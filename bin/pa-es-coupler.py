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
import logging
import os
import sys
import signal
import time
from pa_elasticsearch import Coupler

coupler_running = True
reload_coupler = True

def signal_handler(signum, frame):
    "Handles unix signals"
    if signum == signal.SIGTERM:
        logging.info("Exiting when poll ends")
        coupler_running = False
    elif signum == signal.SIGHUP:
        logging.info("Reloading config next poll")
        reload_coupler = True

def create_example_config():
    "Prints out a config example"
    print(
"""[coupler]
# Leave logfile out or empty to log to stderr
logfile = /var/log/coupler.log
loglevel = WARNING
lockfile = /var/lock/pa-es-coupler.lock
# Polling period in minutes.
poll_period = 10

[elasticsearch]
# A simple config:
# hosts = http://localhost:9200

# A more complex set up:
# hosts = http://server1.local:9200,https://server2.local:9243
# username = foo
# password = bar

[pa]
username = foo
password = "bar123!!"
basic_auth = "abcdef1=="
realm = 12345
# jobtemplates = Single,Multi,Crawl,Scripted
# Below is the only supported date format!
# since = 2017-01-30T00:00+0000""")

def run(argv=None):
    "Runs the program"
    parser = argparse.ArgumentParser(description="Extracts PA data into ElasticSearch")
    parser.add_argument('--config', dest='config_path', nargs=1,
                        help="Path to the config file")
    parser.add_argument(
        '--log', dest='log',
        help="Path to the log file the coupler will write into")
    parser.add_argument(
        '--loglevel', dest='loglevel',
        help="The log level to report in the log file. Can be ERROR, WARNING or INFO")
    parser.add_argument(
        '--full-index', action='store_true',
        help="Force a full reindex of PA data")
    parser.add_argument(
        '--example-config', action='store_true',
        help="Outputs a sample configuration file and exits"
    )
    args = parser.parse_args()

    if args.example_config:
        create_example_config()
        return 0

    conf = os.path.join(os.getcwd(), 'config.ini')
    if args.config_path is not None:
        conf = os.path.realpath(args.config_path[0])

    signal.signal(signal.SIGHUP, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        coupler = Coupler(conf)
        coupler.run()
    except Exception as error:
        logging.critical(str(error))
        return 1

if __name__ == '__main__':
    sys.exit(run(sys.argv))
