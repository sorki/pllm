import os
import logging

import libvirt
import virtinst
from lxml import etree

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
            logging.warn("Failed to lookup active domain id %d", i)

    # Get all inactive VMs
    names = conn.listDefinedDomains()
    for name in names:
        try:
            vm = conn.lookupByName(name)
            inactive.append(vm)
        except:
            # guest probably in process of dieing
            logging.warn("Failed to lookup inactive domain %d", name)

    return (active, inactive)

class LibvirtBackend(object):
    def __init__(self, libvirt_target=None, storage_pool='default'):
        self.con = libvirt.open(libvirt_target)
        self.pool = self.con.storagePoolLookupByName(storage_pool)
        self.pool_path = virtinst.util.get_xml_path(self.pool.XMLDesc(0),
            '/pool/target/path/text()')

        self.pool_type = virtinst.util.get_xml_path(self.pool.XMLDesc(0),
            '/pool/@type')

    def create_volume(self, name, typ, size):
        ptypes = virtinst.Storage.StoragePool.get_pool_types()
        if typ not in ptypes:
            raise RuntimeError(
                'Unknown pool type: {0}, available: {1}'.format(typ,
                ', '.join(ptypes)))

        pool_type = virtinst.Storage.StoragePool.get_pool_class(typ)
        vol_type = pool_type.get_volume_class()

        logging.debug('Using volume type: {0}'.format(vol_type))

        volume = vol_type(name, pool=self.pool,
            capacity=size, allocation=size, conn=self.con)

        return volume

    def volume_path(self, name):
        return os.path.join(self.pool_path, name)

    def get_volume(self, name, typ, size, force_recreate=False):
        vol = None
        volpath = self.volume_path(name)
        logging.debug('Looking for volume with path: {0}'.format(volpath))
        try:
            vol = self.con.storageVolLookupByPath(volpath)
            logging.debug('Existing volume found')
        except libvirt.libvirtError as e:
            logging.debug('Existing volume not found')

        def recreate(vol):
            if vol:
                vol.delete(0)

            nvol = self.create_volume(name, typ, size)
            nvol.install()

        if vol:
            orig_typ, cap, alloc = vol.info()
            if cap != size:
                logging.debug('Volume capacity mismatch, recreating')
                recreate(vol)

            if force_recreate:
                logging.debug('Force recreate in effect')
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
        logging.debug('Cleanup for {0} initiated'.format(name))

        dom = None
        try:
            dom = self.con.lookupByName(name)
        except libvirt.libvirtError:
            logging.debug('Existing domain not found')

        if dom:
            logging.debug('Domain already defined')
            domain = self.con.lookupByName(name)
            util.destroy_libvirt_domain(domain)
            domain.undefine()
            logging.debug('Domain undefined')

        vols = filter(lambda x: x.startswith(name), self.pool.listVolumes())
        for vol in vols:
            volpath = self.volume_path(vol)
            logging.debug('Looking for {0}'.format(volpath))
            lvvol = self.con.storageVolLookupByPath(volpath)
            logging.debug('Deleting volume {0}'.format(volpath))
            ret = lvvol.delete(libvirt.VIR_STORAGE_VOL_DELETE_NORMAL)
            if ret != 0:
                logging.error('Unable to delete volume {0}'.format(volpath))

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
                logging.debug('Found disk placeholder, processing')
                gigs = 5
                if '_' in source.attrib['dev']:
                    gigs = int(
                        source.attrib['dev'].split('_')[1].replace('G', ''))
                    logging.debug('Custom volume size: {0}'.format(gigs))

                size = gigs * 1024**3

                volname = self.gen_volume_name(ident)
                path = self.get_volume(volname, self.pool_type, size)
                logging.debug('New volume: {0}'.format(path))
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
        for domain in active+inactive:
            used_macs.append(
                virtinst.util.get_xml_path(domain.XMLDesc(0),
                    '/domain/devices/interface/mac/@address'))

        macs = tree.xpath('/domain/devices/interface/mac')
        for mac in macs:
            while True:
                new_mac = virtinst.util.randomMAC(type='qemu').lower()
                if new_mac not in used_macs:
                    mac.attrib['address'] = new_mac
                    logging.debug('Setting mac address to {0}'.format(new_mac))
                    break

        newxml = etree.tostring(tree)
        lvdom = self.con.defineXML(newxml)
        return domains.LibvirtDomain(self.con, ident, lvdom)
