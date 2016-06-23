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

debug = False


# set global vars for the script
now = time.asctime(time.localtime(time.time()))
output_filename='/bootflash/error_stats'

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

def get_asic(module,ports):
    first_port=ports.split(',')[0]
    command = ('slot {0} show hardware internal '
               'dev-port-map').format(module)

    output=cli(command).split('\n')

    output=output[20:len(output)-2]

    for line in output:
        if line.split()[0] == first_port:
            asic = line.split()[2]
    return asic

def check_for_errors(module):
    # check asic counters if CRC counters are incrementing
    error_dict=dict()
    command='show hardware internal error module'
    #regex = ".* mstat_rx_pkts_bad_crc                         (.*)  .*"
    regex = (".* mstat_rx_pkts_bad_crc                         "
             "(.*)  (.*) -")

    output=cli(command + ' ' + module).split('\n')

    asic_error=dict()
    for line in output:
        match = re.search(regex,line)
        if match and match.group(1) and match.group(2):
            if debug:
                print('found regex match')
                print('adding value: {0} to key: {1}'.format(str(match.group(1)).strip('0'),match.group(2)))
            asic_error[match.group(2)] = str(match.group(1)).strip('0')
    #return error_dict
    if len(asic_error.keys()) > 0:
        return asic_error
    else:
        return False

def compare_counters(current_counters):
    # compare current counter with previous
    first_run=False
    # load previous counters
    try:
        old_counters = pickle.load(open(output_filename+'.p','rb'))
    except (IOError), e:
        first_run=True

    if not first_run:
        # check if counter dictionary is empty
        for module in current_counters.keys():
            if module in old_counters:
                if current_counters[module] > old_counters[module]:
                    # counters have incremented since last run
                    print(('Counters for module {0} have incremented'
                          ).format(module))
                    serial=get_serial(str(module))
                    syslog(1,('Module {0} -- SN:{1} is failing.'
                             ).format(module,serial))
            else:
                # to get here the module does not exist in previous
                # output
                print("no previous stats for module {0}".format(module))
    else:
        # here would mean this is the first time the script has run
        return

def write_output(current_counters):
    # output serialized data from current scan
    pickle.dump(current_counters,open(output_filename+'.p','wb'))

    # assume log file exists
    log_exist = True

    # open and read contents of existing log file
    try:
        with open(output_filename+'.log','r') as f:
            data = f.read()
    # catch if log file does not exist
    except (IOError), e:
        log_exist = False

    # write out log file
    with open(output_filename+'.log','w') as f:
        f.write('\n---\n')
        f.write('{0}'.format(now))
        for k, v in current_counters.iteritems():
            if v:
                serial=get_serial(str(k))
                f.write("\n+ Module {0} | SN {1}:\n".format(k,serial))
                for l, w in v.iteritems():
                    asic=get_asic(k,l)
                    f.write(("-- ASIC {0} - Ports {1} - Errors:  {2}\n"
                            ).format(asic,l,w))
        f.flush()
        # append old log file contents
        if log_exist:
            f.write(data)
            f.flush()

def main():
    # main function
    error_stats=dict()
    for linecard in build_module_list():
        error_stats = check_for_errors(linecard)
    if len(error_stats.keys()) > 0:
            compare_counters(error_stats)
    write_output(error_stats)

if __name__ == '__main__':
    sys.exit(main())
