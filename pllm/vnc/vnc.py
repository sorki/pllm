import cv2
import numpy as np

from twisted.python import log
from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.internet.protocol import ClientFactory


import rfb
import keys


# key/mouse* methods from vncdotool.client (MIT License)


class VNC(rfb.RFBClient):
    x = 0
    y = 0
    buttons = 0
    screen = None
    deferred = None

    def vncConnectionMade(self):
        self.setPixelFormat()
        self.setEncodings([rfb.RAW_ENCODING, rfb.PSEUDOENC_CURSOR,
                           rfb.PSEUDOENC_DESKTOP_SIZE])
        self.factory.clientConnectionMade(self)

    def _decode_key(self, key):
        return [keys.KEYMAP.get(k) or ord(k) for k in key.split('-')]

    def key_press(self, key):
        """ Send a key press to the server

            key: string: either [a-z] or a from KEYMAP
        """
        log.msg('key_press {0}'.format(key))
        self.key_down(key)
        self.key_up(key)

        return self

    def key_down(self, key):
        log.msg('key_down {0}'.format(key))
        keys = self._decode_key(key)
        for k in keys:
            self.keyEvent(k, down=1)

        return self

    def key_up(self, key):
        log.msg('key_up {0}'.format(key))
        keys = self._decode_key(key)
        for k in keys:
            self.keyEvent(k, down=0)

        return self

    def mouse_press(self, button):
        """ Send a mouse click at the last set position

            button: int: [1-n]

        """
        log.msg('mouse_press {0}'.format(button))
        buttons = self.buttons | (1 << (button - 1))
        self.pointerEvent(self.x, self.y, buttonmask=buttons)
        self.pointerEvent(self.x, self.y, buttonmask=self.buttons)

        self.framebufferUpdateRequest()

        return self

    def mouse_down(self, button):
        """ Send a mouse button down at the last set position

            button: int: [1-n]

        """
        log.msg('mouse_down {0}'.format(button))
        self.buttons |= 1 << (button - 1)
        self.pointerEvent(self.x, self.y, buttonmask=self.buttons)

    def mouse_up(self, button):
        """ Send a mouse button released at the last set position

            button: int: [1-n]

        """
        log.msg('mouse_up {0}'.format(button))
        self.buttons &= ~(1 << (button - 1))
        self.pointerEvent(self.x, self.y, buttonmask=self.buttons)

    def mouse_move(self, x, y):
        """ Move the mouse pointer to position (x, y)
        """
        #log.msg('mouse_move {0},{1}'.format(x, y))
        self.x, self.y = x, y
        self.pointerEvent(x, y, self.buttons)
        return self

    def mouse_drag(self, x, y, step=1):
        """ Move the mouse point to position (x, y) in increments of step
        """
        log.msg('mouse_drag {0},{1}'.format(x, y))
        if x < self.x:
            xsteps = [self.x - i for i in xrange(step, self.x - x + 1, step)]
        else:
            xsteps = xrange(self.x, x, step)

        if y < self.y:
            ysteps = [self.y - i for i in xrange(step, self.y - y + 1, step)]
        else:
            ysteps = xrange(self.y, y, step)

        for ypos in ysteps:
            self.mouse_move(self.x, ypos)

        for xpos in xsteps:
            self.mouse_move(xpos, self.y)

        self.mouse_move(x, y)

        return self

    def bell(self):
        log.msg('VNC bell')

    def save_screen(self, fpath, screen=None):
        log.msg('Saving {0}'.format(fpath))
        if screen:
            cv2.imwrite(fpath, screen)
        else:
            cv2.imwrite(fpath, self.screen)

    def updateRectangle(self, x, y, width, height, data):
        if not data:
            return

        # create opencv image and convert colors properly
        shape = (height, width, 4)
        img = np.ndarray(shape, dtype=np.uint8, buffer=data)
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)

        if self.screen is None:
            self.screen = img

        ch, cw, d = self.screen.shape

        if cw < (x + width) or ch < (y + height):
            # upward screen resize
            ncw = max(cw, x + width)
            nch = max(ch, y + height)
            nimg = np.ndarray((nch, ncw, d), dtype=np.uint8)
            nimg[0:ch, 0:cw] = self.screen
            nimg[y:height, x:width] = img
            self.screen = nimg

        elif cw == width and ch == height:
            self.screen = img

        else:
            self.screen[y:y + height, x:x + width] = img

    def commitUpdate(self, rectangles=None):
        if self.deferred:
            d = self.deferred
            self.deferred = None
            # callback one second later so we catch all the changes
            # caused by our last action. If we callback instantly
            # we get in-transition screenshot which is not what we want
            reactor.callLater(1, d.callback, self)


class VNCFactory(ClientFactory):
    """A factory for remote frame buffer connections."""

    protocol = VNC

    def __init__(self, shared=0):
        self.shared = shared
        self.deferred = Deferred()
        self.proto = None

    def clientConnectionMade(self, protocol):
        log.msg("VNC connection made")
        self.proto = protocol
        self.proto.framebufferUpdateRequest()
        self.deferred.callback(self.proto)
