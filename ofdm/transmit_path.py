#!/usr/bin/python3
#
# Copyright 2005,2006,2011 Free Software Foundation, Inc.
#
# This file is part of GNU Radio
#
# GNU Radio is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
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

import copy

from gnuradio import blocks, digital, gr

try:
    from gnuradio import pdu
except ImportError:
    # Fallback for older versions
    pdu = blocks

# /////////////////////////////////////////////////////////////////////////////
#                              transmit path
# /////////////////////////////////////////////////////////////////////////////


class transmit_path(gr.hier_block2):
    def __init__(self, options):
        """
        See below for what options should hold
        """

        gr.hier_block2.__init__(
            self,
            "transmit_path",
            gr.io_signature(0, 0, 0),
            gr.io_signature(1, 1, gr.sizeof_gr_complex),
        )

        options = copy.copy(options)  # make a copy so we can destructively modify

        self._verbose = options.verbose  # turn verbose mode on/off
        self._tx_amplitude = options.tx_amplitude  # digital amp sent to radio

        # Modern GNU Radio 3.11 OFDM transmitter
        # Convert options to new API parameters
        fft_len = getattr(options, "fft_length", 64)
        cp_len = getattr(options, "cp_length", 16)

        # Create packet transmission using message queue approach
        # This is more reliable for GNU Radio 3.11
        import queue

        self.packet_queue = queue.Queue()

        # Use null source initially, will be replaced dynamically
        self.packet_source = blocks.vector_source_b([], False, 1, [])

        # Add stream to tagged stream converter for packet framing
        self.stream_to_tagged_stream = blocks.stream_to_tagged_stream(
            gr.sizeof_char, 1, 1, "packet_length"
        )

        # Create OFDM transmitter with default parameters
        self.ofdm_tx = digital.ofdm_tx(
            fft_len=fft_len, cp_len=cp_len, packet_length_tag_key="packet_length"
        )

        self.amp = blocks.multiply_const_cc(1)
        self.set_tx_amplitude(self._tx_amplitude)

        # Display some information about the setup
        if self._verbose:
            self._print_verbage()

        # Create and setup transmit path flow graph
        self.connect(
            self.packet_source,
            self.stream_to_tagged_stream,
            self.ofdm_tx,
            self.amp,
            self,
        )

    def set_tx_amplitude(self, ampl):
        """
        Sets the transmit amplitude sent to the USRP

        Args:
            : ampl 0 <= ampl < 1.0.  Try 0.10
        """
        self._tx_amplitude = max(0.0, min(ampl, 1))
        self.amp.set_k(self._tx_amplitude)

    def send_pkt(self, payload="", eof=False):
        """
        Sends a packet through the OFDM transmitter
        Compatible interface with old GNU Radio API
        """
        if eof:
            # Handle end-of-file case
            return True

        if isinstance(payload, str):
            # Convert string to bytes for Python 3 compatibility
            payload = payload.encode("latin-1")
        elif payload is None:
            payload = b""

        # Convert payload to list of integers
        data = list(payload) if payload else []

        if data:
            # Set packet length for tagged stream
            self.stream_to_tagged_stream.set_packet_len(len(data))

            # Create new vector source with the packet data
            # This is a workaround for GNU Radio 3.11
            self.packet_source.set_data(data, [])

        return True

    def add_options(normal, expert):
        """
        Adds transmitter-specific options to the Options Parser
        """
        normal.add_option(
            "",
            "--tx-amplitude",
            type="eng_float",
            default=0.1,
            metavar="AMPL",
            help="set transmitter digital amplitude: 0 <= AMPL < 1.0 [default=%default]",
        )
        normal.add_option(
            "-W",
            "--bandwidth",
            type="eng_float",
            default=500e3,
            help="set symbol bandwidth [default=%default]",
        )
        normal.add_option("-v", "--verbose", action="store_true", default=False)
        expert.add_option(
            "",
            "--log",
            action="store_true",
            default=False,
            help="Log all parts of flow graph to file (CAUTION: lots of data)",
        )

    # Make a static method to call before instantiation
    add_options = staticmethod(add_options)

    def _print_verbage(self):
        """
        Prints information about the transmit path
        """
        print("Tx amplitude     %s" % (self._tx_amplitude))
