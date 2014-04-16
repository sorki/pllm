import os
import time
import logging
import threading

import cv
import libvirt
import libvirt_qemu

import util

class Domain(object):
    def __init__(self):
        self.screen = None
        self.screen_id = 0
        self.screen_lock = threading.RLock()

    def start(self):
        raise NotImplementedError

    def stop(self):
        raise NotImplementedError

    def restart(self):
        self.stop()
        self.start()

    def send_keys(self, keys):
        for key in keys:
            self.send_key(key)
            #time.sleep(1)

    def cv_image(self):
        ''' iplimage '''
        raise NotImplementedError

    def screenshot(self):
        with self.screen_lock:
            cvim = None
            while cvim is None:
                time.sleep(0.1)
                cvim = self.cv_image()

            self.screen_id += 1
            self.screen = cvim

    def click(self, x, y):
        raise NotImplementedError

    def send_key(self, key):
        raise NotImplementedError

class LibvirtDomain(Domain):
    def __init__(self, con, ident, dom):
        super(LibvirtDomain, self).__init__()
        self.con = con
        self.ident = ident
        self.dom = dom

    def send_cmd(self, cmd):
        logging.debug('Sending qemu monitor command {0}'.format(cmd))
        # handle reconnects!
        try:
            ret = libvirt_qemu.qemuMonitorCommand(self.dom, cmd,
                libvirt_qemu.VIR_DOMAIN_QEMU_MONITOR_COMMAND_HMP)
        except libvirt.libvirtError:
            logging.debug('libvirtError caught, retrying in 2 seconds')
            time.sleep(2)
            self.dom = self.con.lookupByUUIDString(self.dom.UUIDString())
            return self.send_cmd(cmd)

        if ret:
            logging.debug('Result {0}'.format(ret))
        return ret

    def start(self):
        logging.debug('Creating domain')
        self.dom.create()

    def stop(self):
        util.destroy_libvirt_domain(self.dom)

    def is_running(self):
        return self.dom.info()[0] == libvirt.VIR_DOMAIN_RUNNING

    def cv_image(self):
        fname = '/tmp/pllm_{0}_{1}.ppm'.format(self.ident, self.screen_id)
        try:
            self.send_cmd('screendump {0}'.format(fname))
            img = cv.LoadImage(fname)
        except IOError:
            logging.debug('No screen dumped, retrying in 2 seconds')
            return self.cv_image()
        # FIXME
        #os.unlink(fname)
        return img

    def click(self, x, y, screen_width=1024, screen_height=768):
        cx = x * 0x7fff / screen_width
        cy = y * 0x7fff / screen_height
        self.send_cmd('mouse_move {0} {1}'.format(cx, cy))
        time.sleep(.5)
        self.send_cmd('mouse_button 1')
        time.sleep(1)
        self.send_cmd('mouse_button 0')
        time.sleep(.3)

    def send_key(self, key):
        self.send_cmd('sendkey {0}'.format(key))
        time.sleep(.1)
