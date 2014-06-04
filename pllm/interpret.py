import bdb


class FixedBdb(bdb.Bdb):
    '''
    Bdb with fixed quit, required until
    http://bugs.python.org/issue16446
    '''

    def trace_dispatch(self, *args):
        if self.quitting:
            raise bdb.BdbQuit

        return bdb.Bdb.trace_dispatch(self, *args)


class Interpret(FixedBdb):
    def __init__(self, domain, line_callback=lambda x: x):
        bdb.Bdb.__init__(self)
        self.domain = domain
        self.line_callback = line_callback

    def user_line(self, frame):
        if frame.f_code.co_filename == '<string>':
            self.line_callback(frame)

    def start(self, code):
        self.run(code, dict(dom=self.domain))
