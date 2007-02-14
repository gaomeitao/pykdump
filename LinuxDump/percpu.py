#
# -*- coding: latin-1 -*-
# Time-stamp: <06/11/24 13:39:58 alexs>

# Per-cpu functions

from pykdump.API import *

# Emulate __get_cpu_var. For efficiency rerasons We return
# the whole array (list) of addresses for all CPUs

def get_cpu_var_26(varname):
    cpuvarname = "per_cpu__" + varname
    saddr = sym2addr(cpuvarname)
    addrlist = []
    for cpu in range(CPUS):
        addr = (saddr + per_cpu_offsets[cpu])  & 0xffffffffffffffffL
        addrlist.append(addr)
    return addrlist

def get_cpu_var_24(varname, cpu = None):
    saddr = sym2addr(varname)
    addrlist = []
    ctype =  whatis(varname).ctype
    ssize = struct_size(ctype)
    addrlist = []
    for cpu in range(CPUS):
        addrlist.append(saddr +  ssize*cpu)
    return addrlist

CPUS = sys_info.CPUS
if (symbol_exists("per_cpu__runqueues")):
    if (symbol_exists("cpu_pda")):
        # AMD64
        per_cpu_offsets = []
        pda_addr = sym2addr("cpu_pda")
        size = struct_size("struct x8664_pda")
        for cpu in range(0, sys_info.CPUS):
            cpu_pda = readSU("struct x8664_pda", pda_addr +  size*cpu)
            offset = cpu_pda.data_offset
            per_cpu_offsets.append(offset)
    elif (symbol_exists("__per_cpu_offset")):
        per_cpu_offsets = readSymbol("__per_cpu_offset")
    else:
        per_cpu_offsets = [0]
    get_cpu_var = get_cpu_var_26
else:
    get_cpu_var = get_cpu_var_24