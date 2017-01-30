#!/usr/bin/env python3

import argparse
import sys
import os
from pacoupler.coupler import Coupler

def run(argv=None):
    parser = argparse.ArgumentParser(description='Extracts PA data into ElasticSearch')
    parser.add_argument('--config', dest='config_path', nargs=1,
                        help="Path to the config file")
    parser.add_argument('--log', dest='log', help="Path to the log file the coupler will write into")
    parser.add_argument('--loglevel', dest='loglevel', help="The log level to report in the log file. Can be ERROR, WARNING or INFO")
    parser.add_argument('--lockfile', dest='lockfile', help="Path to the lock file used to prevent concurrent imports")
    parser.add_argument('--full-index', action='store_true', help="Force a full reindex of PA data")
    args = parser.parse_args()

    conf = '/etc/pa-coupler/config.ini'
    if os.name == 'nt':
        conf = os.path.dirname(os.path.realpath(__file__)) + '/config.ini'
    if args.config_path is not None:
        conf = os.path.realpath(args.config_path[0])

    coupler = Coupler(conf, log=args.log, loglevel=args.loglevel, lockfile=args.lockfile)
    return coupler.run(args.full_index)

if __name__ == '__main__':
    sys.exit(run(sys.argv))
