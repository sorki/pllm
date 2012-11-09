import os
import logging

import cv
import libvirt

import config

def get_host_macs():
    with os.popen('LC_ALL=C /sbin/ip addr') as f:
        return map(lambda x: x.split()[1],
                filter(lambda x: 'link/ether' in x,
                    f.readlines()))

def destroy_libvirt_domain(domain):
    domain_state = domain.info()[0]
    if domain_state in [
        libvirt.VIR_DOMAIN_RUNNING,
        libvirt.VIR_DOMAIN_PAUSED,
        libvirt.VIR_DOMAIN_PMSUSPENDED]:

        logging.debug('Destroying domain')
        domain.destroy()
    else:
        logging.debug('Domain not running')

def load_img(name):
    return cv.LoadImage('{0}/{1}.png'.format(config.CONFIG['img_dir'], name))
