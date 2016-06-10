#!/usr/bin/env python
# coding=utf-8

r"""
NEXUS 7000 CHECK IF ANY INSTALLED M1 MODULES ARE FAILED/FAILING

This script is designed to run local on a Cisco Nexus 7000 switch
with the goal of finding M1 linecards that have failed.
There exists an issue where these cards fail silently and stop
forwarding any traffic.
In a failure scenario the module logs 'mstat_rx_pkts_bad_crc' asic
errors.
these counters can be cleared with the following command:
'debug system internal clear-counters module <module>'
"""

#
# LICENSE INFORMATION
# ===
# Copyright 2016 Brandon Premo

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from cisco import *
from syslog import syslog
import sys
import re
import pickle
import time


# set global vars for the script
now = time.asctime(time.localtime(time.time()))
error_stat_filename='/bootflash/error_stats'

def build_module_list():
    # build list of affected modules
    m1_cards=[]
    output1=cli('show module').split('\n')
    for line in output1:
        if 'N7K-M132XP' in line:
            m1_cards.append(line.split()[0])
    return m1_cards

def get_serial(module):
    serial=clid('show module ' + module
               )['TABLE_modmacinfo/serialnum/1']
    return serial

def check_for_errors(module):
    # check asic counters if CRC counters are incrementing
    error_dict=dict()
    command='show hardware internal error module'
    regex = ".* mstat_rx_pkts_bad_crc                         (.*)  .*"
    output=cli(command + ' ' + module).split('\n')

    for line in output:
        match = re.search(regex,line)
        if match and match.group(1):
            error_dict[module] = int(match.group(1))
        else:
            error_dict[module] = 0
    return error_dict

def compare_counters(current_counters):
    # compare current counter with previous
    first_run=False
    # load previous counters
    try:
        old_counters = pickle.load(open(error_stat_filename+'.p','rb'))
    except (IOError), e:
        first_run=True

    if not first_run:
        for module in current_counters.keys():
            if module in old_counters:
                if current_counters[module] > old_counters[module]:
                    # counters have incremented since last run
                    print(('Counters for module {0} have incremented'
                          ).format(module))
                    serial=get_serial(str(module))
                    syslog(1,('Module {0} -- SN:{1} is failing'
                             ).format(module,serial))
            else:
                # to get here the module does not exist in previous
                # output
                print("no previous stats for module {0}".format(module))

def write_output(current_counters):
    pickle.dump(current_counters,open(error_stat_filename+'.p','wb'))

    with open(error_stat_filename+'.log','a') as f:
        f.write('\n---\n')
        f.write('{0}\n'.format(now))
        for k, v in current_counters.iteritems():
            serial=get_serial(str(k))
            f.write("Module {0} - {1} - errors:  {2}\n".format(k,serial,v))
        f.flush()

def main():
    # main function

    for linecard in build_module_list():
        error_stats = check_for_errors(linecard)

    compare_counters(error_stats)

    write_output(error_stats)

if __name__ == '__main__':
    sys.exit(main())
