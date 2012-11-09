#!/usr/bin/env python

import time
import logging
from pllm import backends, process, config

TRESHOLD = 0.8

def main():
    # load cfg
    logging.basicConfig(level=logging.DEBUG)

    # init libvirt connection
    lv = backends.LibvirtBackend('qemu:///system')

    with open('data/f18.xml') as f:
        xml = f.read()

    lv.remove_test_vm('f18')
    dom = lv.create_test_vm(xml, 'f18',
        '/var/lib/libvirt/images/Fedora-18-Beta-TC4-x86_64-DVD.iso')

    dom.start()
    time.sleep(.5)

    print dom.send_cmd('info mice')

    def click(dom):
        lv.send_cmd(dom, 'mouse_button 1')
        time.sleep(.01)
        lv.send_cmd(dom, 'mouse_button 0')

    def move(dom, x, y):
        lv.send_cmd(dom, 'mouse_move %d %d' % (x, y))

    import cv
    cv.NamedWindow('master')
    cx, cy = -1,-1

    def mousecb(event, x, y, flags, img):
        if event == cv.CV_EVENT_LBUTTONDOWN:
            logging.debug('Click ({0},{1})'.format(x,y))
            logging.debug('Size ({0},{1})'.format(img.width, img.height))
            dom.click(x, y, img.width, img.height)

    class automata(object):
        def __init__(self, dom, stage = 'boot'):
            self.dom = dom
            self.stage = stage

        def test_grub(self, image):
            res, x, y = process.match(image, cv.LoadImage('img/grub_autoboot_label.png'))
            if res >= TRESHOLD:
                self.stage = 'grub'

        def test_anaconda(self, image):
            res, x, y = process.match(image, cv.LoadImage('img/anaconda_welcome.png'))
            if res >= TRESHOLD:
                # minor bug preventing correct first click
                dom.click(0,0)
                self.stage = 'anaconda'

        def run(self, image):
            logging.debug('Current stage: {0}'.format(self.stage))
            if self.stage == 'boot':
                self.test_grub(image)

            if self.stage == 'grub':
                self.dom.send_key('ret')
                self.test_anaconda(image)

            if self.stage == 'anaconda':
                res, x, y = process.match(image,
                    cv.LoadImage('img/anaconda_eng_lang.png'))
                if res >= TRESHOLD:
                    self.dom.click(x,y)

    #wat = automata(dom)

    c = 0
    import threading
    class ScreenThread(threading.Thread):
        def __init__(self, dom, interval=1000):
            super(ScreenThread, self).__init__()
            self.dom = dom
            self.target = config.get('screenshot_target')
            self.interval = interval
            self.running = False

        def run(self):
            while True:
                if not self.running:
                    return

                dom.screen_lock.acquire()
                dom.screen = dom.cv_image()
                cv.ShowImage('master', dom.screen)
                cv.SaveImage('{0}/{1}.png'.format(self.target, dom.screen_id),
                    dom.screen)
                dom.screen_id += 1
                dom.screen_lock.release()
                cv.WaitKey(self.interval)

        def start(self):
            self.running = True
            super(ScreenThread, self).start()

        def stop(self):
            self.running = False

    sct = ScreenThread(dom)
    sct.start()
    time.sleep(1)

    #import IPython
    #IPython.embed()
    import pseudo

    try:
        while True:
            logging.debug('f18')
            pseudo.f18(dom)
            time.sleep(2)
    except KeyboardInterrupt:
        pass
    #cv.SetMouseCallback('master', mousecb, shot)

    sct.stop()

    # create VM
    # init monitoring

if __name__ == "__main__":
    main()
