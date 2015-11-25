#!/usr/bin/env python
# -*- coding: utf-8 -*-
# module LinuxDump.Time
#
# --------------------------------------------------------------------
# (C) Copyright 2006-2015 Hewlett Packard Enterprise Development LP
#
# Author: Alex Sidorenko <asid@hpe.com>
#
# --------------------------------------------------------------------
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

from __future__ import print_function

__doc__ = '''
This is a package providing subroutines for time manipulation
'''

__all__ = ['j_delay', 'seconds_since_boot', 'get_uptime_fromproc',
           'get_uptime_fromcrash']

# Tasks and Pids

from pykdump.API import *
import crash
from collections import namedtuple


def j_delay(ts, jiffies):
    v = (jiffies - ts) & INT_MASK
    if (v > INT_MAX):
        v = "     n/a"
    elif (v > HZ*3600*20):
        v = ">20hours"
    else:
        v = "%8.2f s" % (float(v)/HZ)
    return v

class _readSymbol():
    def __init__(self, topsymbol = None):
        self.topsymbol = topsymbol
    def __getattr__(self, attr):
        if (self.topsymbol):
            return getattr(readSymbol(self.topsymbol), attr)
        else:
            return readSymbol(attr)

timespec = namedtuple("timespec", ['tv_sec', 'tv_nsec'])

NSEC_PER_SEC = 1000000000
def set_normalized_timespec(sec, nsec):
    while (nsec >= NSEC_PER_SEC):
        nsec -= NSEC_PER_SEC
        sec += 1
	
    while (nsec < 0):
        nsec += NSEC_PER_SEC
        sec -= 1

    return timespec(sec, nsec)



def getboottime():
    tv_sec = tk.wall_to_monotonic.tv_sec +  tk.total_sleep_time.tv_sec
    tv_nsec = tk.wall_to_monotonic.tv_nsec + tk.total_sleep_time.tv_nsec
    return set_normalized_timespec(-tv_sec, -tv_nsec)
    

def seconds_since_boot():
    boot = getboottime()
    return get_seconds() - boot.tv_sec

# Kernel-dependent subroutines. In older kernels, we have a global
# 'struct timespec wall_to_monotonic' and 'xtime', on newer kernels they
# are members, 'timekeeper.wall_to_monotonic' and 'timekeeper.xtime'
#


if (symbol_exists("wall_to_monotonic")):
    tk = _readSymbol()
    def get_seconds():
        return tk.xtime.tv_sec
    # In old (e.g. RHEL5) kernels, there is no seconds_since_boot().
    # In this case, refage calculations in
    # use just get_seconds() -> xtime.tv_sec;
    if (not symbol_exists("total_sleep_time")):
        seconds_since_boot = None
else:
    tk = _readSymbol("timekeeper")
    def get_seconds():
        return tk.xtime_sec
        

def get_uptime_fromproc():
    with open('/proc/uptime', 'r') as f:
        uptime_seconds = int(float((f.readline().split()[0])))
    return uptime_seconds


def get_uptime_fromcrash():
    return crash.get_uptime()/HZ
