#!/usr/bin/python
import os
import shutil

from twisted.python import log
from twisted.application import service
from twisted.application.internet import TCPClient, TCPServer
from twisted.internet import task
from twisted.internet import reactor, threads
from twisted.internet.defer import Deferred

from pllm import manhole, interpret
from pllm import backends, config, monitor, util
from pllm.vision import process

from pllm.vnc.vnc import VNCFactory


trace = util.trace

CAP_DELAY = 1


class Pllm(object):
    '''
    Master state machine
    '''

    def __init__(self, application):
        super(Pllm, self).__init__()

        self.vnc = None
        self.int = None
        self.dom = None
        self.mon = None
        self.manhole = None
        self.vision = None
        self.app = application
        self.ocr_enabled = True

        self.dom_ident = 'f21'
        f = '/var/lib/libvirt/images/Fedora-Server-netinst-x86_64-21.iso'
        self.dom_media_path = f
        self.libvirt_uri = config.get('libvirt_uri')
        self.storage_pool_name = config.get('storage_pool_name')

        self.work_dir = config.get('work_dir')
        self.state = 'INIT'

    def main(self):
        prev_state = self.state

        if self.state == 'INIT':
            if not self.mon:
                self.start_monitor()
            else:
                self.state = 'VM_INIT'

        if self.state == 'VM_INIT':
            if not self.dom:
                self.start_domain()

            elif self.dom.is_running:
                self.state = 'VNC_INIT'

        if self.state == 'VNC_INIT':
            if not self.vnc:
                self.start_vnc()
            else:
                self.state = 'VISION_INIT'

        if self.state == 'VISION_INIT':
            if not self.vision:
                self.start_vision()
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

        if prev_state != self.state:
            self.emit('STATE_CHANGE', self.state)

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

    @trace
    def vnc_started(self, proto):
        #proto.framebufferUpdateRequest()
        self.vnc = proto
        self.dom.transport = proto

        self.vnc_loop = task.LoopingCall(proto.framebufferUpdateRequest)
        self.vnc_loop.start(1.0)

        self.schedule_save(proto, 0)

    @trace
    def start_vision(self):
        self.vision = process.VisionPipeline(domain=self.dom)

    def start_manhole(self):
        opts = {
            'ssh':    int(config.get('ssh_port')),
            'namespace': {'pllm': self},
        }

        self.manhole = manhole.manhole_service(opts)
        self.manhole.setServiceParent(self.app)

    def start_monitor(self):
        self.mon = monitor.MonitorFactory()
        monitor_service = TCPServer(int(config.get('monitor_port')), self.mon)
        monitor_service.setServiceParent(self.app)

    def emit(self, msg, data=None):
        self.mon.emit(msg, data)

    @trace
    def store_ocr_results(self, ocr_res):
        full, segments = ocr_res
        log.msg('ocr: full page text length:{0}, segments:{1}'
                .format(len(full), len(segments)))

        log.msg('ocr: full sample: "{0}..."'.format(repr(full[:30])))

        self.emit('OCR_FULL', full)
        self.emit('OCR_SEGMENTS', segments)

        self.dom.text = full
        self.dom.segments = segments

    @trace
    def save_screen(self, proto, counter):
        screendir = os.path.join(self.work_dir,
                                 '{0:03d}'.format(counter))

        similar = process.similar(self.dom.screen, proto.screen)
        if similar:
            print('Similar images, skipping')
            self.emit('SIMILAR')
            reactor.callLater(CAP_DELAY, self.schedule_save, proto, counter)
        else:
            if os.path.isdir(screendir):
                shutil.rmtree(screendir)

            os.mkdir(screendir)

            fpath = os.path.join(screendir, "screen.png")
            cpath = os.path.join(self.work_dir, "last.png")

            with self.dom.screen_lock:
                proto.save_screen(fpath)
                proto.save_screen(cpath)

                self.dom.screen = proto.screen.copy()
                self.dom.screen_id = counter
                self.dom.screen_path = fpath

            self.emit('SCREEN_COUNTER', counter)
            self.emit('SCREEN_DIR', screendir)
            self.emit('SCREEN_STORED', fpath)
            self.emit('SCREEN_CURRENT', cpath)

            if self.ocr_enabled:
                self.vision.process_screen(fpath)

            self.emit('SCHEDULE_SAVE_DELAY', CAP_DELAY)
            reactor.callLater(CAP_DELAY, self.schedule_save, proto, counter + 1)

    @trace
    def schedule_save(self, proto, counter):
        self.emit('SCHEDULE_SAVE')

        proto.deferred = Deferred()
        proto.deferred.addCallback(self.save_screen, counter)

    @trace
    def start_interpret(self):
        self.emit('START_INTERPRET')

        def interpret_emit(frame):
            self.emit('INTERPRET_LINE', frame.f_lineno)

        with open('pseudo.py') as f:
            code = f.read()

        self.int = interpret.Interpret(self.dom, interpret_emit)
        reactor.callInThread(self.int.start, code)

    @trace
    def stop(self):
        # stop bdb interpreter
        if self.int:
            self.int.set_quit()

        self.emit('STOP_INTERPRET')


application = service.Application("PLLM")
app = Pllm(application)
# yield so logging and twistd stuff can be initialized
reactor.callLater(0.1, app.main)
reactor.addSystemEventTrigger('before', 'shutdown', app.stop)
