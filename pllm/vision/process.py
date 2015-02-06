from twisted.internet import defer, task, threads

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
        self.max_retries = 2

    def run(self):
        fn = getattr(tasks, self.task_name)
        tries = 0
        while True:
            try:
                result = fn(*self.args)
                break

            except Exception, e:
                if tries >= self.max_retries:
                    import traceback
                    traceback.print_exc()
                    return self

                print("Task failed, reason: {0}".format(e))
                print("Retrying")
                tries += 1

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
            job.running = True
            print("Starting {0}".format(job))
            self.process_task(job)
            return

    def done(self, job):
        self.running -= 1
        print("Done {0}".format(job))
        if job.result is not None:
            job.d.callback((job.task_name, job.ident, job.result))
        else:
            print("Task did not return any result")

    def process_task(self, job):
        d = threads.deferToThread(job.run)
        d.addCallback(self.done)

        return d

    def _process_task(self, task_name, ident, priority, args):
        fn = getattr(tasks, task_name)
        return (task_name, ident, self.run_task(fn, args))

    def run_task(self, fn, args):
        return fn(*args)
