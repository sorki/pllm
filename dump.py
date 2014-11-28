#!/usr/bin/python
import argparse

from twisted.internet import reactor

from pllm import config, monitor

parser = argparse.ArgumentParser(description='PLLM monitor dumper')
parser.add_argument('-r', '--raw',
                    action="store_true", default=False,
                    help='Dump raw messages')

args = parser.parse_args()


def dump(evt, data):
    if data:
        print(evt + ':' + str(data))
    else:
        print(evt)


def dump_raw(msg):
    print(msg)

fact = monitor.MonitorClientFactory()

if args.raw:
    fact.fwd_raw = dump_raw
else:
    fact.fwd = dump

reactor.connectTCP('localhost', config.get('monitor_port'), fact)
reactor.run()
