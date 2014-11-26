from twisted.python import log
from twisted.internet.protocol import Factory, ClientFactory
from twisted.protocols.basic import LineReceiver

import util


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
        nmsg = msg
        if data:
            nmsg += ':{0}'.format(data)
        self.broadcast(nmsg)

    def emitenc(self, msg, data):
        self.emit(msg, '|' + util.encdata(data))


class MonitorClient(LineReceiver):
    delimiter = '\n'
    fwd = None

    def decode(self, msg):
        if ':' in msg:
            evt, data = msg.split(':', 1)
            if data[0] == '|':
                data = util.decdata(data[1:])
        else:
            evt = msg
            data = None

        return (evt, data)

    def lineReceived(self, line):
        evt, data = self.decode(line)

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
