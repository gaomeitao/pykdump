# module LinuxDump.inet.routing
#
# Time-stamp: <09/03/12 15:35:12 alexs>
#
# Copyright (C) 2006-2007 Alex Sidorenko <asid@hp.com>
# Copyright (C) 2006-2007 Hewlett-Packard Co., All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# Dump routing table from RT-hash

debug = False

from pykdump.API import *

from LinuxDump.inet import *

# On 2.4
# struct flowi {
# 	int	oif;
# 	int	iif;

# 	union {
# 		struct {
# 			__u32			daddr;
# 			__u32			saddr;
# 			__u32			fwmark;
# 			__u8			tos;
# 			__u8			scope;
# 		} ip4_u;
		
# 		struct {
# 			struct in6_addr		daddr;
# 			struct in6_addr		saddr;
# 			__u32			flowlabel;
# 		} ip6_u;
# 	} nl_u;

# on 2.6
# struct flowi {
# 	int	oif;
# 	int	iif;
# 	__u32	mark;

# 	union {
# 		struct {
# 			__be32			daddr;
# 			__be32			saddr;
# 			__u8			tos;
# 			__u8			scope;
# 		} ip4_u;


# static struct rt_hash_bucket 	*rt_hash_table;
def print_rt_hash():
    rt_hash_mask = readSymbol("rt_hash_mask")
    rt_hash_table_addr = readSymbol("rt_hash_table")
    if (rt_hash_table_addr == 0):
	print WARNING, "rt_hash_table is NULL"
	return
    rthb = getStructInfo("struct rt_hash_bucket")
    rthb_sz = rthb.size

    rtable_i = getStructInfo("struct rtable")
    rt_next_off = rtable_i["u"].offset

    
    buckets = getFullBuckets(rt_hash_table_addr, rthb_sz,
                             rt_hash_mask+1, rthb["chain"].offset)
    buckets.reverse()

    count = 0
    jiffies = readSymbol("jiffies")
    nl_u_off = member_offset("struct flowi", "nl_u")
    print "dev      rt_src            rt_dst          fl4_src         fl4_dst   sec ago"
    print "---   -------------    -------------    -------------    -----------  --------"


    for head in buckets:
        # rtable entries are linked by 'u.rt_next' pointer
        #print hexl(head)
        for rtaddr in readList(head, rt_next_off):
            #print "\t", hexl(rtaddr)
            count += 1
            r = readSU("struct rtable", rtaddr)
            dst = r.u.dst
            fl = r.fl
            addrfl = Addr(fl)

            fl4_dst = readU32(addrfl + nl_u_off)
            fl4_src = readU32(addrfl + nl_u_off + 4)

            print dst.dev.Deref.name.ljust(5), \
                  ntodots(r.rt_src).ljust(16), \
                  ntodots(r.rt_dst).ljust(16),\
                  ntodots(fl4_src).ljust(16), \
                  ntodots(fl4_dst).ljust(16),\
                  (jiffies - dst.lastuse)/sys_info.HZ

    print "\n", count, "entries"

def print_fib():
    if (member_offset("struct fib_node", "fn_alias") !=-1):
        g = get_fib_v26()
    else:
        g = get_fib_v24()
    do_fib_print(g)


# Do the real printing, an Iterable passed as an argument
def do_fib_print(g):
    cmdformat = True
    print ""
    if (cmdformat):
        print "Destination     Gateway         Genmask         Flags Metric Ref    Use Iface"
    else:
        print "Iface\tDestination\tGateway \tFlags\tRefCnt\tUse\tMetric\tMask\t\tMTU\tWindow\tIRTT"
    for e in g:
        e.ref = 0               # Not used in the Linux kernel
        e.use = 0
        if (cmdformat):
            # emulate 'route -n' format
            dest = ntodots(e.dest)
            gw= ntodots(e.gw)
            genmask = ntodots(e.mask)
            oflags = flags2str(e.flags)
            print "%-15s %-15s %-15s %-5s %-6s %-6s %-3s %-8s" % \
                  (dest, gw, genmask, oflags, e.metric, e.ref, e.use, e.dev)
        else:
            print "%s\t%08X\t%08X\t%04X\t%d\t%08X\t%d" % \
                  (e.dev, e.dest, e.gw, e.flags, e.metric, e.mask, e.mtu)
                        


def get_fib_v26():
    if (symbol_exists("fib_tables")):
        #struct fn_hash *table = (struct fn_hash *) ip_fib_main_table->tb_data;
        RT_TABLE_MAIN = readSymbol("main_rule").r_table
        #print "RT_TABLE_MAIN=",RT_TABLE_MAIN
        fib_tables = readSymbol("fib_tables")
        table_main = readSU("struct fib_table", fib_tables[RT_TABLE_MAIN])
    else:
        if (symbol_exists("main_rule")):   # < 2.6.24
            RT_TABLE_MAIN = readSymbol("main_rule").common.table
        else:
            RT_TABLE_MAIN = 254
        #print "RT_TABLE_MAIN=",RT_TABLE_MAIN

        if (symbol_exists("fib_table_hash")):
            #static struct hlist_head fib_table_hash[FIB_TABLE_HASHSZ];
            fib_table_hash = readSymbol("fib_table_hash")
        elif (symbol_exists("init_net")): # 2.6.27
            fib_table_hash = readSymbol("init_net").ipv4.fib_table_hash
        else:
            raise TypeError, "Don't know how to get routes for this kernel"

        offset = member_offset("struct fib_table", "tb_hlist")

	table_main = None
        # Warning: on 2.6.27 the size of fib_table_hash is defined by
        # FIB_TABLE_HASHSZ (usually 2 for IPv4). As there is no way
        # to obtain it from dump, we break out as soon as we find
        # the main table
        for b in fib_table_hash:
            first = b.first
            if (first):
                for a in readList(first, 0):
                    tb = readSU("struct fib_table", a-offset)
                    print tb, tb.tb_id
                    if (tb.tb_id == RT_TABLE_MAIN):
                        table_main = tb
                        break
                if (table_main): break

    #     unsigned char tb_data[0];
    #print "table_main=", table_main
    fn_hash = readSU("struct fn_hash", table_main.tb_data)

    hlist_head_sz = struct_size("struct hlist_head")
    
    fn_zone_list_addr = fn_hash.fn_zone_list
    fz_next_off = getStructInfo("struct fn_zone")["fz_next"].offset

    if (debug):
        print "fn_zone_list_addr=0x%x" % fn_zone_list_addr

    b = Bunch()
    
    # Walk all fn_zones
    for addr in readList(fn_zone_list_addr, fz_next_off):
        fn_zone = readSU("struct fn_zone", addr)
        b.mask = fn_zone.fz_mask
        hash_head = fn_zone.fz_hash     # This is a pointer to hlist_head
	maxslot = fn_zone.fz_divisor    # Array dimension
        #print 'fn_zone=0x%x, head=0x%x entries=%d maxslot=%d' % \
        #      (Addr(fn_zone),hash_head, fn_zone.fz_nent,  maxslot)
        for i in range(0, maxslot):
            headaddr = long(hash_head) +  i * hlist_head_sz
            first = readSU("struct hlist_head", headaddr).first
            if (not first):
                continue
            for a in readList(first):
                # OK, now we have the fib_node table
                #print "\t", hexl(a)
                f = readSU("struct fib_node", a)
                #fib_alias_head = f.fn_alias.next
                fib_alias_head = Addr(f, "fn_alias")
                prefix = f.fn_key
                #print '-'*20
                for fib_alias_addr in list_for_each_entry(fib_alias_head):
                    fa = readSU("struct fib_alias", fib_alias_addr)
                    fa_info = fa.fa_info
                    #print "\tfib_alias addr", hexl(fib_alias_addr)
                    b.mtu = 0
                    b.dest = prefix
                    if (fa_info):
                        fi = readSU("struct fib_info", fa_info)
                        # Here, at last we have fib_info available
                        if (fi.fib_nh.nh_dev):
                            b.dev = fi.fib_nh.nh_dev.Deref.name
                        else:
                            b.dev = '*'
                        b.gw = fi.fib_nh.nh_gw
                        b.metric = fi.fib_priority
                        fib_advmss = fi.fib_metrics[RTAX.RTAX_ADVMSS-1]
                        if (fib_advmss):
                            b.mtu =  fib_advmss + 40
                        b.flags = fib_flags_trans(fa.fa_type, b.mask, fi)
                    else:
                        # fi = NULL
                        b.flags = fib_flags_trans(fa.fa_type, b.mask, 0)
                        b.gw = 0
                        b.metric = 0
                    yield b


    

def get_fib_v24():
    b = Bunch()                         # A container
    #struct fn_hash *table = (struct fn_hash *) ip_fib_main_table->tb_data;
    RT_TABLE_MAIN = readSymbol("main_rule").r_table
    #print "RT_TABLE_MAIN=",RT_TABLE_MAIN
    fib_tables = readSymbol("fib_tables")
    table_main = readSU("struct fib_table", fib_tables[RT_TABLE_MAIN])
    #     unsigned char tb_data[0];
    
    fn_hash = readSU("struct fn_hash", table_main.tb_data)
    fn_zone_list_addr = fn_hash.fn_zone_list
    fz_next_off = getStructInfo("struct fn_zone")["fz_next"].offset

    if (debug):
        print "fn_zone_list_addr=0x%x" % fn_zone_list_addr
    
    # Walk all fn_zones
    for addr in readList(fn_zone_list_addr, fz_next_off):
        fn_zone = readSU("struct fn_zone", addr)
        mask = fn_zone.fz_mask
        hash_head = fn_zone.fz_hash     # This is a pointer to hlist_head
	maxslot = fn_zone.fz_divisor    # Array dimension
        if (debug):
            print 'fn_zone=0x%x, head=0x%x entries=%d maxslot=%d' % \
                  (Addr(fn_zone),hash_head, fn_zone.fz_nent,  maxslot)
        # Here we have a table of pointers to fib_node
        for i in range(0, maxslot):
            first = readPtr(hash_head + i * sys_info.pointersize)
            if (not first):
                continue
            for a in readList(first):
                f = readSU("struct fib_node", a)
                prefix = f.fn_key.datum
                #print '-'*20
                fi = Deref(f.fn_info)
                # Here, at last we have fib_info available
                if (fi.fib_nh.nh_dev):
                    b.dev = fi.fib_nh.nh_dev.Deref.name
                else:
                    b.dev = '*'
                b.gw = fi.fib_nh.nh_gw
                b.metric = fi.fib_priority
                b.mtu = 0
                fib_advmss = fi.fib_metrics[RTAX.RTAX_ADVMSS-1]
                if (fib_advmss):
                    b.mtu =  fib_advmss + 40
                dead = f.fn_state & FN.FN_S_ZOMBIE
                b.flags = fib_flags_trans(f.fn_type, mask, fi, dead=dead)
                b.dest = prefix
                b.mask = mask
                yield b
                    


# Emulation of enums

FN = CDefine('''
#define FN_S_ZOMBIE	1
#define FN_S_ACCESSED	2
'''
)             

RTN_c = '''
enum
{
	RTN_UNSPEC,
	RTN_UNICAST,		/* Gateway or direct route	*/
	RTN_LOCAL,		/* Accept locally		*/
	RTN_BROADCAST,		/* Accept locally as broadcast,
				   send as broadcast */
	RTN_ANYCAST,		/* Accept locally as broadcast,
				   but send as unicast */
	RTN_MULTICAST,		/* Multicast route		*/
	RTN_BLACKHOLE,		/* Drop				*/
	RTN_UNREACHABLE,	/* Destination is unreachable   */
	RTN_PROHIBIT,		/* Administratively prohibited	*/
	RTN_THROW,		/* Not in this table		*/
	RTN_NAT,		/* Translate this address	*/
	RTN_XRESOLVE,		/* Use external resolver	*/
	__RTN_MAX
};
'''
RTN = CEnum(RTN_c)
RTN_MAX = RTN.__RTN_MAX - 1

RTN_defs = '''
#define	RTF_UP		0x0001		/* route usable		  	*/
#define	RTF_GATEWAY	0x0002		/* destination is a gateway	*/
#define	RTF_HOST	0x0004		/* host entry (net otherwise)	*/
#define RTF_REINSTATE	0x0008		/* reinstate route after tmout	*/
#define	RTF_DYNAMIC	0x0010		/* created dyn. (by redirect)	*/
#define	RTF_MODIFIED	0x0020		/* modified dyn. (by redirect)	*/
#define RTF_MTU		0x0040		/* specific MTU for this route	*/
#define RTF_MSS		RTF_MTU		/* Compatibility :-(		*/
#define RTF_WINDOW	0x0080		/* per route window clamping	*/
#define RTF_IRTT	0x0100		/* Initial round trip time	*/
#define RTF_REJECT	0x0200		/* Reject route			*/
'''

RTF = CDefine(RTN_defs)

def fib_flags_trans(itype, mask, fi, dead = False):
    #     	static unsigned type2flags[RTN_MAX + 1] = {
    # 		[7] = RTF_REJECT, [8] = RTF_REJECT,
    # 	};
    # 	unsigned flags = type2flags[type];
    if (itype == 7 or itype == 8):
        flags = RTF.RTF_REJECT
    else:
        flags = 0
    if (fi and fi.fib_nh.nh_gw):
        flags |= RTF.RTF_GATEWAY
    if (mask == 0xFFFFFFFF):
        flags |= RTF.RTF_HOST;
    if (not dead):
        flags |= RTF.RTF_UP;
    return flags;

# Symbolic flags representation
def flags2str(flags):
    oflags = ''
    if (flags & RTF.RTF_UP):
        oflags += 'U'
    if (flags & RTF.RTF_GATEWAY):
        oflags += 'G'
    if (flags & RTF.RTF_HOST):
        oflags += 'H'
    if (flags & RTF.RTF_REJECT):
        oflags += 'R'
    if (flags & RTF.RTF_DYNAMIC):
        oflags += 'D'
    if (flags & RTF.RTF_MODIFIED):
        oflags += 'M'
    return oflags

RTAX_c = '''
enum
{
	RTAX_UNSPEC,
	RTAX_LOCK,
	RTAX_MTU,
	RTAX_WINDOW,
	RTAX_RTT,
	RTAX_RTTVAR,
	RTAX_SSTHRESH,
	RTAX_CWND,
	RTAX_ADVMSS,
	RTAX_REORDERING,
	RTAX_HOPLIMIT,
	RTAX_INITCWND,
	RTAX_FEATURES,
	__RTAX_MAX
};
'''

RTAX = CEnum(RTAX_c)
