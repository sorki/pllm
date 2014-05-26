#!/usr/bin/python
import os
import logging

from twisted.python import log
from twisted.application import service
from twisted.application.internet import TCPClient
from twisted.internet import task
from twisted.internet import reactor
from twisted.internet.defer import Deferred

from pllm import manhole, interpret
from pllm import backends, config

from pllm.vnc.vnc import VNCFactory


def trace(func):                         # Use function, not class with __call__
    def wrapper(*args, **kwargs):
        print('{0}'.format(func.__name__))
        val = func(*args, **kwargs)
        print('/{0}'.format(func.__name__))
        return val
    return wrapper

CAP_DELAY = .5


class Pllm(object):
    '''
    Master state machine
    '''

    def __init__(self, application):
        super(Pllm, self).__init__()

        self.vnc = None
        self.int = None
        self.dom = None
        self.manhole = None
        self.app = application

        self.dom_ident = 'f20'
        f = '/var/lib/libvirt/images/Fedora-20-x86_64-netinst.iso'
        self.dom_media_path = f
        self.libvirt_uri = config.get('libvirt_uri')
        self.storage_pool_name = config.get('storage_pool_name')

        self.work_dir = config.get('work_dir')
        self.state = 'VM_INIT'

    @trace
    def main(self):
        if self.state == 'VM_INIT':
            if not self.dom:
                self.start_domain()

            elif self.dom.is_running:
                self.state = 'VNC_INIT'

        if self.state == 'VNC_INIT':
            if not self.vnc:
                self.start_vnc()
            else:
                self.state = 'MANHOLE_INIT'

        if self.state == 'MANHOLE_INIT':
            if not self.manhole:
                self.start_manhole()
            else:
                self.state = 'MAIN'

        if self.state == 'MAIN':
            if not self.int:
                self.start_interpret()
            else:
                self.state = 'RUNNING'

        reactor.callLater(1, self.main)

    def start_domain(self):
        lv = backends.LibvirtBackend(self.libvirt_uri, self.storage_pool_name)
        xml = 'data/{0}.xml'.format(self.dom_ident)

        with open(xml) as f:
            xml = f.read()

        lv.remove_test_vm(self.dom_ident)
        self.dom = lv.create_test_vm(xml, self.dom_ident, self.dom_media_path)
        self.dom.start()

    def start_vnc(self):
        vnc_factory = VNCFactory()
        vnc_factory.deferred.addCallback(self.vnc_started)
        vnc_service = TCPClient("localhost", 5900, vnc_factory)
        vnc_service.setServiceParent(self.app)

    def start_manhole(self):
        opts = {
            'ssh':    1667,
            'namespace': {'pllm': self},
        }

        self.manhole = manhole.manhole_service(opts)
        self.manhole.setServiceParent(self.app)

    @trace
    def vnc_started(self, proto):
        proto.framebufferUpdateRequest()
        self.schedule_save(proto, 0)
        self.vnc = proto
        self.dom.transport = proto

    def test_rects(self, proto):
        print 'rects'
        print proto
        reactor.callLater(2, proto.keyPress, 'enter')
        reactor.callLater(8, proto.keyPress, 'alt Q')
        #reactor.callLater(12, test_rects, proto)
        #proto.keyPress('alt Q')

    @trace
    def save_screen(self, proto, counter):
        fpath = os.path.join(self.work_dir, "{0}.png".format(counter))
        cpath = os.path.join(self.work_dir, "last.png")
        proto.save_screen(fpath)
        proto.save_screen(cpath)

        with self.dom.screen_lock:
            self.dom.screen = proto.screen
            self.dom.screen_id = counter

        reactor.callLater(CAP_DELAY, self.schedule_save, proto, counter + 1)

    @trace
    def schedule_save(self, proto, counter):
        proto.deferred = Deferred()
        proto.deferred.addCallback(self.save_screen, counter)

    @trace
    def start_jobs(self, proto):
        log.msg("Starting jobs")

        proto.framebufferUpdateRequest()
        #l = task.LoopingCall(ocr, proto)
        #reactor.callLater(1, l.start, 5)

        l2 = task.LoopingCall(self.test_rects, proto)
        l2.start(8)

        #l3 = task.LoopingCall(store_current, proto)
        #l3.start(1)
        self.schedule_save(proto, 0)
        #reactor.callLater(1, l2.start, 5)

    @trace
    def start_interpret(self):
        with open('next_pseudo.py') as f:
            code = f.read()

        self.int = interpret.Interpret(self.dom)
        reactor.callInThread(self.int.start, code)


application = service.Application("PLLM")
app = Pllm(application)
# yield so logging and twistd stuff can be initialized
logging.basicConfig(level=logging.DEBUG)
reactor.callLater(0.1, app.main)
