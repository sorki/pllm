import os
import base64
import cPickle as pickle

import cv2
import libvirt
from twisted.python import log

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

        log.msg('Destroying domain')
        domain.destroy()
    else:
        log.msg('Domain not running')


def template_path(name):
    return '{0}/{1}.png'.format(config.CONFIG['template_dir'], name)


def load_img(name):
    return cv2.imread(template_path(name))


def encdata(data):
    return base64.b64encode(pickle.dumps(data))


def decdata(data):
    return pickle.loads(base64.b64decode(data))


def trace(func):
    def wrapper(*args, **kwargs):
        print('{0}'.format(func.__name__))
        val = func(*args, **kwargs)
        print('/{0}'.format(func.__name__))
        return val
    return wrapper
