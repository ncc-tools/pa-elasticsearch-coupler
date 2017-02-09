#!/usr/bin/env python3

#    Copyright 2017 NCC Group plc
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import argparse
import sys
import os
from pa_elasticsearch import Coupler

def run(argv=None):
    parser = argparse.ArgumentParser(description='Extracts PA data into ElasticSearch')
    parser.add_argument('--config', dest='config_path', nargs=1,
                        help="Path to the config file")
    parser.add_argument(
        '--log', dest='log',
        help="Path to the log file the coupler will write into")
    parser.add_argument(
        '--loglevel', dest='loglevel',
        help="The log level to report in the log file. Can be ERROR, WARNING or INFO")
    parser.add_argument(
        '--lockfile', dest='lockfile',
        help="Path to the lock file used to prevent concurrent imports")
    parser.add_argument(
        '--full-index', action='store_true',
        help="Force a full reindex of PA data")
    args = parser.parse_args()

    conf = '/etc/pa-coupler/config.ini'
    if os.name == 'nt':
        conf = '{0}/config.ini'.format(os.path.dirname(os.path.realpath(__file__)))
    if args.config_path is not None:
        conf = os.path.realpath(args.config_path[0])

    try:
        coupler = Coupler(conf, log=args.log, loglevel=args.loglevel, lockfile=args.lockfile)
        return coupler.run(args.full_index)
    except Exception as error:
        print(str(error))
        return 100

if __name__ == '__main__':
    sys.exit(run(sys.argv))
