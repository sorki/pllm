from twisted.python import log
from twisted.internet.protocol import Factory
from twisted.protocols.basic import LineReceiver


class Monitor(LineReceiver):
    delimiter = '\n'

    def connectionMade(self):
        log.msg('monitor got new client')
        self.factory.clients.append(self)

    def connectionLost(self, reason):
        log.msg('monitor lost client')
        self.factory.clients.remove(self)

    def lineReceived(self, line):
        log.msg('monitor recieved: {0}'.format(line))
        #self.sendLine('ok')


class MonitorFactory(Factory):
    protocol = Monitor
    clients = []

    def broadcast(self, msg):
        for client in self.clients:
            client.sendLine(msg)
