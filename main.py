#!/usr/bin/env python

import time
import logging
from pllm import backends, config

def main():
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

    import cv
    cv.NamedWindow('master')

    def mousecb(event, x, y, flags, img):
        if event == cv.CV_EVENT_LBUTTONDOWN:
            logging.debug('Click ({0},{1})'.format(x,y))
            logging.debug('Size ({0},{1})'.format(img.width, img.height))
            dom.click(x, y, img.width, img.height)

    import threading
    class ScreenThread(threading.Thread):
        def __init__(self, dom, interval=3000):
            super(ScreenThread, self).__init__()
            self.dom = dom
            self.target = config.get('screenshot_target')
            self.interval = interval
            self.running = False

            self.distinct = True

        def compare(self, im1, im2):
            if type(im1) != type(im2):
                return False

            if im1.width != im2.width or im1.height != im2.height:
                return False

            dst = cv.CreateImage((im1.width, im2.height), cv.IPL_DEPTH_8U, 1)
            #cv.Zero(dst)
            cv.Cmp(im1, im2, dst, cv.CV_CMP_NE)
            logging.debug('WAT {0}'.format(cv.CountNonZero(dst)))
            return dst

        def run(self):
            while True:
                if not self.running:
                    return

                dom.screen_lock.acquire()
                dom.screen_id += 1
                dom.screen = dom.cv_image()
                cv.ShowImage('master', dom.screen)
                cv.SaveImage('{0}/{1}.png'.format(self.target, dom.screen_id),
                    dom.screen)
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
            time.sleep(.2)
    except KeyboardInterrupt:
        pass
    #cv.SetMouseCallback('master', mousecb, shot)

    sct.stop()

if __name__ == "__main__":
    main()
