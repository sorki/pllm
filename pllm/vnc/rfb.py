"""
RFB protocol implementation, client side.

Override RFBClient and RFBFactory in your application.

Reference:
http://www.realvnc.com/docs/rfbproto.pdf

(C) 2003 cliechti@gmx.net
    2014 rmarko@fedoraproject.org
      - stripped version
      - cleaned up, removed pyDes dep and password auth support
      - added PSEUDOENC_ (mainly DESKTOP_SIZE is important for resizing support)
      - python3 compat

MIT License
"""

import math
from struct import pack, unpack
from twisted.python import log
from twisted.internet.protocol import ClientFactory, Protocol

#encoding-type
#for SetEncodings()
RAW_ENCODING = 0
COPY_RECTANGLE_ENCODING = 1
RRE_ENCODING = 2
CORRE_ENCODING = 4
HEXTILE_ENCODING = 5
ZLIB_ENCODING = 6
TIGHT_ENCODING = 7
ZLIBHEX_ENCODING = 8
ZRLE_ENCODING = 16
#0xffffff00 to 0xffffffff tight options
PSEUDOENC_CURSOR = -239
PSEUDOENC_XCURSOR = -240
PSEUDOENC_DESKTOP_SIZE = -223
PSEUDOENC_EXTENDED_DESKTOP_SIZE = -308
PSEUDOENC_DESKTOP_NAME = -307
PSEUDOENC_FENCE = -312
PSEUDOENC_CONTINUOUS_UPDATES = -313


class RFBClient(Protocol):

    def __init__(self):
        self.debug = False
        self._packet = []
        self._packet_len = 0
        self._handler = self._handleInitial
        self._already_expecting = 0

    #------------------------------------------------------
    # states used on connection startup
    #------------------------------------------------------

    def _handleInitial(self):
        buffer = ''.join(self._packet)
        if '\n' in buffer:
            if buffer[:3] == 'RFB':
                #~ print "rfb"
                major, minor = [int(x) for x in buffer[3:-1].split('.')]
                if (major, minor) not in [(3, 3), (3, 7),
                                          (3, 8), (3, 889), (4, 0)]:

                    log.msg("wrong protocol version, {0}.{1}\n"
                            .format(major, minor))
                    self.transport.loseConnection()
            buffer = buffer[12:]
            self.transport.write('RFB 003.003\n')
            self._packet[:] = [buffer]
            self._packet_len = len(buffer)
            self._handler = self._handleExpected
            self.expect(self._handleAuth, 4)
        else:
            self._packet[:] = [buffer]
            self._packet_len = len(buffer)

    def _handleAuth(self, block):
        (auth,) = unpack("!I", block)
        #~ print "auth:", auth
        if auth == 0:
            self.expect(self._handleConnFailed, 4)
        elif auth == 1:
            self._doClientInitialization()
            return
        elif auth == 2:
            self.expect(self._handleVNCAuth, 16)
        else:
            log.msg("unknown auth response ({0})".format(auth))

    def _handleConnFailed(self, block):
        (waitfor,) = unpack("!I", block)
        self.expect(self._handleConnMessage, waitfor)

    def _handleConnMessage(self, block):
        log.msg("Connection refused: {0}".format(block))

    def _handleVNCAuth(self, block):
        self._challenge = block
        self.vncRequestPassword()
        self.expect(self._handleVNCAuthResult, 4)

    def _handleVNCAuthResult(self, block):
        (result,) = unpack("!I", block)
        #~ print "auth:", auth
        if result == 0:     # OK
            self._doClientInitialization()
            return
        elif result == 1:   # failed
            self.vncAuthFailed("autenthication failed")
            self.transport.loseConnection()
        elif result == 2:   # too many
            self.vncAuthFailed("too many tries to log in")
            self.transport.loseConnection()
        else:
            log.msg("unknown auth response ({0})".format(result))

    def _doClientInitialization(self):
        self.transport.write(pack("!B", self.factory.shared))
        self.expect(self._handleServerInit, 24)

    def _handleServerInit(self, block):
        (self.width, self.height, pixformat, namelen) = unpack("!HH16sI", block)
        (self.bpp, self.depth, self.bigendian, self.truecolor,
         self.redmax, self.greenmax, self.bluemax,
         self.redshift, self.greenshift, self.blueshift) = \
            unpack("!BBBBHHHBBBxxx", pixformat)
        self.bypp = self.bpp / 8        # calc bytes per pixel
        self.expect(self._handleServerName, namelen)

    def _handleServerName(self, block):
        self.name = block
        #callback:
        self.vncConnectionMade()
        self.expect(self._handleConnection, 1)

    #------------------------------------------------------
    # Server to client messages
    #------------------------------------------------------
    def _handleConnection(self, block):
        (msgid,) = unpack("!B", block)
        if msgid == 0:
            self.expect(self._handleFramebufferUpdate, 3)
        elif msgid == 2:
            self.bell()
            self.expect(self._handleConnection, 1)
        elif msgid == 3:
            self.expect(self._handleServerCutText, 7)
        else:
            if self.debug:
                log.msg("unknown message received (id {0})".format(msgid))
            self.expect(self._handleConnection, 1)

    def _handleFramebufferUpdate(self, block):
        (self.rectangles,) = unpack("!xH", block)
        self.rectanglePos = []
        self.beginUpdate()
        self._doConnection()

    def _doConnection(self):
        if self.rectangles:
            self.expect(self._handleRectangle, 12)
        else:
            self.commitUpdate(self.rectanglePos)
            self.expect(self._handleConnection, 1)

    def _handleRectangle(self, block):
        (x, y, width, height, encoding) = unpack("!HHHHi", block)
        if self.rectangles:
            self.rectangles -= 1
            self.rectanglePos.append((x, y, width, height))
            if encoding == COPY_RECTANGLE_ENCODING:
                self.expect(self._handleDecodeCopyrect, 4, x, y, width, height)
            elif encoding == RAW_ENCODING:
                self.expect(self._handleDecodeRAW,
                            width * height * self.bypp, x, y, width, height)
            elif encoding == HEXTILE_ENCODING:
                self._doNextHextileSubrect(
                    None, None, x, y, width, height, None, None)
            elif encoding == CORRE_ENCODING:
                self.expect(self._handleDecodeCORRE,
                            4 + self.bypp, x, y, width, height)
            elif encoding == RRE_ENCODING:
                self.expect(self._handleDecodeRRE,
                            4 + self.bypp, x, y, width, height)
            #~ elif encoding == ZRLE_ENCODING:
                #~ self.expect(self._handleDecodeZRLE, )
            elif encoding == PSEUDOENC_CURSOR:
                length = width * height * self.bypp
                length += int(math.floor((width + 7.0) / 8)) * height
                self.expect(self._handleDecodePsuedoCursor,
                            length, x, y, width, height)
            elif encoding in [
                    PSEUDOENC_DESKTOP_SIZE,
                    PSEUDOENC_EXTENDED_DESKTOP_SIZE,
                    PSEUDOENC_CONTINUOUS_UPDATES,
                    PSEUDOENC_FENCE,
                    PSEUDOENC_XCURSOR]:

                pass
            else:
                if self.debug:
                    log.msg("unknown encoding received (encoding {0})"
                            .format(encoding))
                self._doConnection()
        else:
            self._doConnection()

    # ---  RAW Encoding
    def _handleDecodeRAW(self, block, x, y, width, height):
        #TODO convert pixel format?
        self.updateRectangle(x, y, width, height, block)
        self._doConnection()

    # ---  CopyRect Encoding
    def _handleDecodeCopyrect(self, block, x, y, width, height):
        (srcx, srcy) = unpack("!HH", block)
        self.copyRectangle(srcx, srcy, x, y, width, height)
        self._doConnection()

    # ---  RRE Encoding
    def _handleDecodeRRE(self, block, x, y, width, height):
        (subrects,) = unpack("!I", block[:4])
        color = block[4:]
        self.fillRectangle(x, y, width, height, color)
        if subrects:
            self.expect(self._handleRRESubRectangles,
                        (8 + self.bypp) * subrects, x, y)
        else:
            self._doConnection()

    def _handleRRESubRectangles(self, block, topx, topy):
        #~ print "_handleRRESubRectangle"
        pos = 0
        end = len(block)
        sz = self.bypp + 8
        format = "!{0}sHHHH".format(self.bypp)
        while pos < end:
            (color, x, y, width, height) = unpack(format, block[pos:pos + sz])
            self.fillRectangle(topx + x, topy + y, width, height, color)
            pos += sz
        self._doConnection()

    # ---  CoRRE Encoding
    def _handleDecodeCORRE(self, block, x, y, width, height):
        (subrects,) = unpack("!I", block[:4])
        color = block[4:]
        self.fillRectangle(x, y, width, height, color)
        if subrects:
            self.expect(self._handleDecodeCORRERectangles,
                        (4 + self.bypp) * subrects, x, y)
        else:
            self._doConnection()

    def _handleDecodeCORRERectangles(self, block, topx, topy):
        #~ print "_handleDecodeCORRERectangle"
        pos = 0
        sz = self.bypp + 4
        format = "!{0}sBBBB".format(self.bypp)
        while pos < sz:
            (color, x, y, width, height) = unpack(format, block[pos:pos + sz])
            self.fillRectangle(topx + x, topy + y, width, height, color)
            pos += sz
        self._doConnection()

    # ---  Hexile Encoding

    def _doNextHextileSubrect(self, bg, color, x, y, width, height, tx, ty):
        #coords of next tile
        #its line after line of tiles
        #finished when the last line is completly received

        #dont inc the first time
        if tx is not None:
            #calc next subrect pos
            tx += 16
            if tx >= x + width:
                tx = x
                ty += 16
        else:
            tx = x
            ty = y
        #more tiles?
        if ty >= y + height:
            self._doConnection()
        else:
            self.expect(self._handleDecodeHextile,
                        1, bg, color, x, y, width, height, tx, ty)

    def _handleDecodeHextile(self, block, bg, color,
                             x, y, width, height, tx, ty):

        (subencoding,) = unpack("!B", block)
        #calc tile size
        tw = th = 16
        if x + width - tx < 16:
            tw = x + width - tx
        if y + height - ty < 16:
            th = y + height - ty
        #decode tile
        if subencoding & 1:     # RAW
            self.expect(self._handleDecodeHextileRAW,
                        tw * th * self.bypp, bg, color,
                        x, y, width, height, tx, ty, tw, th)
        else:
            numbytes = 0
            if subencoding & 2:     # BackgroundSpecified
                numbytes += self.bypp
            if subencoding & 4:     # ForegroundSpecified
                numbytes += self.bypp
            if subencoding & 8:     # AnySubrects
                numbytes += 1
            if numbytes:
                self.expect(self._handleDecodeHextileSubrect,
                            numbytes, subencoding, bg, color,
                            x, y, width, height, tx, ty, tw, th)
            else:
                self.fillRectangle(tx, ty, tw, th, bg)
                self._doNextHextileSubrect(bg, color, x, y,
                                           width, height, tx, ty)

    def _handleDecodeHextileSubrect(self, block, subencoding, bg, color,
                                    x, y, width, height, tx, ty, tw, th):

        subrects = 0
        pos = 0
        if subencoding & 2:     # BackgroundSpecified
            bg = block[:self.bypp]
            pos += self.bypp
        self.fillRectangle(tx, ty, tw, th, bg)
        if subencoding & 4:     # ForegroundSpecified
            color = block[pos:pos + self.bypp]
            pos += self.bypp
        if subencoding & 8:     # AnySubrects
            #~ (subrects, ) = unpack("!B", block)
            subrects = ord(block[pos])
        #~ print subrects
        if subrects:
            if subencoding & 16:  # SubrectsColoured
                self.expect(self._handleDecodeHextileSubrectsColoured,
                            (self.bypp + 2) * subrects, bg, color, subrects,
                            x, y, width, height, tx, ty, tw, th)
            else:
                self.expect(self._handleDecodeHextileSubrectsFG, 2 * subrects,
                            bg, color, subrects, x, y,
                            width, height, tx, ty, tw, th)
        else:
            self._doNextHextileSubrect(bg, color, x, y, width, height, tx, ty)

    def _handleDecodeHextileRAW(self, block, bg, color,
                                x, y, width, height, tx, ty, tw, th):
        """ Decoded tile in raw encoding  """

        self.updateRectangle(tx, ty, tw, th, block)
        self._doNextHextileSubrect(bg, color, x, y, width, height, tx, ty)

    def _handleDecodeHextileSubrectsColoured(self, block, bg, color,
                                             subrects, x, y, width, height,
                                             tx, ty, tw, th):
        """ Decode subrects with their own color """

        sz = self.bypp + 2
        pos = 0
        end = len(block)
        while pos < end:
            pos2 = pos + self.bypp
            color = block[pos:pos2]
            xy = ord(block[pos2])
            wh = ord(block[pos2 + 1])
            sx = xy >> 4
            sy = xy & 0xf
            sw = (wh >> 4) + 1
            sh = (wh & 0xf) + 1
            self.fillRectangle(tx + sx, ty + sy, sw, sh, color)
            pos += sz
        self._doNextHextileSubrect(bg, color, x, y, width, height, tx, ty)

    def _handleDecodeHextileSubrectsFG(self, block, bg, color,
                                       subrects, x, y, width, height,
                                       tx, ty, tw, th):
        """ all subrect with same color """

        pos = 0
        end = len(block)
        while pos < end:
            xy = ord(block[pos])
            wh = ord(block[pos + 1])
            sx = xy >> 4
            sy = xy & 0xf
            sw = (wh >> 4) + 1
            sh = (wh & 0xf) + 1
            self.fillRectangle(tx + sx, ty + sy, sw, sh, color)
            pos += 2
        self._doNextHextileSubrect(bg, color, x, y, width, height, tx, ty)

    # ---  ZRLE Encoding
    def _handleDecodeZRLE(self, block):
        raise NotImplementedError

    # --- Pseudo Cursor Encoding
    def _handleDecodePsuedoCursor(self, block, x, y, width, height):
        split = width * height * self.bypp
        image = block[:split]
        mask = block[split:]
        self.updateCursor(x, y, width, height, image, mask)
        self._doConnection()

    # ---  other server messages

    def _handleServerCutText(self, block):
        (length, ) = unpack("!xxxI", block)
        self.expect(self._handleServerCutTextValue, length)

    def _handleServerCutTextValue(self, block):
        self.copy_text(block)
        self.expect(self._handleConnection, 1)

    #------------------------------------------------------
    # incomming data redirector
    #------------------------------------------------------
    def dataReceived(self, data):
        #~ sys.stdout.write(repr(data) + '\n')
        #~ print len(data), ", ", len(self._packet)
        self._packet.append(data)
        self._packet_len += len(data)
        self._handler()

    def _handleExpected(self):
        if self._packet_len >= self._expected_len:
            buffer = ''.join(self._packet)
            while len(buffer) >= self._expected_len:
                self._already_expecting = 1
                block = buffer[:self._expected_len]
                buffer = buffer[self._expected_len:]
                self._expected_handler(block, *self._expected_args,
                                       **self._expected_kwargs)
            self._packet[:] = [buffer]
            self._packet_len = len(buffer)
            self._already_expecting = 0

    def expect(self, handler, size, *args, **kwargs):
        self._expected_handler = handler
        self._expected_len = size
        self._expected_args = args
        self._expected_kwargs = kwargs
        if not self._already_expecting:
            self._handleExpected()  # just in case that there is already enough data

    #------------------------------------------------------
    # client -> server messages
    #------------------------------------------------------

    def setPixelFormat(self, bpp=32, depth=24, bigendian=0,
                       truecolor=1,
                       redmax=255, greenmax=255, bluemax=255,
                       redshift=0, greenshift=8, blueshift=16):

        pixformat = pack("!BBBBHHHBBBxxx", bpp, depth, bigendian, truecolor,
                         redmax, greenmax, bluemax,
                         redshift, greenshift, blueshift)

        self.transport.write(pack("!Bxxx16s", 0, pixformat))
        #rember these settings
        self.bpp = bpp
        self.depth = depth
        self.bigendian = bigendian
        self.truecolor = truecolor
        self.redmax, self.greenmax, self.bluemax = redmax, greenmax, bluemax
        self.redshift, self.greenshift = redshift, greenshift
        self.blueshift = blueshift
        self.bypp = self.bpp / 8  # calc bytes per pixel
        #~ print self.bypp

    def setEncodings(self, list_of_encodings):
        self.transport.write(pack("!BxH", 2, len(list_of_encodings)))
        for encoding in list_of_encodings:
            self.transport.write(pack("!i", encoding))

    def framebufferUpdateRequest(self, x=0, y=0,
                                 width=None, height=None, incremental=0):

        if width is None:
            width = self.width - x
        if height is None:
            height = self.height - y
        self.transport.write(pack("!BBHHHH", 3, incremental,
                                  x, y, width, height))

    def keyEvent(self, key, down=1):
        """
        For most ordinary keys, the "keysym" is the same
        as the corresponding ASCII value.
        Other common keys are shown in the KEY_ constants.
        """

        self.transport.write(pack("!BBxxI", 4, down, key))

    def pointerEvent(self, x, y, buttonmask=0):
        """Indicates either pointer movement or a pointer button press or release. The pointer is
           now at (x-position, y-position), and the current state of buttons 1 to 8 are represented
           by bits 0 to 7 of button-mask respectively, 0 meaning up, 1 meaning down (pressed).
        """
        self.transport.write(pack("!BBHH", 5, buttonmask, x, y))

    def clientCutText(self, message):
        """The client has new ASCII text in its cut buffer.
           (aka clipboard)
        """
        self.transport.write(pack("!BxxxI", 6, len(message)) + message)

    #------------------------------------------------------
    # callbacks
    # override these in your application
    #------------------------------------------------------
    def vncConnectionMade(self):
        """ Connection is initialized and ready.
            typicaly, the pixel format is set here."""

    def vncRequestPassword(self):
        """a password is needed to log on, use sendPassword() to
           send one."""

        log.msg("Password auth not supported")
        self.transport.loseConnection()

    def vncAuthFailed(self, reason):
        """called when the authentication failed.
           the connection is closed."""
        log.msg("Cannot connect: {0}".format(reason))

    def beginUpdate(self):
        """called before a series of updateRectangle(),
           copyRectangle() or fillRectangle()."""

    def commitUpdate(self, rectangles=None):
        """called after a series of updateRectangle(), copyRectangle()
           or fillRectangle() are finished.
           typicaly, here is the place to request the next screen
           update with FramebufferUpdateRequest(incremental=1).
           argument is a list of tuples (x,y,w,h) with the updated
           rectangles."""

    def updateRectangle(self, x, y, width, height, data):
        """new bitmap data. data is a string in the pixel format set
           up earlier."""

    def copyRectangle(self, srcx, srcy, x, y, width, height):
        """used for copyrect encoding. copy the given rectangle
           (src, srxy, width, height) to the target coords (x,y)"""

    def fillRectangle(self, x, y, width, height, color):
        """fill the area with the color. the color is a string in
           the pixel format set up earlier"""
        #fallback variant, use update recatngle
        #override with specialized function for better performance
        self.updateRectangle(x, y, width, height, color * width * height)

    def updateCursor(self, x, y, width, height, image, mask):
        """ New cursor, focuses at (x, y)
        """

    def bell(self):
        """bell"""

    def copy_text(self, text):
        """The server has new ASCII text in its cut buffer.
           (aka clipboard)"""


class RFBFactory(ClientFactory):
    """A factory for remote frame buffer connections."""

    # the class of the protocol to build
    # should be overriden by application to use a derrived class
    protocol = RFBClient

    def __init__(self, shared=0):
        self.shared = shared
        self.proto = None

    def buildProtocol(self, addr):
        proto = self.protocol()
        return proto
