import time
import logging

from pllm import process, config, util

class screenlock(object):
    def __init__(self, func):
        self.func = func

    def __call__(self, dom, template):
        dom.screen_lock.acquire()
        res = self.func(dom, template)
        dom.screen_lock.release()
        return res

class cachefind(object):
    def __init__(self, func):
        self.func = func
        self.last_screen_id = -1
        self.cache = {}

    def __call__(self, dom, template):
        if self.last_screen_id != dom.screen_id:
            self.cache = {}
            self.last_screen_id = dom.screen_id

        if template in self.cache:
            res = self.cache[template]
        else:
            res = self.func(dom, template)
            self.cache[template] = res

        return res

@screenlock
@cachefind
def find(dom, template):
    res, x, y = process.match(dom.screen, util.load_img(template))
    if res > config.get('treshold'):
        logging.debug('+{0}@{1} = {2}'.format(template, dom.screen_id, res))
        ret = True
    else:
        logging.debug('-{0}@{1} = {2}'.format(template, dom.screen_id, res))
        ret = False

    return ret

@screenlock
@cachefind
def findxy(dom, template):
    res, x, y = process.match(dom.screen, util.load_img(template))
    if res > config.get('treshold'):
        logging.debug('+{0}@{1} = {2}'.format(template, dom.screen_id, res))
        ret = True
    else:
        logging.debug('-{0}@{1} = {2}'.format(template, dom.screen_id, res))
        ret = False

    return (ret, x, y)

def expect(dom, items):
    for stage_name, template, callback in items:
        logging.debug('Testing stage {0}'.format(stage_name))
        if find(dom, template):
            logging.debug('Stage {0} found'.format(stage_name))
            callback(dom)

def click(dom, template):
    logging.debug('Looking for click target')
    ret, x ,y = findxy(dom, template)

    if ret:
        dom.click(x, y)
    else:
        logging.debug('Click target not found')

    time.sleep(0.5)

def wait(dom, template, timeout_seconds=20):
    start = time.time()
    logging.debug('Waiting for target for {0} sec'.format(timeout_seconds))
    while True:
        if find(dom, template):
            logging.debug('Wait target found after {:.2} sec'.format(
                time.time() - start))
            return True

        time.sleep(0.1)

        if time.time() > start + timeout_seconds:
            logging.debug('!! Timeout on wait')
            return False

def waitclick(dom, template):
    wait(dom, template)
    click(dom, template)

def grub(dom):
    dom.send_key('ret')

def anaconda(dom):
    time.sleep(1)
    click(dom, 'anaconda_continue')
    wait(dom, 'anaconda_my_fate', 6)
    if find(dom, 'anaconda_eng_lang'):
        logging.warning('First click glitch present (Found eng lang)')
        click(dom, 'anaconda_eng_lang')
        click(dom, 'anaconda_continue')

    waitclick(dom, 'anaconda_my_fate')
    waitclick(dom, 'anaconda_storage_btn')
    waitclick(dom, 'anaconda_continue')
    waitclick(dom, 'anaconda_dialog_continue')

    waitclick(dom, 'anaconda_software_selection_btn')
    #waitclick(dom, 'anaconda_xfce_choice')
    waitclick(dom, 'anaconda_done_btn')

    waitclick(dom, 'anaconda_begin_btn')
    waitclick(dom, 'anaconda_bluekey_img')
    wait(dom, 'anaconda_done_btn')
    for _ in [1,2]:
        for i in range(6):
            dom.send_key(str(i))

        dom.send_key('tab')

    click(dom, 'anaconda_done_btn')
    waitclick(dom, 'anaconda_done_btn')
    wait(dom, 'anaconda_reboot_btn', 3600)
    click(dom, 'anaconda_reboot_btn')

    logging.debug('Waiting for domain to shutdown')
    while dom.is_running():
        logging.debug('.')
        time.sleep(1)

    print dom.is_running()
    time.sleep(1)
    logging.debug('Starting again')
    print dom.is_running()
    dom.start()

def write(dom, text):
    for letter in text:
        dom.send_key(letter)

def firstboot(dom):
    waitclick(dom, 'firstboot_forward_btn')
    waitclick(dom, 'firstboot_forward_btn') # glitch
    waitclick(dom, 'firstboot_forward_btn') # license
    wait(dom, 'firstboot_create_user_label')
    write(dom, 'pllm framework')
    dom.send_key('tab')
    write(dom, 'pllm')
    dom.send_key('tab')
    dom.send_key('tab')
    write(dom, 'a')
    dom.send_key('tab')
    write(dom, 'a')
    waitclick(dom, 'firstboot_forward_btn')
    waitclick(dom, 'firstboot_finish_btn')

def f18(dom):
    expect(dom, [
        ('grub', 'grub_autoboot_label', grub),
        ('anaconda', 'anaconda_installation_label', anaconda),
        ('firstboot', 'firstboot_welcome_label', firstboot),
        ])

try:
    while True:
        logging.debug('f18')
        f18(dom)
        time.sleep(.2)
except KeyboardInterrupt:
    pass
