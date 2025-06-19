#!/usr/bin/python3
#
# Copyright 2005,2006,2011 Free Software Foundation, Inc.
#
# This file is part of GNU Radio
#
# GNU Radio is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# GNU Radio is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GNU Radio; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street,
# Boston, MA 02110-1301, USA.
#


# /////////////////////////////////////////////////////////////////////////////
#
#    This code sets up up a virtual ethernet interface (typically gr0),
#    and relays packets between the interface and the GNU Radio PHY+MAC
#
#    What this means in plain language, is that if you've got a couple
#    of USRPs on different machines, and if you run this code on those
#    machines, you can talk between them using normal TCP/IP networking.
#
# /////////////////////////////////////////////////////////////////////////////


import os
import struct
import sys
import threading
import time
from optparse import OptionParser

from gnuradio import eng_notation, gr
from gnuradio.eng_option import eng_option

# from current dir
from receive_path import receive_path
from transmit_path import transmit_path
from uhd_interface import uhd_receiver, uhd_transmitter

from constant_server import *

# print os.getpid()
# raw_input('Attach and press enter')


# /////////////////////////////////////////////////////////////////////////////
#
#   Use the Universal TUN/TAP device driver to move packets to/from kernel
#
#   See /usr/src/linux/Documentation/networking/tuntap.txt
#
# /////////////////////////////////////////////////////////////////////////////


# Linux specific...
# TUNSETIFF ifr flags from <linux/tun_if.h>
def open_tun_interface(tun_device_filename):
    from fcntl import ioctl

    mode = IFF_TUN | IFF_NO_PI

    tun = os.open(tun_device_filename, os.O_RDWR)
    ifs = ioctl(tun, TUNSETIFF, struct.pack("16sH", b"gr%d", mode))
    ifname = ifs[:16].strip(b"\x00").decode("utf-8")
    return tun, ifname


def tun_config(ifname, tun_ip=TUN_IP):
    os.system("ip link set %s up" % ifname)
    os.system("ip addr add %s dev %s" % (tun_ip, ifname))
    os.system(
        "route add -net %s netmask 255.255.255.255 %s"
        % (DEST_ADDRS[TARGET_USER], ifname)
    )


# /////////////////////////////////////////////////////////////////////////////
#                             packet process
# /////////////////////////////////////////////////////////////////////////////


def list2str(l):
    s = list(map(chr, l))
    s = "".join(s)

    return s


def chr2num(ch):
    n = list(map(ord, ch))

    return n


def get_addr(msg):
    # Handle both bytes and string input for Python 3 compatibility
    if isinstance(msg, bytes):
        src_addr = list(msg[12:16])
        dest_addr = list(msg[16:20])
    else:
        src_addr = list(map(ord, msg[12:16]))
        dest_addr = list(map(ord, msg[16:20]))
    return src_addr, dest_addr


def add_header(header, payload):
    header = list2str(header)
    # Ensure consistent data types for concatenation
    if isinstance(payload, bytes):
        header = header.encode("latin-1")
    return header + payload


def parse_header(header):
    # Handle both bytes and string input for Python 3 compatibility
    if isinstance(header, bytes):
        header = list(header)
    else:
        header = list(map(ord, header))

    pkt_cnt = header[0]
    src_addr = header[1:5]
    dest_addr = header[5:9]
    control = header[-1]

    return pkt_cnt, src_addr, dest_addr, control


# /////////////////////////////////////////////////////////////////////////////
#                             the flow graph
# /////////////////////////////////////////////////////////////////////////////


class my_top_block(gr.top_block):
    def __init__(self, callback, options):
        gr.top_block.__init__(self)

        self.source = uhd_receiver(
            options.args,
            options.bandwidth,
            options.rx_freq,
            options.lo_offset,
            options.rx_gain,
            options.spec,
            options.antenna,
            options.clock_source,
            options.verbose,
        )

        self.sink = uhd_transmitter(
            options.args,
            options.bandwidth,
            options.tx_freq,
            options.lo_offset,
            options.tx_gain,
            options.spec,
            options.antenna,
            options.clock_source,
            options.verbose,
        )

        self.txpath = transmit_path(options)
        self.rxpath = receive_path(callback, options)

        self.connect(self.txpath, self.sink)
        self.connect(self.source, self.rxpath)

    def carrier_sensed(self):
        """
        Return True if the receive path thinks there's carrier
        """
        return self.rxpath.carrier_sensed()

    def set_freq(self, target_freq):
        """
        Set the center frequency we're interested in.
        """
        self.u_snk.set_freq(target_freq)
        self.u_src.set_freq(target_freq)

    def set_bandwidth(self, bandwidth):
        """
        set usrp tx/rx bandwidth
        """
        self.lock()
        self.sink.u.set_samp_rate(bandwidth)
        self.source.u.set_samp_rate(bandwidth)
        self.unlock()


# /////////////////////////////////////////////////////////////////////////////
#                           Carrier Sense MAC
# /////////////////////////////////////////////////////////////////////////////


class cs_mac(object):
    """
    Prototype carrier sense MAC

    Reads packets from the TUN/TAP interface, and sends them to the PHY.
    Receives packets from the PHY via phy_rx_callback, and sends them
    into the TUN/TAP interface.

    Of course, we're not restricted to getting packets via TUN/TAP, this
    is just an example.
    """

    def __init__(
        self,
        tun_fd,
        verbose=False,
    ):
        self.tun_fd = tun_fd  # file descriptor for TUN/TAP interface
        self.verbose = verbose
        self.tb = None  # top block (access to PHY)
        self.tx_time = -1

        self.src_addr = [int(s) for s in SRC_ADDR.split(".")]
        self.dest_addr = [int(s) for s in DEST_ADDRS[TARGET_USER].split(".")]

        self.tx_id = 0
        self.tx_pdu = None

        self.last_rx_id = -1
        self.recv_ack = 1

        self.timer = None
        self.lock = threading.Lock()

    def arq_fsm(self):
        with self.lock:
            self.main_loop()

    def set_flow_graph(self, tb):
        self.tb = tb

    def rx_change_bandwidth(self, control):
        """
        TO DO
        """
        return False

    def rx_ack(self, control):
        if control == CTL_ACK:
            return True
        return False

    def rx_dummy(self, pkt_cnt, src_addr):
        """
        TODO
        """
        return False

    def tx_change_bandwidth(self, payload):
        """
        TO DO
        """
        return False

    def tx_accept_pkt(self, dest_addr):
        """
        TODO
        """
        if dest_addr == self.dest_addr:
            return True
        return False

    def tx_process(self, payload, dest_addr):
        """TODO"""
        return payload

    def tx_to_server(self, dest_addr):
        """TODO"""
        return True

    def tx_ack(self, pkt_cnt, dest_addr):
        header = [pkt_cnt] + self.src_addr + dest_addr + [CTL_ACK]
        payload = "ACKACKACKTHISISACK"
        data = add_header(header, payload)

        self.tb.txpath.send_pkt(data)

    def phy_rx_callback(self, ok, payload):
        """
        Invoked by thread associated with PHY to pass received packet up.

        Args:
            ok: bool indicating whether payload CRC was OK
            payload: contents of the packet (string)
        """
        if self.verbose:
            print("Rx: ok = %r  len(payload) = %4d\n\n" % (ok, len(payload)))
        if ok:
            header = payload[0:HEADER_LEN]
            data = payload[HEADER_LEN:]

            pkt_cnt, src_addr, dest_addr, control = parse_header(header)
            if DEBUG:
                print("[DEBUG] dest_addr", dest_addr)

            if dest_addr == self.src_addr:
                if DEBUG:
                    print("[DEBUG] Data for me! pkt no: %d" % pkt_cnt)
                    print("[DEBUG] Recv time: %.6f" % time.time())

                discard = False

                # which kind of pkt?
                if self.rx_change_bandwidth(control):  # it's a control pkt
                    """
                        change bandwidth
                        TODO
                    """
                    if DEBUG:
                        print("[DEBUG] recv change bandwidth pkt")
                    discard = True

                elif self.rx_ack(control):  # it's a ack pkt
                    if DEBUG:
                        print("[DEBUG] recv ack data")
                    discard = True
                    # it's  a correct ack data
                    if pkt_cnt == self.tx_id:
                        with self.lock:
                            self.timer.cancel()
                            self.recv_ack = 1
                            self.tx_id = (self.tx_id + 1) % 256
                            threading.Thread(target=self.arq_fsm)

                else:  # it's a norm pkt
                    # it's dump, we discard it, but still send ack
                    if pkt_cnt == self.last_rx_id:
                        if DEBUG:
                            print("[DEBUG] Recv dump pkt!")
                        discard = True
                    else:
                        self.last_rx_id = pkt_cnt
                    # send ack
                    self.tx_ack(pkt_cnt, dest_addr)

                if not discard:
                    # Ensure data is bytes for os.write
                    if isinstance(data, str):
                        data = data.encode("latin-1")
                    os.write(self.tun_fd, data)

    def main_loop(self):
        """
        Main loop for MAC.
        Only returns if we get an error reading from TUN.

        FIXME: may want to check for EINTR and EAGAIN and reissue read
        """
        # min_delay = 0.001               # seconds

        # if we have recv ack, we can get next pkt
        if self.recv_ack:
            while 1:
                payload = os.read(self.tun_fd, 10 * 1024)
                src_addr, dest_addr = get_addr(payload)

                if not payload:  # something goes wrong
                    self.tb.txpath.send_pkt(eof=True)
                    return

                # should I trans this pkt?
                if self.tx_accept_pkt(dest_addr):
                    control = CTL_NORM
                    pkt_cnt = self.tx_id

                    # it's a control pkt?
                    if self.tx_change_bandwidth(payload):
                        """
                        change bandwidth 
                        TODO
                        """
                        control = CTL_CHANGE_BW

                    # pkt process: add header et.
                    header = [pkt_cnt] + src_addr + dest_addr + [control]
                    self.tx_pdu = add_header(header, payload)
                    break

        # trans data
        if self.verbose:
            print("Send time: %.6f" % time.time())

        self.tb.txpath.send_pkt(self.tx_pdu)
        self.recv_ack = 0
        # self.tb.txpath.send_pkt(data)

        if self.verbose:
            print("Tx: len(payload) = %4d" % (len(payload),))

        self.timer = threading.Timer(WAIT_INTERVAL, self.arq_fsm)

        """ 
        CSMA part

        delay = min_delay
        while self.tb.carrier_sensed():
            sys.stderr.write('B')
            time.sleep(delay)
            if delay < 0.050:
                delay = delay * 2       # exponential back-off

        self.tx_time = time.time()
        """


# /////////////////////////////////////////////////////////////////////////////
#                                   main
# /////////////////////////////////////////////////////////////////////////////
TARGET_USER = -1


def main():
    users = [str(i) for i in range(NUM_USRP)]

    parser = OptionParser(option_class=eng_option, conflict_handler="resolve")
    expert_grp = parser.add_option_group("Expert")

    parser.add_option(
        "--target",
        type="string",
        default="",
        help="Which user to communicate:0,1,2... [default=%%default]",
    )

    parser.add_option(
        "-m",
        "--modulation",
        type="choice",
        choices=["bpsk", "qpsk"],
        default="bpsk",
        help="Select modulation from: bpsk, qpsk [default=%%default]",
    )

    parser.add_option("-v", "--verbose", action="store_true", default=False)
    expert_grp.add_option(
        "-c",
        "--carrier-threshold",
        type="eng_float",
        default=30,
        help="set carrier detect threshold (dB) [default=%default]",
    )
    expert_grp.add_option(
        "",
        "--tun-device-filename",
        default="/dev/net/tun",
        help="path to tun device file [default=%default]",
    )

    # Modern GNU Radio 3.11 OFDM modules don't have add_options methods
    # OFDM parameters are now configured directly in transmit/receive paths
    expert_grp.add_option(
        "",
        "--fft-length",
        type="int",
        default=64,
        help="set OFDM FFT length [default=%default]",
    )
    expert_grp.add_option(
        "",
        "--cp-length",
        type="int",
        default=16,
        help="set OFDM cyclic prefix length [default=%default]",
    )
    transmit_path.add_options(parser, expert_grp)
    receive_path.add_options(parser, expert_grp)
    uhd_receiver.add_options(parser)
    uhd_transmitter.add_options(parser)

    (options, args) = parser.parse_args()
    if len(args) != 0:
        parser.print_help(sys.stderr)
        sys.exit(1)

    if options.target not in users:
        print("Error: You must specify correct target user!")
        parser.print_help(sys.stderr)
        sys.exit(1)

    """
        if options.rx_freq is None or options.tx_freq is None:
        sys.stderr.write("You must specify -f FREQ or --freq FREQ\n")
        parser.print_help(sys.stderr)
        sys.exit(1)
    """

    global TARGET_USER
    TARGET_USER = int(options.target)

    # open the TUN/TAP interface
    (tun_fd, tun_ifname) = open_tun_interface(options.tun_device_filename)
    tun_config(tun_ifname)

    # Attempt to enable realtime scheduling
    r = gr.enable_realtime_scheduling()
    if r == gr.RT_OK:
        realtime = True
    else:
        realtime = False
        print("Note: failed to enable realtime scheduling")

    # instantiate the MAC
    mac = cs_mac(tun_fd, verbose=True)

    # build the graph (PHY)
    options.bandwidth = BAND_USRPS[TARGET_USER]
    options.tx_freq = TXFREQ_USRPS[TARGET_USER]
    options.rx_freq = RXFREQ_USRPS[TARGET_USER]
    options.args = ADDR_USRPS[TARGET_USER]
    tb = my_top_block(mac.phy_rx_callback, options)

    mac.set_flow_graph(tb)  # give the MAC a handle for the PHY

    print("modulation:     %s" % (options.modulation,))
    print("freq:           %s" % (eng_notation.num_to_str(options.tx_freq)))

    tb.rxpath.set_carrier_threshold(options.carrier_threshold)
    print("Carrier sense threshold:", options.carrier_threshold, "dB")

    print()
    print("Allocated virtual ethernet interface: %s" % (tun_ifname,))
    print("You must now use ifconfig to set its IP address. E.g.,")
    print()
    print("  $ sudo ifconfig %s 192.168.200.1" % (tun_ifname,))
    print()
    print("Be sure to use a different address in the same subnet for each machine.")
    print()

    tb.start()  # Start executing the flow graph (runs in separate threads)

    threading.Thread(target=mac.arq_fsm).start()
    # mac.main_loop()    # don't expect this to return...

    # tb.stop()     # but if it does, tell flow graph to stop.
    tb.wait()  # wait for it to finish


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
