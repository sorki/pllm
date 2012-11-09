import os
import time
import logging
import threading

import cv
import libvirt
import libvirt_qemu

import util

class Domain(object):
    def __init__(self, con, ident, dom):
        self.con = con
        self.ident = ident
        self.dom = dom
        self.screen = None
        self.screen_id = 0
        self.screen_lock = threading.Lock()

    def start(self):
        raise NotImplemented

    def cv_image(self):
        raise NotImplemented

    def click(self, x, y):
        raise NotImplemented

    def send_key(self, key):
        raise NotImplemented

class LibvirtDomain(Domain):
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
