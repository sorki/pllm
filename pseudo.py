import time

from pllm.vision.tasks import template_match

PASSWORD = "1337password_is_leet!!!"

# useless
TIMEOUT = 60000


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
def find(dom, template_name):
    res, x, y = template_match(dom.screen_path, template_name)
    if res:
        print('+{0}@{1} = {2}'.format(template_name, dom.screen_id, res))
        ret = True
    else:
        print('-{0}@{1} = {2}'.format(template_name, dom.screen_id, res))
        ret = False

    return ret


@screenlock
@cachefind
def findxy(dom, template_name):
    res, x, y = template_match(dom.screen_path, template_name)
    if res:
        print('+{0}@{1} = {2}'.format(template_name, dom.screen_id, res))
        ret = True
    else:
        print('-{0}@{1} = {2}'.format(template_name, dom.screen_id, res))
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


def click_segment(dom, text, exact=False):
    print('Looking for segment with text "{0}"'.format(text))

    for segname, data in dom.segments.items():
        rect, ocrd = data
        x, y, w, h = rect

        found = False

        if exact:
            if text == ocrd:
                found = True
        else:
            if text.lower() in ocrd.lower():
                found = True

        if found:
            print('Found target at {0}x{1}'.format(x, y))
            dom.clickxy(x + w / 2, y + h / 2)
            return True

    print('Click target not found')


def wait(dom, template, timeout_seconds=TIMEOUT):
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


def wait_segment(dom, text, exact=False, timeout_seconds=TIMEOUT):
    start = time.time()
    print('Waiting segment with text "{0}"'.format(text))

    while True:
        for segname, data in dom.segments.items():
            rect, ocrd = data
            x, y, w, h = rect
            found = False

            if exact:
                if text == ocrd:
                    found = True
            else:
                if text.lower() in ocrd.lower():
                    found = True

            if found:
                print('Wait target found at segment {0}x{1} after {2:.2f} sec'
                     .format(x, y, time.time() - start))
                return True

        time.sleep(0.1)

        if time.time() > start + timeout_seconds:
            print('!! Timeout on wait')
            return False


def wait_text(dom, text, timeout_seconds=TIMEOUT):
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


def wait_next(dom, timeout_seconds=TIMEOUT):
    start = time.time()
    print('Waiting for next screen for {0} sec'.format(timeout_seconds))
    last = dom.screen_id
    while last == dom.screen_id:
        time.sleep(0.1)

        if time.time() > start + timeout_seconds:
            print('!! Timeout on wait_next')
            return False

    return True


def wait_click(dom, template):
    wait(dom, template)
    click(dom, template)


def wait_click_text(dom, text, exact=False):
    wait_segment(dom, text, exact)
    click_segment(dom, text, exact)


def grub(dom):
    dom.key_press('tab')
    # erase part of cmdline
    for _ in "rd.live.check quiet":
        dom.key_press('backspace')
        time.sleep(0.2)

    # disable gelocation so we don't start with random language
    dom.write(' geoloc=0')
    wait_next(dom)
    dom.key_press('ret')


def anaconda(dom):
    dom.mouse_move(1,1)

    wait_click_text(dom, 'continue')
    if not wait_text(dom, 'installation summary'):
        print('First click glitch present')
        wait_click_text(dom, 'continue')

    wait_text(dom, 'installation summary')

    while True:
        wait_click(dom, 'anaconda_storage_incomplete_btn')
        if wait_text(dom, 'local standard disks'):
            break

    wait_click_text(dom, 'I will configure partitioning')
    wait_click_text(dom, 'done')

    def create_partition(mount, size):
        wait_click(dom, 'anaconda_partitioning_plus_btn')
        wait_text(dom, 'add a new mount point')

        dom.write(mount)
        dom.key_press('right')
        dom.key_press('tab')
        dom.key_press('tab')
        dom.write(size)

        wait_click_text(dom, 'add mount point')

    create_partition('/', '5G')
    create_partition('/boot', '200M')
    create_partition('swap', '1G')
    create_partition('/home', '')

    wait_click_text(dom, 'done')
    wait_click_text(dom, 'accept changes')

    wait_click(dom, 'anaconda_software_btn')
    #wait_click(dom, 'anaconda_xfce_choice')
    wait_click_text(dom, 'done')
    wait_click_text(dom, 'begin installation')

    wait_click_text(dom, 'root password')
    wait_segment(dom, 'done')
    for _ in [1, 2]:
        dom.write(PASSWORD)
        dom.key_press('tab')

    wait_click_text(dom, 'done')

    time.sleep(2)
    print(dom.text)

    wait_click_text(dom, 'user creation')
    wait_segment(dom, 'done')

    dom.write('bob')

    for _ in range(4):
        dom.key_press('tab')
        time.sleep(0.2)

    for _ in [1, 2]:
        dom.write(PASSWORD)
        dom.key_press('tab')

    wait_click_text(dom, 'done')

    wait_next(dom)
    print(dom.text)

    print('Waiting for configuration to finish')
    wait_click_text(dom, 'Reboot', exact=True)

    print('Waiting for domain to shutdown')
    while dom.is_running():
        print('.')
        time.sleep(1)

    print dom.is_running()
    time.sleep(1)
    print('Starting again')
    print dom.is_running()
    dom.start()

def f21(dom):
    expect(dom, [
        ('grub', 'grub_autoboot_label', grub),
    ])

    expect_text(dom, [
        ('anaconda', 'welcome to fedora', anaconda)
    ])

try:
    while True:
        print('f21')
        f21(dom)
        time.sleep(1)
except KeyboardInterrupt:
    pass
