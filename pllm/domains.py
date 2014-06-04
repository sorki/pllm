import threading

import libvirt
from twisted.python import log

import util


class Domain(object):
    def __init__(self):
        self.screen = None
        self.screen_id = 0
        self.screen_lock = threading.RLock()
        self.transport = None

    def start(self):
        raise NotImplementedError

    def stop(self):
        raise NotImplementedError

    def restart(self):
        self.stop()
        self.start()

    # shortcuts
    def write(self, keys):
        for key in keys:
            self.key_press(key)

    def click(self):
        self.mouse_press(1)

    def clickxy(self, x, y):
        #self.mouse_move(x, y)
        self.mouse_drag(x, y)
        self.mouse_press(1)

    # composition with transport
    def trans(self, method, *args, **kwargs):
        if not self.transport:
            raise RuntimeError("domain has no transport assigned")

        if hasattr(self.transport, method):
            m = getattr(self.transport, method)
            return m(*args, **kwargs)

        raise AttributeError("transport has no attribute '{0}'".format(method))

    # following methods define an API that
    # self.transport object has to provide
    def key_press(self, key):
        self.trans('key_press', key)

    def key_down(self, key):
        self.trans('key_down', key)

    def key_up(self, key):
        self.trans('key_up', key)

    def mouse_press(self, button):
        self.trans('mouse_press', button)

    def mouse_down(self, button):
        self.trans('mouse_down', button)

    def mouse_up(self, button):
        self.trans('mouse_up', button)

    def mouse_move(self, x, y):
        self.trans('mouse_move', x, y)

    def mouse_drag(self, x, y, step=1):
        self.trans('mouse_drag', x, y, step=step)


class LibvirtDomain(Domain):
    def __init__(self, ident, dom):
        super(LibvirtDomain, self).__init__()
        self.ident = ident
        self.dom = dom

    def start(self):
        log.msg('Creating domain')
        self.dom.create()

    def stop(self):
        util.destroy_libvirt_domain(self.dom)

    def is_running(self):
        return self.dom.info()[0] == libvirt.VIR_DOMAIN_RUNNING
