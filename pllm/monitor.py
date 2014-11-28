from twisted.python import log
from twisted.internet.protocol import Factory, ClientFactory
from twisted.protocols.basic import LineReceiver

import util


def encode(evt, data):
    if data:
        return '_{0}:{1}'.format(evt, util.encdata(data))
    else:
        return evt


def decode(msg):
    if msg[0] == '_':
        evt, data = msg.split(':', 1)
        data = util.decdata(data)
    else:
        evt = msg
        data = None

    return (evt, data)


class MonitorServer(LineReceiver):
    delimiter = '\n'

    def connectionMade(self):
        log.msg('monitor got new client')
        self.factory.clients.append(self)

    def connectionLost(self, reason):
        log.msg('monitor lost client')
        self.factory.clients.remove(self)

    def lineReceived(self, line):
        log.msg('monitor recieved: {0}'.format(line))


class MonitorFactory(Factory):
    protocol = MonitorServer
    clients = []

    def broadcast(self, msg):
        for client in self.clients:
            client.sendLine(msg)

    def emit(self, msg, data=None):
        self.broadcast(encode(msg, data))


class MonitorClient(LineReceiver):
    delimiter = '\n'
    fwd = None
    fwd_raw = None

    def lineReceived(self, line):
        evt, data = decode(line)

        if self.fwd_raw:
            self.fwd_raw(line)

        if self.fwd:
            self.fwd(evt, data)
        else:
            print(evt)
            if data:
                print(repr(data))


class MonitorClientFactory(ClientFactory):
    protocol = MonitorClient
    fwd = None

    def buildProtocol(self, addr):
        proto = self.protocol()
        if self.fwd:
            proto.fwd = self.fwd

        return proto
