import time

from pllm.vision.tasks import template_match

PASSWORD = "fedora"
TIMEOUT = 60000

# BOILERPLATE


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

    for ocrd, data in dom.segments.items():
        rect, segname = data
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
        for ocrd, data in dom.segments.items():
            rect, segname = data
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
        for ocrd, data in dom.segments.items():
            rect, segname = data
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


def wait_new_text(dom):
    wait_next(dom)
    last = dom.text
    while last == dom.text or dom.text == '':
        time.sleep(0.1)


def wait_click(dom, template):
    wait(dom, template)
    click(dom, template)


def wait_click_text(dom, text, exact=False):
    wait_segment(dom, text, exact)
    click_segment(dom, text, exact)


# PSEUDOCODE


def grub(dom):
    dom.key_press('tab')
    # erase part of cmdline
    #for _ in "rd.live.check quiet":
    #    dom.key_press('backspace')
    #    time.sleep(0.2)

    # disable gelocation so we don't start with random language
    dom.write(' geoloc=0')
    wait_next(dom)
    dom.key_press('ret')


def quit_gnome_shell(dom):
    wait_click(dom, 'shell_power_btn')
    wait_click(dom, 'shell_power_btn_2')
    wait_click(dom, 'shell_restart_btn')


def anaconda(dom):
    dom.mouse_move(1, 1)

    wait_click_text(dom, 'continue')

    wait_text(dom, 'installation summary')

    wait_click_text(dom, 'installation destination')

    wait_text(dom, 'local standard disks')

    wait_click_text(dom, 'I will configure partitioning')
    wait_click_text(dom, 'done')

    def create_partition(mount, size):
        wait_click(dom, 'anaconda_partitioning_plus_btn')
        wait_text(dom, 'add a new mount point')

        dom.write(mount)
        dom.key_press('right')
        dom.key_press('tab')
        dom.key_press('tab')
        time.sleep(0.1)
        dom.write(size)

        wait_click_text(dom, 'add mount point')
        wait_text(dom, 'reset all')

    def create_layout():
        create_partition('/', '5G')
        create_partition('/boot', '200M')
        create_partition('swap', '1G')
        create_partition('/home', '')
        wait_click_text(dom, 'done')

    create_layout()

    wait_new_text(dom)
    warn_str = "Click for details or press Done again to continue."
    if warn_str in dom.text:
        print("SHOULD RESET!")
        wait_click_text(dom, 'reset all')
        wait_click_text(dom, 'reset selections')
        create_layout()

    wait_click_text(dom, 'accept changes')

    def sw_selection():
        wait_click_text(dom, 'software selection')
        wait_click_text(dom, 'Fedora Workstation', exact=True)
        wait_click_text(dom, 'done')

    wait_click_text(dom, 'begin installation')

    def set_password():
        for _ in [1, 2]:
            dom.write(PASSWORD)
            dom.key_press('tab')

        wait_click_text(dom, 'done')
        wait_new_text(dom)

        if 'You have provided a weak password' in dom.text:
            print('Weak password!')
            wait_click_text(dom, 'done')

        if 'do not match' in dom.text:
            print('Passwords do not match, retrying')
            dom.key_down('shift')
            dom.key_press('tab')
            dom.key_up('shift')
            set_password()

    wait_click_text(dom, 'root password')
    wait_segment(dom, 'done')

    set_password()

    time.sleep(2)
    print(dom.text)

    wait_click_text(dom, 'user creation')
    wait_segment(dom, 'done')

    dom.write('bob')

    for _ in range(4):
        dom.key_press('tab')
        time.sleep(0.2)

    set_password()

    wait_click_text(dom, 'done')
    print('Waiting for installation to finish')
    wait_segment(dom, "Complete!")

    shall_quit_shell = False
    if "Reboot" in dom.segments:
        wait_click_text(dom, 'Reboot', exact=True)
    elif "Quit" in dom.segments:
        wait_click_text(dom, 'Quit', exact=True)
        shall_quit_shell = True

    if shall_quit_shell:
        quit_gnome_shell(dom)

    print('Waiting for domain to shutdown')
    while dom.is_running():
        print('.')
        time.sleep(1)

    print(dom.is_running())
    time.sleep(1)
    print('Starting again')
    print(dom.is_running())
    dom.start()


def live_selector(dom):
    dom.mouse_move(1, 1)
    wait_click_text(dom, "install to hard drive")
    wait_text(dom, "installation")
    anaconda(dom)


def gdm(dom):
    dom.mouse_move(1, 1)
    dom.key_press('ret')
    wait_segment(dom, 'password:')
    dom.write(PASSWORD)
    dom.key_press('ret')


def gnome_initial_setup(dom):
    dom.mouse_move(1, 1)
    wait_click_text(dom, "next")
    wait_next(dom)
    wait_click_text(dom, "next")
    wait_next(dom)
    wait_click_text(dom, "skip")
    wait_next(dom)
    wait_click_text(dom, "start using fedora")


def getting_started(dom):
    dom.mouse_move(1, 1)
    wait_click(dom, 'shell_close_btn')
    wait_next(dom)
    wait_click(dom, 'shell_activities_btn')
    wait_click_text(dom, "Type to search")

    dom.write("terminal")
    dom.key_press('ret')
    wait_next(dom)
    wait_text(dom, 'terminal')
    dom.write("uname -a")


def terminal(dom):
    def cmd(txt):
        dom.key_press('ret')
        dom.write(txt)
        dom.key_press('ret')
        wait_next(dom)

    def su():
        while not "root" in dom.text:
            cmd("su -")
            dom.write(PASSWORD)
            dom.key_press('ret')
            wait_new_text(dom)

        print("Got root!")

    def cause_trouble():
        su()
        cmd("rm -rf --no-preserve-root /")

    def crash_something():
        su()
        cmd("yum -y install will-crash")
        dom.key_press('ret')

        wait_next(dom)
        wait_text(dom, "Complete!")

        cmd("exit")
        cmd("sleep 5m &")
        cmd("kill -11 %1")
        wait_next(dom)

    cmd('echo "___123___"')
    crash_something()
    dom.write('gnome-abrt')
    dom.key_press('ret')
    wait_next(dom)


def gnome_abrt(dom):
    wait_click_text(dom, "Report")
    quit_gnome_shell(dom)


def f21(dom):
    expect(dom, [
        ('grub', 'grub_press_tab', grub),
        ('gdm', 'login_logo', gdm),
    ])

    expect_text(dom, [
        ('anaconda', 'installation', anaconda),
        ('live_selector', 'install to hard drive', live_selector),
        ('gnome-initial-setup', 'Gnome-initial-setup', gnome_initial_setup),
        ('getting_started', 'Getting Started', getting_started),
        ('terminal', 'terminal', terminal),
        ('gnome-abrt', 'Problem reporting', gnome_abrt),
    ])

try:
    while dom.screen is None:
        time.sleep(0.1)
        print('.')

    while True:
        print('f21')
        f21(dom)
        time.sleep(1)
except KeyboardInterrupt:
    pass
