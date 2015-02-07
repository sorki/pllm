import os
import random

import libvirt
from lxml import etree
from twisted.python import log

import util
import domains


def handler(ctxt, err):
    global errno
    errno = err

libvirt.registerErrorHandler(handler, 'pllm')


# taken from virtinst/_util.py (python-virtinst), GPLv2+
def fetch_all_guests(conn):
    """
    Return 2 lists: ([all_running_vms], [all_nonrunning_vms])
    """
    active = []
    inactive = []

    # Get all active VMs
    ids = conn.listDomainsID()
    for i in ids:
        try:
            vm = conn.lookupByID(i)
            active.append(vm)
        except libvirt.libvirtError:
            # guest probably in process of dieing
            log.msg("Failed to lookup active domain id #{0}".format(i))

    # Get all inactive VMs
    names = conn.listDefinedDomains()
    for name in names:
        try:
            vm = conn.lookupByName(name)
            inactive.append(vm)
        except:
            # guest probably in process of dieing
            log.msg("Failed to lookup inactive domain {0}".format(name))

    return (active, inactive)


def random_mac():
    return ':'.join(
        ['{:0>2x}'.format(x) for x in
            [0x52, 0x54, 0x00,
             random.randint(0x00, 0xff),
             random.randint(0x00, 0xff),
             random.randint(0x00, 0xff)]
         ])


def get_xpath(xml, xpath):
    tree = etree.fromstring(xml)
    return tree.xpath(xpath)[0]


class LibvirtBackend(object):
    def __init__(self, libvirt_target=None, storage_pool='default'):
        self.con = libvirt.open(libvirt_target)
        self.pool = self.con.storagePoolLookupByName(storage_pool)

        self.pool_path = get_xpath(self.pool.XMLDesc(0),
                                   '/pool/target/path/text()')

        self.pool_type = get_xpath(self.pool.XMLDesc(0),
                                   '/pool/@type')

    def create_volume(self, name, typ, size, path):

        root = etree.Element('volume')
        name_tag = etree.Element('name')
        name_tag.text = name
        root.append(name_tag)

        for tag in ['capacity', 'allocation']:
            size_tag = etree.Element(tag)
            size_tag.text = str(size)
            size_tag.attrib['unit'] = 'bytes'
            root.append(size_tag)

        target_tag = etree.Element('target')
        path_tag = etree.Element('path')
        path_tag.text = path
        target_tag.append(path_tag)
        root.append(target_tag)

        vol = self.pool.createXML(etree.tostring(root))
        return vol

    def volume_path(self, name):
        return os.path.join(self.pool_path, name)

    def get_volume(self, name, typ, size, force_recreate=False):
        vol = None
        volpath = self.volume_path(name)
        log.msg('Looking for volume with path: {0}'.format(volpath))
        try:
            vol = self.con.storageVolLookupByPath(volpath)
            log.msg('Existing volume found')
        except libvirt.libvirtError:
            log.msg('Existing volume not found')

        def recreate(vol):
            if vol:
                vol.delete(0)

            self.create_volume(name, typ, size, volpath)

        if vol:
            orig_typ, cap, alloc = vol.info()
            if cap != size:
                log.msg('Volume capacity mismatch, recreating')
                recreate(vol)

            if force_recreate:
                log.msg('Force recreate in effect')
                recreate(vol)
        else:
            recreate(vol)

        return volpath

    def gen_volume_name(self, ident):
        current_volumes = self.pool.listVolumes()

        num = 0
        while True:
            name = 'pllm_{0}_{1}'.format(ident, num)
            if name not in current_volumes:
                return name
            num += 1

    def instance_name(self, ident):
        return 'pllm_{0}'.format(ident)

    def remove_test_vm(self, ident):
        '''
        Deletes both domain and volumes matching ident.
        '''

        name = self.instance_name(ident)
        log.msg('Cleanup for {0} initiated'.format(name))

        dom = None
        try:
            dom = self.con.lookupByName(name)
        except libvirt.libvirtError:
            log.msg('Existing domain not found')

        if dom:
            log.msg('Domain already defined')
            domain = self.con.lookupByName(name)
            util.destroy_libvirt_domain(domain)
            domain.undefine()
            log.msg('Domain undefined')

        vols = filter(lambda x: x.startswith(name), self.pool.listVolumes())
        for vol in vols:
            volpath = self.volume_path(vol)
            log.msg('Looking for {0}'.format(volpath))
            lvvol = self.con.storageVolLookupByPath(volpath)
            log.msg('Deleting volume {0}'.format(volpath))
            ret = lvvol.delete(libvirt.VIR_STORAGE_VOL_DELETE_NORMAL)
            if ret != 0:
                log.msg('Unable to delete volume {0}'.format(volpath))

    def create_test_vm(self, xml, ident, media_path):
        name = self.instance_name(ident)

        tree = etree.fromstring(xml)
        # handle name & uuid
        dname = tree.xpath('/domain/name')[0]
        dname.text = name

        # handle disks
        disk_sources = tree.xpath('/domain/devices/disk[@device="disk"]/source')
        for source in disk_sources:
            if 'PLACEHOLDER' in source.attrib['dev']:
                log.msg('Found disk placeholder, processing')
                gigs = 5
                if '_' in source.attrib['dev']:
                    gigs = int(
                        source.attrib['dev'].split('_')[1].replace('G', ''))
                    log.msg('Custom volume size: {0}'.format(gigs))

                size = gigs * 1024 ** 3

                volname = self.gen_volume_name(ident)
                path = self.get_volume(volname, self.pool_type, size)
                log.msg('New volume: {0}'.format(path))
                source.attrib['dev'] = path

        # handle CDrom
        media_sources = tree.xpath(
            '/domain/devices/disk[@device="cdrom"]/source')
        for source in media_sources:
            if source.attrib['file'] == 'PLACEHOLDER':
                source.attrib['file'] = media_path

        # handle mac address
        used_macs = util.get_host_macs()

        active, inactive = fetch_all_guests(self.con)
        for domain in active + inactive:
            used_macs.append(
                get_xpath(domain.XMLDesc(0),
                          '/domain/devices/interface/mac/@address'))

        macs = tree.xpath('/domain/devices/interface/mac')
        for mac in macs:
            while True:
                new_mac = random_mac()
                if new_mac not in used_macs:
                    mac.attrib['address'] = new_mac
                    log.msg('Setting mac address to {0}'.format(new_mac))
                    break

        newxml = etree.tostring(tree)
        lvdom = self.con.defineXML(newxml)
        return domains.LibvirtDomain(ident, lvdom)

    def reuse_test_vm(self, ident):
        '''
        Reuse existing machine
        '''

        name = self.instance_name(ident)

        try:
            lvdom = self.con.lookupByName(name)
            log.msg('Reusing existing domain')
            return domains.LibvirtDomain(ident, lvdom)
        except libvirt.libvirtError:
            log.msg('Existing domain not found, recreating')
            return self.create_test_vm(ident)
