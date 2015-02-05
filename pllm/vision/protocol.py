import os

from twisted.protocols.basic import LineReceiver
from twisted.internet import defer
from twisted.internet.protocol import Factory

from pllm import util
from pllm.vision import process


class VisionClientProtocol(LineReceiver):
    identmap = dict()

    def lineReceived(self, line):
        dec = util.decdata(line)
        dec = dec[1]
        task_name, ident, result = dec

        self.identmap["{0}_{1}".format(task_name, ident)].callback(result)

    def process_task(self, task_name, ident, priority, args):
        d = defer.Deferred()
        self.identmap["{0}_{1}".format(task_name, ident)] = d

        enc = util.encdata((task_name, ident, priority, args))
        self.sendLine(enc)

        return d


class VisionServerProtocol(LineReceiver):
    def connectionMade(self):
        print("Got client")

    def connectionLost(self, reason):
        print("Lost client")

    def sendResults(self, results, ident):
        print("Sending results of #{0}".format(ident))
        enc = util.encdata((ident, results))
        self.sendLine(enc)

    def lineReceived(self, line):
        dec = util.decdata(line)
        task_name, ident, priority, args = dec

        print("Starting task #{0} {1} with args {2}"
              .format(task_name, ident, args))

        task = self.factory.vision.add_task(
            task_name, ident, priority, args)
        task.addCallback(self.sendResults, ident)


class VisionServerFactory(Factory):
    def __init__(self):
        self.vision = process.VisionPipeline()

    def buildProtocol(self, addr):
        proto = VisionServerProtocol()
        proto.factory = self
        return proto
