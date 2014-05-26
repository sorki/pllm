import bdb

class Interpret(bdb.Bdb):
    def __init__(self, domain, line_callback=lambda x: x):
        bdb.Bdb.__init__(self)
        self.domain = domain
        self.line_callback = line_callback

    def user_line(self, frame):
        if frame.f_code.co_filename == '<string>':
            self.line_callback(frame)

    def start(self, code):
        self.run(code, dict(dom=self.domain))
