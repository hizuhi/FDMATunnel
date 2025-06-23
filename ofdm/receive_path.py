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

import pmt
from gnuradio import analog, blocks, digital, gr

# GNU Radio version compatibility layer
try:
    from gnuradio import pdu

    PDU_AVAILABLE = True
except ImportError:
    # Fallback for older versions
    pdu = blocks
    PDU_AVAILABLE = False

# Detect GNU Radio version for compatibility
try:
    # Try to get version info
    import gnuradio

    GR_VERSION = getattr(gnuradio, "version", "3.8")
    print(f"[DEBUG] GNU Radio version: {GR_VERSION}")
except:
    GR_VERSION = "3.8"

# Version-specific compatibility flags
USE_LEGACY_OFDM = GR_VERSION.startswith("3.8") or GR_VERSION.startswith("3.9")
USE_NEW_PDU = GR_VERSION.startswith("3.11") and PDU_AVAILABLE


class packet_callback_handler(gr.basic_block):
    """
    Custom message handler for GNU Radio 3.11 OFDM receiver
    Converts PDU messages back to callback function calls for compatibility
    """

    def __init__(self, callback_func):
        gr.basic_block.__init__(
            self, name="packet_callback_handler", in_sig=None, out_sig=None
        )

        self.callback_func = callback_func
        self.message_port_register_in(pmt.intern("pdus"))
        self.set_msg_handler(pmt.intern("pdus"), self.handle_msg)

    def handle_msg(self, msg):
        """
        Handle incoming PDU messages and convert to callback
        """
        try:
            # Extract the PDU data
            if pmt.is_pair(msg):
                meta = pmt.car(msg)
                data = pmt.cdr(msg)

                # Convert PMT vector to bytes
                if pmt.is_u8vector(data):
                    payload = bytes(pmt.u8vector_elements(data))
                    print(f"[DEBUG] Received packet: len={len(payload)}")
                    # Call the original callback with ok=True and payload
                    if self.callback_func:
                        self.callback_func(True, payload)
                else:
                    # Invalid data format
                    print("[DEBUG] Invalid data format in PDU")
                    if self.callback_func:
                        self.callback_func(False, b"")
            else:
                # Invalid message format
                print("[DEBUG] Invalid message format")
                if self.callback_func:
                    self.callback_func(False, b"")

        except Exception as e:
            # Error in message processing
            print(f"Error in packet callback handler: {e}")
            if self.callback_func:
                self.callback_func(False, b"")


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

        # Create version-compatible OFDM receiver
        if USE_LEGACY_OFDM:
            print("[DEBUG] Using legacy OFDM demodulator (3.8/3.9 style)")
            # For GNU Radio 3.8/3.9 - use old API with direct callback
            try:
                self.ofdm_rx = digital.ofdm_demod(options, callback=rx_callback)
                self.use_direct_callback = True
                self.use_pdu_conversion = False
            except Exception as e:
                print(f"[DEBUG] Legacy OFDM failed: {e}, falling back to new API")
                self.ofdm_rx = digital.ofdm_rx(
                    fft_len=fft_len,
                    cp_len=cp_len,
                    packet_length_tag_key="packet_length",
                )
                self.use_direct_callback = False
                self.use_pdu_conversion = True
        else:
            print("[DEBUG] Using modern OFDM receiver (3.10+ style)")
            # For GNU Radio 3.10+ - use new API
            self.ofdm_rx = digital.ofdm_rx(
                fft_len=fft_len, cp_len=cp_len, packet_length_tag_key="packet_length"
            )
            self.use_direct_callback = False
            self.use_pdu_conversion = True

        # Create callback handler for modern versions
        if not self.use_direct_callback:
            self.callback_handler = packet_callback_handler(rx_callback)

            # Try to use PDU conversion if available
            if self.use_pdu_conversion:
                try:
                    if USE_NEW_PDU:
                        self.tagged_stream_to_pdu = pdu.tagged_stream_to_pdu(
                            gr.types.byte_t, "packet_length"
                        )
                    else:
                        self.tagged_stream_to_pdu = blocks.tagged_stream_to_pdu(
                            gr.types.byte_t, "packet_length"
                        )
                    print("[DEBUG] PDU conversion available")
                except Exception as e:
                    print(f"[DEBUG] PDU conversion failed: {e}")
                    self.use_pdu_conversion = False

        # Store callback for later use
        self._rx_callback = rx_callback

        # Carrier Sensing Blocks
        alpha = 0.001
        thresh = 30  # in dB, will have to adjust
        self.probe = analog.probe_avg_mag_sqrd_c(thresh, alpha)

        # Connect the flow graph based on version compatibility
        self.connect(self, self.ofdm_rx)

        # Version-specific connections
        if self.use_direct_callback:
            print("[DEBUG] Using direct callback (legacy mode)")
            # For legacy versions, OFDM demod handles callback directly
            # Just connect to probe for carrier sensing
            self.connect(self.ofdm_rx, self.probe)
        else:
            print("[DEBUG] Using message-based callback (modern mode)")
            # Add a null sink to handle OFDM RX output
            self.null_sink = blocks.null_sink(gr.sizeof_char)

            # Connect OFDM RX output - try different approaches
            if self.use_pdu_conversion and hasattr(self, "tagged_stream_to_pdu"):
                try:
                    # Try to connect to PDU converter
                    self.connect(self.ofdm_rx, self.tagged_stream_to_pdu)
                    # Connect message port for packet reception
                    self.msg_connect(
                        self.tagged_stream_to_pdu, "pdus", self.callback_handler, "pdus"
                    )
                    print("[DEBUG] Using PDU conversion path")
                except Exception as e:
                    print(f"[DEBUG] PDU connection failed: {e}")
                    # Fallback to null sink
                    self.connect(self.ofdm_rx, self.null_sink)
            else:
                # Direct connection to null sink
                self.connect(self.ofdm_rx, self.null_sink)
                print("[DEBUG] Using null sink fallback")

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
