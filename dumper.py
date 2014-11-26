#!/usr/bin/python
from twisted.internet import reactor

from pllm import config, monitor


def dump(evt, data):
    if data:
        print(evt + ':' + str(data))
    else:
        print(evt)

fact = monitor.MonitorClientFactory()
fact.fwd = dump

reactor.connectTCP('localhost', config.get('monitor_port'), fact)
reactor.run()
