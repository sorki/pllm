#!/usr/bin/python
import os
import shutil

from twisted.python import log
from twisted.application import service
from twisted.application.internet import TCPClient, TCPServer
from twisted.internet import task
from twisted.internet import reactor, threads
from twisted.internet.defer import Deferred
from twisted.internet.endpoints import TCP4ClientEndpoint, connectProtocol

from pllm import manhole, interpret
from pllm import backends, config, monitor, util
from pllm.vision import process, algo
from pllm.vision.protocol import VisionClientProtocol

from pllm.vnc.vnc import VNCFactory


trace = util.trace

CAP_DELAY = 1.5


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
        f = '/var/lib/libvirt/images/Fedora-Live-Workstation-x86_64-21-5.iso'
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
        vnc_factory.connected_callback = self.vnc_started
        vnc_factory.disconnected_callback = self.vnc_stopped
        vnc_service = TCPClient("localhost", 5900, vnc_factory)
        vnc_service.setServiceParent(self.app)

    @trace
    def vnc_stopped(self):
        self.vnc_loop.stop()

    @trace
    def vnc_started(self, proto):
        self.vnc = proto
        self.dom.transport = proto

        self.vnc_loop = task.LoopingCall(proto.framebufferUpdateRequest)
        self.vnc_loop.start(5.0)
        self.schedule_save(proto)

    @trace
    def start_vision(self):
        port = config.get("vision_pipe_port")
        proto = VisionClientProtocol()
        point = TCP4ClientEndpoint(reactor, "localhost", port)
        d = connectProtocol(point, proto)
        d.addCallback(self.vision_started)

    @trace
    def vision_started(self, protocol):
        self.vision = protocol

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
    def store_ocr_full(self, result, ident):
        log.msg('vis: full result for {0}'.format(ident))
        with self.dom.screen_lock:
            if self.dom.screen_id > ident:
                if not self.dom.allow_outdated_results:
                    log.msg('outdated, discarding')
                    return

            self.dom.text = result

    @trace
    def store_ocr_segments(self, result, ident):
        log.msg('vis: segments result for {0}'.format(ident))
        with self.dom.screen_lock:
            if self.dom.screen_id > ident:
                log.msg('outdated, discarding')
                return

            self.dom.segments = result

    @trace
    def store_ocr_results(self, result, ident):
        log.msg('vis: got result for {0}'.format(ident))
        with self.dom.screen_lock:
            if self.dom.screen_id > ident:
                log.msg('outdated, discarding')
                return

        full, segments = result
        log.msg('ocr: full page text length:{0}, segments:{1}'
                .format(len(full), len(segments)))

        log.msg('ocr: full sample: "{0}..."'.format(repr(full[:30])))

        self.emit('OCR_FULL', full)
        self.emit('OCR_SEGMENTS', segments)

        self.dom.text = full

    @trace
    def save_screen(self, proto):
        with self.dom.screen_lock:
            similar = algo.similar(self.dom.screen, proto.screen)
            if similar:
                self.dom.similar_counter += 1
                if self.dom.similar_counter >= 3:
                    if not self.dom.ocr_enabled:
                        print('Re-enabling ocr')
                        self.dom.ocr_enabled = True
                        self.start_ocr_tasks()

                print('Similar images, skipping')
                self.emit('SIMILAR')
                reactor.callLater(CAP_DELAY, self.schedule_save, proto)
            else:
                self.dom.similar_counter = 0

                self.dom.screen = proto.screen.copy()
                screendir = os.path.join(self.work_dir,
                                         '{0:03d}'.format(self.dom.screen_id))

                if os.path.isdir(screendir):
                    shutil.rmtree(screendir)

                os.mkdir(screendir)

                fpath = os.path.join(screendir, "screen.png")
                cpath = os.path.join(self.work_dir, "last.png")

                proto.save_screen(fpath)
                proto.save_screen(cpath)

                self.dom.screen_id += 1
                self.dom.screen_path = fpath

                self.dom.text = ""
                self.dom.segments = {}

                if self.dom.ocr_enabled:
                    self.start_ocr_tasks()

                self.emit('SCREEN_ID', self.dom.screen_id)
                self.emit('SCREEN_DIR', screendir)
                self.emit('SCREEN_STORED', fpath)
                self.emit('SCREEN_CURRENT', cpath)

                self.emit('SCHEDULE_SAVE_DELAY', CAP_DELAY)

            reactor.callLater(CAP_DELAY, self.schedule_save, proto)

    def start_ocr_tasks(self):
        fpath = self.dom.screen_path
        counter = self.dom.screen_id

        full_task = self.vision.process_task(
            "ocr_full", counter, 0, [fpath])
        full_task.addCallback(self.store_ocr_full, counter)

        segments_task = self.vision.process_task(
            "ocr_segments", counter, 0, [fpath])
        segments_task.addCallback(self.store_ocr_segments, counter)

    #@trace
    def schedule_save(self, proto):
        self.emit('SCHEDULE_SAVE')

        proto.deferred = Deferred()
        proto.deferred.addCallback(self.save_screen)

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
