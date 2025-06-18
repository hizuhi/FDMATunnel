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

from gnuradio import analog, blocks, digital, gr

try:
    from gnuradio import pdu
except ImportError:
    # Fallback for older versions
    pdu = blocks

# /////////////////////////////////////////////////////////////////////////////
#                              receive path
# /////////////////////////////////////////////////////////////////////////////


class receive_path(gr.hier_block2):
    def __init__(self, rx_callback, options):
        gr.hier_block2.__init__(
            self,
            "receive_path",
            gr.io_signature(1, 1, gr.sizeof_gr_complex),
            gr.io_signature(0, 0, 0),
        )

        options = copy.copy(options)  # make a copy so we can destructively modify

        self._verbose = options.verbose
        self._log = options.log
        self._rx_callback = (
            rx_callback  # this callback is fired when there's a packet available
        )

        # Modern GNU Radio 3.11 OFDM receiver
        # Convert options to new API parameters
        fft_len = getattr(options, "fft_length", 64)
        cp_len = getattr(options, "cp_length", 16)

        # Create OFDM receiver with default parameters
        self.ofdm_rx = digital.ofdm_rx(
            fft_len=fft_len, cp_len=cp_len, packet_length_tag_key="packet_length"
        )

        # Create callback mechanism for packet reception
        # Convert tagged stream back to packets and call callback
        self.tagged_stream_to_pdu = pdu.tagged_stream_to_pdu(
            gr.types.byte_t, "packet_length"
        )

        # Message sink to handle received packets
        self.msg_sink = blocks.message_debug()

        # Store callback for later use
        self._rx_callback = rx_callback

        # Carrier Sensing Blocks
        alpha = 0.001
        thresh = 30  # in dB, will have to adjust
        self.probe = analog.probe_avg_mag_sqrd_c(thresh, alpha)

        # Connect the flow graph
        # Input -> OFDM RX -> Tagged Stream to PDU (via message port)
        self.connect(self, self.ofdm_rx)

        # Connect OFDM RX output to tagged stream converter
        self.connect(self.ofdm_rx, self.tagged_stream_to_pdu)

        # Connect message port for packet reception
        self.msg_connect(self.tagged_stream_to_pdu, "pdus", self.msg_sink, "store")

        # Connect probe for carrier sensing (using input signal)
        self.connect(self, self.probe)

        # Display some information about the setup
        if self._verbose:
            self._print_verbage()

    def carrier_sensed(self):
        """
        Return True if we think carrier is present.
        """
        # return self.probe.level() > X
        return self.probe.unmuted()

    def carrier_threshold(self):
        """
        Return current setting in dB.
        """
        return self.probe.threshold()

    def set_carrier_threshold(self, threshold_in_db):
        """
        Set carrier threshold.

        Args:
            threshold_in_db: set detection threshold (float (dB))
        """
        self.probe.set_threshold(threshold_in_db)

    def add_options(normal, expert):
        """
        Adds receiver-specific options to the Options Parser
        """
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
            help="Log all parts of flow graph to files (CAUTION: lots of data)",
        )

    # Make a static method to call before instantiation
    add_options = staticmethod(add_options)

    def _print_verbage(self):
        """
        Prints information about the receive path
        """
        pass
