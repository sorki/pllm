from twisted.application import service, internet
from twisted.cred import portal

from twisted.conch.insults import insults
from twisted.conch import manhole, manhole_ssh, checkers


class ChainedProtocolFactory(object):
    def __init__(self, namespace):
        self.namespace = namespace

    def __call__(self):
        return insults.ServerProtocol(manhole.ColoredManhole, self.namespace)


def manhole_service(opts):
    """
    Create a manhole server service.
    """

    svc = service.MultiService()

    namespace = opts['namespace']
    if namespace is None:
        namespace = {}

    checker = checkers.SSHPublicKeyDatabase()

    if opts['ssh']:
        sshRealm = manhole_ssh.TerminalRealm()
        sshRealm.chainedProtocolFactory = ChainedProtocolFactory(namespace)

        sshPortal = portal.Portal(sshRealm, [checker])
        f = manhole_ssh.ConchFactory(sshPortal)
        csvc = internet.TCPServer(opts['ssh'], f)
        csvc.setServiceParent(svc)

    return svc
