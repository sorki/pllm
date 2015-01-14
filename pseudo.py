import time

from pllm import vision, config, util


class screenlock(object):
    def __init__(self, func):
        self.func = func

    def __call__(self, dom, template):
        with dom.screen_lock:
            res = self.func(dom, template)
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
    res, x, y = vision.template_match(dom.screen, util.load_img(template))
    if res > config.get('treshold'):
        print('+{0}@{1} = {2}'.format(template, dom.screen_id, res))
        ret = True
    else:
        print('-{0}@{1} = {2}'.format(template, dom.screen_id, res))
        ret = False

    return ret


@screenlock
@cachefind
def findxy(dom, template):
    res, x, y = vision.template_match(dom.screen, util.load_img(template))
    if res > config.get('treshold'):
        print('+{0}@{1} = {2}'.format(template, dom.screen_id, res))
        ret = True
    else:
        print('-{0}@{1} = {2}'.format(template, dom.screen_id, res))
        ret = False

    return (ret, x, y)


def expect(dom, items):
    for stage_name, template, callback in items:
        print('Testing stage {0}'.format(stage_name))
        if find(dom, template):
            print('Stage "{0}" found'.format(stage_name))
            callback(dom)


def expect_text(dom, items):
    for stage_name, text, callback in items:
        print('Testing text presence "{0}" for stage "{1}"'
              .format(text, stage_name))

        if text.lower() in dom.text.lower():
            print('Stage "{0}" found'.format(stage_name))
            callback(dom)


def click(dom, template):
    print('Looking for click target')
    ret, x, y = findxy(dom, template)

    if ret:
        dom.clickxy(x, y)
    else:
        print('Click target not found')

    time.sleep(0.5)


def click_text(dom, text):
    print('Looking for click target with text "{0}"'.format(text))

    for segname, data in dom.segments.items():
        rect, ocrd = data
        x, y, w, h = rect

        if text.lower() in ocrd.lower():
            print('Found target at {0}x{1}'.format(x, y))
            dom.clickxy(x + w / 2, y + h / 2)
            return

    print('Click target not found')


def wait(dom, template, timeout_seconds=30):
    start = time.time()
    print('Waiting for target for {0} sec'.format(timeout_seconds))
    while True:
        if find(dom, template):
            print('Wait target found after {0:.2f} sec'.format(
                time.time() - start))
            return True

        time.sleep(0.1)

        if time.time() > start + timeout_seconds:
            print('!! Timeout on wait')
            return False


def wait_text(dom, text, timeout_seconds=30):
    start = time.time()
    print('Waiting for "{0}" text for {1} sec'.format(text, timeout_seconds))

    while True:
        if text.lower() in dom.text.lower():
            print('Wait target found after {0:.2f} sec'.format(
                time.time() - start))
            return True

        # check segments
        for segname, data in dom.segments.items():
            rect, ocrd = data
            x, y, w, h = rect

            if text.lower() in ocrd.lower():
                print('Wait target found at segment {0}x{1} after{2:.2f} sec'
                      .format(x, y, time.time() - start))
                return True

        time.sleep(0.1)

        if time.time() > start + timeout_seconds:
            print('!! Timeout on wait')
            return False


def wait_click(dom, template):
    wait(dom, template)
    click(dom, template)


def wait_click_text(dom, text):
    wait_text(dom, text)
    click_text(dom, text)


def grub(dom):
    dom.key_press('tab')
    # erase part of cmdline
    for _ in "rd.live.check quiet":
        dom.key_press('backspace')
        time.sleep(0.2)

    # disable gelocation so we don't start with random language
    dom.write(' geoloc=0')
    time.sleep(2)  # screenshot
    dom.key_press('ret')


def anaconda(dom):
    # first click glitch, but why?
    dom.mouse_move(1, 1)
    #dom.click()

    click_text(dom, 'continue')
    if not wait_text(dom, 'installation summary', 5):
        print('First click glitch present')
        click_text(dom, 'continue')

    wait_text(dom, 'installation summary')

    while True:
        wait_click(dom, 'anaconda_storage_incomplete_btn')
        if wait_text(dom, 'local standard disks'):
            break

    wait_click_text(dom, 'done')
    wait_text(dom, 'installation options')
    dom.key_press('alt-m')
    wait_click_text(dom, 'continue')

    def create_partition(mount, size):
        wait_text(dom, 'manual partitioning')

        while not wait_text(dom, 'add a new mount point', 2):
            wait_click(dom, 'anaconda_partitioning_plus_btn')

        dom.write(mount)
        dom.key_press('right')
        dom.key_press('tab')
        dom.key_press('tab')
        dom.write(size)

        while not wait_text(dom, 'manual partitioning', 2):
            wait_click_text(dom, 'add mount point')

    create_partition('/', '5G')
    create_partition('/boot', '100M')
    create_partition('/home', '1G')

    wait_click_text(dom, 'done')
    wait_click_text(dom, 'accept changes')

    wait_click(dom, 'anaconda_software_btn')
    #wait_click(dom, 'anaconda_xfce_choice')
    wait_click_text(dom, 'done')
    wait_click_text(dom, 'begin installation')

    wait_click(dom, 'anaconda_rootpw_btn')
    wait_text(dom, 'root password')
    for _ in [1, 2]:
        for i in range(6):
            dom.key_press(str(i))

        dom.key_down('tab')

    # password too simple, need to click two times
    wait_click_text(dom, 'done')
    wait_click_text(dom, 'done')

    time.sleep(2)
    print(dom.text)

    wait_click(dom, 'anaconda_user_creation_btn')
    wait_click_text(dom, 'done')

    time.sleep(2)
    print(dom.text)

    print('Waiting for installation to finish')
    while True:
        wait_click_text(dom, 'reboot')

    print('Waiting for domain to shutdown')
    while dom.is_running():
        print('.')
        time.sleep(1)

    print dom.is_running()
    time.sleep(1)
    print('Starting again')
    print dom.is_running()
    dom.start()


def write(dom, text):
    for letter in text:
        dom.key_down(letter)


def firstboot(dom):
    wait_click(dom, 'firstboot_forward_btn')
    wait_click(dom, 'firstboot_forward_btn')
    wait_click(dom, 'firstboot_forward_btn')
    wait(dom, 'firstboot_create_user_label')
    write(dom, 'pllm framework')
    dom.key_down('tab')
    write(dom, 'pllm')
    dom.key_down('tab')
    dom.key_down('tab')
    write(dom, 'a')
    dom.key_down('tab')
    write(dom, 'a')
    wait_click(dom, 'firstboot_forward_btn')
    wait_click(dom, 'firstboot_finish_btn')


def f20(dom):
    expect(dom, [
        ('grub', 'grub_autoboot_label', grub),
    ])

    expect_text(dom, [
        ('anaconda', 'welcome to fedora', anaconda)
    ])

try:
    while True:
        print('f20')
        f20(dom)
        time.sleep(1)
except KeyboardInterrupt:
    pass
