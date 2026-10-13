#!/usr/bin/env python3
"""Replay a real relay-routed ZTO call, or collect another read-only rehearsal."""
import argparse
import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
CORE = HERE.parent / 'call-rehearsal' / 'rehearse.py'
spec = importlib.util.spec_from_file_location('relay_rehearsal_core', CORE)
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('demo', help='replay saved real ZTO evidence without networking')
    live = commands.add_parser('live', help='read ZTO or IMD through an explicit relay')
    live.add_argument('--relay', required=True)
    live.add_argument('--rpc', choices=core.ENDPOINTS, default=core.ENDPOINTS[0],
                      help='public source attribution, not a verified upstream identity')
    live.add_argument('--token', choices=core.TOKENS, default='ZTO')
    live.add_argument('--save', help='new observation file inside the workspace')
    args = parser.parse_args(argv)
    if args.command == 'demo':
        return core.main(['replay', str(HERE / 'zto-relay-observation.json')])
    forwarded = ['demo', '--relay', args.relay, '--rpc', args.rpc, '--token', args.token]
    if args.save:
        forwarded.extend(['--save', args.save])
    return core.main(forwarded)


if __name__ == '__main__':
    sys.exit(main())
