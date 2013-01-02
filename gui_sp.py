import time
import signal
import logging
import threading

import cv

import gtk
import gobject
import SpiceClientGtk as spice

from pllm import domains, config, fuhacko, xutil

def gtk_yield():
    while gtk.events_pending():
        gtk.main_iteration()
    time.sleep(.01)

class GuiSpiceDomain(domains.Domain):
    def __init__(self, display):
        super(GuiSpiceDomain, self).__init__()
        self.display = display

    def send_motion_event(self, x, y):
        event = gtk.gdk.Event(gtk.gdk.MOTION_NOTIFY)
        event.x = float(x)
        event.y = float(y)
        event.send_event = True
        event.time = 0
        self.display.emit('motion-notify-event', event)
        gtk_yield()

    def send_button_event(self, x, y, button, press=True):
        # 1 left, 2 middle, 3 right
        etyp = gtk.gdk.BUTTON_PRESS
        if not press:
            etyp = gtk.gdk.BUTTON_RELEASE

        event = gtk.gdk.Event(etyp)
        event.button = button
        event.x = float(x)
        event.y = float(y)
        event.send_event = True
        event.time = 0
        if press:
            self.display.emit('button-press-event', event)
        else:
            event.state = getattr(gtk.gdk, 'BUTTON{0}_MASK'.format(button))
            self.display.emit('button-release-event', event)

        gtk_yield()

    def click(self, x, y):
        logging.debug('Click {0}x{1}'.format(x,y))
        #x = x * 0x7fff / 1024
        #y = y * 0x7fff / 768

    def send_key_event(self, code, kval, press=True):
        etyp = gtk.gdk.KEY_PRESS
        if not press:
            etyp = gtk.gdk.KEY_RELEASE

        event = gtk.gdk.Event(etyp)
        event.hardware_keycode = code
        event.keyval = kval
        #event.send_event = True
        event.time = 0
        self.display.emit('key-press-event', event)

        while gtk.events_pending():
            gtk.main_iteration()
        time.sleep(0.01)

    def send_key(self, key):
        trans = {
            'ret': 'Return',
            'tab': 'Tab',
        }

        if key in trans:
            key = trans[key]

        print('Key {0}'.format(key))

        code, kval, mask = xutil.get_keycode_keysym(key)
        scode = 50
        skval = gtk.keysyms.Shift_L

        if mask == 1:
            self.send_key_event(scode, skval, True)

#            pass
#        i = 0
        for i in [0, 1]:
            self.send_key_event(code, kval, i == 0)

        if mask == 1:
            self.send_key_event(scode, skval, False)

    def cv_image(self):
        pixbuf = self.display.get_pixbuf()
        if pixbuf is None:
            return None

        cv_im = cv.CreateImageHeader((pixbuf.get_width(), pixbuf.get_height()),
            cv.IPL_DEPTH_8U, 3)

        cv.SetData(cv_im, pixbuf.get_pixels(), pixbuf.get_rowstride())
        cv.CvtColor(cv_im, cv_im, cv.CV_BGR2RGB)

        return cv_im

class GuiApp(object):
    def destroy(self, widget, data=None):
        gtk.main_quit()

    def key(self, args, ev):
        if ev.keyval == gtk.gdk.keyval_from_name("X"):
            import IPython
            IPython.embed()

        if ev.keyval == gtk.gdk.keyval_from_name("W"):
            print 'evt'
            x,y = 190., 500.
            # 680, 590
            event = gtk.gdk.Event(gtk.gdk.MOTION_NOTIFY)
            event.x = float(x)
            event.y = float(y)
            event.send_event = True
            event.time = 0
            self.display.emit('motion-notify-event', event)
            gtk_yield()

            button = 1

            for press in [True, False]:
                etyp = gtk.gdk.BUTTON_PRESS
                if not press:
                    etyp = gtk.gdk.BUTTON_RELEASE

                event = gtk.gdk.Event(etyp)
                event.button = button
                event.x = float(x)
                event.y = float(y)
                event.send_event = True
                event.time = 0
                if press:
                    self.display.emit('button-press-event', event)
                else:
                    event.state = getattr(gtk.gdk, 'BUTTON{0}_MASK'.format(button))
                    self.display.emit('button-release-event', event)

                gtk_yield()

            return True

        if ev.keyval == gtk.gdk.keyval_from_name("E"):
            print 'evt'
            x,y = 190., 500.
            #x,y = 838., 510.
            event = gtk.gdk.Event(gtk.gdk.MOTION_NOTIFY)
            event.x = x
            event.y = y
            event.send_event = True
            event.time = 0
            self.display.emit('motion-notify-event', event)
            gtk_yield()

            event = gtk.gdk.Event(gtk.gdk.BUTTON_PRESS)
            event.button = 1
            event.x = x
            event.y = y
            event.send_event = True
            event.time = 0
            self.display.emit('button-press-event', event)
            gtk_yield()

            event = gtk.gdk.Event(gtk.gdk.BUTTON_RELEASE)
            event.button = 1
            event.state = gtk.gdk.BUTTON1_MASK
            event.x = x
            event.y = y
            event.send_event = True
            event.time = 0
            self.display.emit('button-release-event', event)
            gtk_yield()

            return True

    def disp_key(self, args, ev):
        print('hw:{0}, sw:{1}'.format(ev.hardware_keycode, ev.keyval))
        print ev.type
        print ev.time

    def disp_mov(self, args, ev):
        print ev.x, ev.y

    def disp_btn(self, args, ev):
        print ev.x, ev.y, ev.button, ev.state

    def __init__(self):
        window = gtk.Window()

        self.display = None
        self.display_channel = None
        self.spice_session = None

        self.window = window

        self.mainbox = gtk.VBox()
        window.add(self.mainbox)
        window.connect('destroy', self.destroy)
        window.connect("key-press-event", self.key)

        self.open_host()

        window.show_all()

    def _init_widget(self):
        self.mainbox.add(self.display)
        #self.display.connect("key-press-event", self.disp_key)
        self.display.connect("motion-notify-event", self.disp_mov)
        self.display.connect("button-press-event", self.disp_btn)
        self.display.connect("button-release-event", self.disp_btn)
        self.display.show()

    def _main_channel_event_cb(self, channel, event):
        if event == spice.CHANNEL_CLOSED:
            print 'disconnected'
        elif event == spice.CHANNEL_ERROR_AUTH:
            print 'auth_error'

    def _channel_new_cb(self, session, channel):
        #gobject.GObject.connect(channel, "open-fd",
        #                        self._channel_open_fd_request)

        if type(channel) == spice.MainChannel:
            channel.connect_after("channel-event", self._main_channel_event_cb)
            return

        if type(channel) == spice.DisplayChannel:
            channel_id = channel.get_property("channel-id")

            if channel_id != 0:
                logging.debug("Spice multi-head unsupported")
                return

            self.display_channel = channel
            self.display = spice.Display(self.spice_session, channel_id)
            #self.console.window.get_object("console-vnc-viewport").add(self.display)
            self._init_widget()
            #self.console.connected()
            return

        return
        if (type(channel) in [spice.PlaybackChannel, spice.RecordChannel] and
            not self.audio):
            self.audio = spice.Audio(self.spice_session)
            return

    def open_host(self):
        host = 'localhost'
        port = 5900

        uri = "spice://"
        uri += str(host) + "?port=" + str(port)
        logging.debug("spice uri: %s", uri)

        self.spice_session = spice.Session()
        self.spice_session.set_property("uri", uri)
        gobject.GObject.connect(self.spice_session, "channel-new",
                                self._channel_new_cb)
        self.spice_session.connect()



    def main(self):
        gtk.main()

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    logging.basicConfig(level=logging.DEBUG)

    gui = GuiApp()

    target = config.get('screenshot_target')

    even = True

    def cbs():
        dom = GuiSpiceDomain(gui.display)

        def screenshot():
            #import IPython
            #IPython.embed()
            dom.screenshot()
            print dom.screen_id
            cv.SaveImage('{0}/{1}.png'.format(target,
                    dom.screen_id), dom.screen)

            return True

        def send():
            #gtk.threads_enter()
            #dom = GuiSpiceDomain(gui.display)
            time.sleep(1)
            dom.send_keys('No musi jebat!')
            #dom.send_key('ret')
            #gtk.threads_leave()

            return True

        def click():
            x,y = 838., 510.
            x,y = 190., 500.
            dom.send_motion_event(x, y)
            dom.send_button_event(x, y, 1)
            dom.send_button_event(x, y, 1, False)
            print 'wat'

        def click2():
            global even
            print 'evt'
            x,y = 190., 500.
            if not even:
                x,y = 680, 590
                even = True
            else:
                even = False
            event = gtk.gdk.Event(gtk.gdk.MOTION_NOTIFY)
            event.x = float(x)
            event.y = float(y)
            event.send_event = True
            event.time = 0
            dom.display.emit('motion-notify-event', event)
            gtk_yield()

            button = 1

            for press in [True, False]:
                etyp = gtk.gdk.BUTTON_PRESS
                if not press:
                    etyp = gtk.gdk.BUTTON_RELEASE

                event = gtk.gdk.Event(etyp)
                event.button = button
                event.x = float(x)
                event.y = float(y)
                event.send_event = True
                event.time = 0
                if press:
                    dom.display.emit('button-press-event', event)
                else:
                    event.state = getattr(gtk.gdk, 'BUTTON{0}_MASK'.format(button))
                    dom.display.emit('button-release-event', event)

                gtk_yield()

            print 'evt_end'
            return True


        gobject.timeout_add_seconds(1, screenshot)
        #gobject.timeout_add_seconds(1, click)
        gobject.timeout_add_seconds(4, click2)
        gobject.timeout_add_seconds(2, send)

    #gobject.timeout_add_seconds(2, cbs)
    #gobject.timeout_add_seconds(2, send)


    '''
    class FThread(threading.Thread):
        def __init__(self, dom):
            super(FThread, self).__init__()
            self.fuh = fuhacko.Fuhacko(dom)
            self.running = False

        def run(self):
            time.sleep(2)
            with open('pseudo.py') as f:
                code = f.read()
                self.fuh.start(code)

    ff = FThread(dom)
    ff.start()
    '''

    #gobject.timeout_add_seconds(5, dom.click, 400, 400)
    gui.main()
