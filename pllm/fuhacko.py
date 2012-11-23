import bdb

class Fuhacko(bdb.Bdb):
    def user_line(self, frame):
        #import IPython
        #IPython.embed()
        if frame.f_code.co_filename == '<string>':
            print frame.f_lineno


