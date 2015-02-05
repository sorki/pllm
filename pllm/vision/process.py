import os
import multiprocessing

from twisted.internet import reactor, defer, task, threads

from pllm import config, util
from pllm.vision import tasks


class Job(object):
    def __init__(self, task_name, ident, priority, args):
        self.task_name = task_name
        self.ident = ident
        self.priority = priority
        self.args = args
        self.obsolete = False
        self.running = False
        self.d = defer.Deferred()
        self.result = None

    def run(self):
        fn = getattr(tasks, self.task_name)
        result =  fn(*self.args)
        self.result = result
        return self

    def __str__(self):
        return "#{0} {1}({2})".format(self.ident, self.task_name,
                                      self.args)


class VisionPipeline(object):
    def __init__(self):
        self.limit = 2
        self.running = 0
        self.q = list()
        self.lp = task.LoopingCall(self.maybe_run_task)
        self.lp.start(1)

    def add_task(self, task_name, ident, priority, args):
        for j in self.q:
            if j.ident < ident:
                j.obsolete = True

        job = Job(task_name, ident, priority, args)
        self.q.append(job)
        return job.d

    def maybe_run_task(self):
        if self.running >= self.limit:
            return

        for job in self.q:
            if job.obsolete or job.running:
                continue

            self.running += 1
            job.running =True
            print("Starting {0}".format(job))
            self.process_task(job)
            return

    def done(self, job):
        self.running -= 1
        print("Done {0}".format(job))
        job.d.callback((job.task_name, job.ident, job.result))

    def process_task(self, job):
        d = threads.deferToThread(job.run)
        d.addCallback(self.done)

        return d

    def _process_task(self, task_name, ident, priority, args):
        fn = getattr(tasks, task_name)
        return (task_name, ident, self.run_task(fn, args))

    def run_task(self, fn, args):
        return fn(*args)


def process(fpath):
    full = ocr(fpath, block=False)

    segs = segmentize(fpath)
    segs_res = {}

    for segname, shape in segs.items():
        x, y, w, h = shape
        seg_ocr = ocr(segname)
        if seg_ocr:
            segs_res[segname] = (shape, seg_ocr)

    return (full, segs_res)
