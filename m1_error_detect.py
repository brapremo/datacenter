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

debug = True

if debug:
    test_modules=[1,2]


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
    if debug:
        serial='XXXXXXXXXXX'
    else:
        serial=clid('show module ' + module
               )['TABLE_modmacinfo/serialnum/1']
    return serial

def get_asic(module,ports):
    first_port=ports.split(',')[0]
    command = ('slot {0} show hardware internal '
               'dev-port-map').format(module)

    if debug:
        output=(
    '''--------------------------------------------------------------
CARD_TYPE:       32 port 10G
>Front Panel ports:32
--------------------------------------------------------------
 Device name             Dev role              Abbr num_inst:
--------------------------------------------------------------
> Octopus                DEV_QUEUEING           QUEUE  2
> Sotra                  DEV_REWRITE            RWR_1  2
> Metropolis             DEV_REWRITE            RWR_0  4
> Eureka                 DEV_LAYER_2_LOOKUP     L2LKP  1
> Lamira                 DEV_LAYER_3_LOOKUP     L3LKP  1
> R2D2                   DEV_ETHERNET_MAC       MAC_0  8
> Santa-Cruz-Module      DEV_SWITCH_FABRIC      SWICHF 1
> Ashburton              DEV_ETHERNET_MAC       MAC_2  8
> Naxos                  DEV_ETHERNET_MAC       MAC_1  16
> EDC                    DEV_PHY                PHYS   16
+-----------------------------------------------------------------------+
+----------------+++FRONT PANEL PORT TO ASIC INSTANCE MAP+++------------+
+-----------------------------------------------------------------------+
FP port |  PHYS | MAC_0 | MAC_1 | MAC_2 | RWR_0 | RWR_1 | L2LKP | L3LKP | QUEUE |SWICHF
   1       15      7       15      7       3       0       0       0       1       0
   2       0       0       0       0       0       1       0       0       0       0
   3       15      7       15      7       3       0       0       0       1       0
   4       0       0       0       0       0       1       0       0       0       0
   5       14      7       14      7       3       0       0       0       1       0
   6       1       0       1       0       0       1       0       0       0       0
   7       14      7       14      7       3       0       0       0       1       0
   8       1       0       1       0       0       1       0       0       0       0
   9       13      6       13      6       3       0       0       0       1       0
   10      2       1       2       1       0       1       0       0       0       0
   11      13      6       13      6       3       0       0       0       1       0
   12      2       1       2       1       0       1       0       0       0       0
   13      12      6       12      6       3       0       0       0       1       0
   14      3       1       3       1       0       1       0       0       0       0
   15      12      6       12      6       3       0       0       0       1       0
   16      3       1       3       1       0       1       0       0       0       0
   17      11      5       11      5       2       0       0       0       1       0
   18      4       2       4       2       1       1       0       0       0       0
   19      11      5       11      5       2       0       0       0       1       0
   20      4       2       4       2       1       1       0       0       0       0
   21      10      5       10      5       2       0       0       0       1       0
   22      5       2       5       2       1       1       0       0       0
   23      10      5       10      5       2       0       0       0       1       0
   24      5       2       5       2       1       1       0       0       0       0
   25      9       4       9       4       2       0       0       0       1       0
   26      6       3       6       3       1       1       0       0       0       0
   27      9       4       9       4       2       0       0       0       1       0
   28      6       3       6       3       1       1       0       0       0       0
   29      8       4       8       4       2       0       0       0       1       0
   30      7       3       7       3       1       1       0       0       0       0
   31      8       4       8       4       2       0       0       0       1       0
   32      7       3       7       3       1       1       0       0       0       0
+-----------------------------------------------------------------------+
+-----------------------------------------------------------------------+'''.split('\n'))
    else:
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

    if debug:
        #if module == '3':

        output=('4464 mstat_rx_pkts_bad_crc                   '
                '      0000000000757233  10,12,14,16 -\n'
                '4464 mstat_rx_pkts_bad_crc                   '
                '      0000000000135242  1,3,5,7 -\n'
                ' Nothing Here\n'
                '4464 mstat_rx_pkts_bad_crc                   '
                '      0000000001235115  2,4,6,8 -').split('\n')
    else:
        output=cli(command + ' ' + module).split('\n')

    asic_error=dict()
    for line in output:
        if debug:
            print('Line: {0}'.format(line))
        match = re.search(regex,line)
        if match and match.group(1) and match.group(2):
            if debug:
                print('found regex match')
                print('adding value: {0} to key: {1}'.format(str(match.group(1)).strip('0'),match.group(2)))
            asic_error[match.group(2)] = str(match.group(1)).strip('0')
           # error_dict[module] = asic_error
    #return error_dict
    if len(asic_error.keys()) > 0:
        return asic_error
    else:
        return

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

def write_output(current_counters):
    pickle.dump(current_counters,open(output_filename+'.p','wb'))

    with open(output_filename+'.log','a') as f:
        f.write('\n---\n')
        f.write('{0}\n'.format(now))
        for k, v in current_counters.iteritems():
            serial=get_serial(str(k))
            f.write("Module {0} - {1}:\n".format(k,serial))
            for l, w in v.iteritems():
                asic=get_asic(k,l)
                f.write(("ASIC {0} - Ports {1} - Errors:  {2:,}\n"
                        ).format(asic,l,int(w)))
        f.flush()

def main():
    # main function
    error_stats=dict()
    if debug:
        for linecard in test_modules:
            error_stats[linecard] = check_for_errors(linecard)
            if debug:
                for k, v in error_stats[linecard].iteritems():
                    print('k:{0} v:{1}'.format(k,v))
    else:
        for linecard in build_module_list():
            error_stats = check_for_errors(linecard)

    if len(error_stats.keys()) > 0:
            compare_counters(error_stats)

    write_output(error_stats)

if __name__ == '__main__':
    sys.exit(main())
