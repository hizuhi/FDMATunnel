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

import numpy as np
from gnuradio import analog, digital, gr


class callback_sink(gr.sync_block):
    """
    自定义 sink，直接调用回调函数处理接收到的数据包
    替代复杂的 vector_sink + 轮询机制
    """

    def __init__(self, callback_func):
        gr.sync_block.__init__(
            self,
            name="callback_sink",
            in_sig=[np.uint8],  # 输入字节流
            out_sig=None,  # 无输出
        )
        self.callback_func = callback_func

    def work(self, input_items, output_items):
        """
        处理输入数据并调用回调函数
        """
        in0 = input_items[0]

        if len(in0) > 0 and self.callback_func:
            # 将 numpy 数组转换为 bytes
            data = bytes(in0)
            # 直接调用回调函数
            self.callback_func(True, data)

        return len(in0)


# /////////////////////////////////////////////////////////////////////////////
#                              receive path
# /////////////////////////////////////////////////////////////////////////////


class receive_path(gr.hier_block2):
    def __init__(self, rx_callback, options):  # 恢复 rx_callback 参数
        gr.hier_block2.__init__(
            self,
            "receive_path",
            gr.io_signature(1, 1, gr.sizeof_gr_complex),
            gr.io_signature(0, 0, 0),  # 无输出，使用内部 callback sink
        )

        options = copy.copy(options)

        self._verbose = options.verbose
        self._log = options.log
        self._rx_callback = rx_callback

        print("[DEBUG] Using simplified OFDM receiver with direct callback")

        # Convert options to new API parameters
        fft_len = getattr(options, "fft_length", 64)
        cp_len = getattr(options, "cp_length", 16)

        # Carrier Sensing Blocks
        alpha = 0.001
        thresh = 30
        self.probe = analog.probe_avg_mag_sqrd_c(thresh, alpha)

        # Create modern OFDM receiver
        # self.ofdm_rx = digital.ofdm_rx(
        #     fft_len=fft_len,
        #     cp_len=cp_len,
        #     packet_length_tag_key="packet_length",
        # )

        self.ofdm_rx = digital.ofdm_rx(
            fft_len=fft_len,
            cp_len=(fft_len // 4),
            frame_length_tag_key="frame_" + "rx_len",
            packet_length_tag_key="rx_len",
            occupied_carriers=((-4, -3, -2, -1, 1, 2, 3, 4),),
            pilot_carriers=((-6, -5, 5, 6),),
            pilot_symbols=((-1, 1, -1, 1),),
            sync_word1=None,
            sync_word2=None,
            bps_header=1,
            bps_payload=2,
            debug_log=False,
            scramble_bits=False,
        )

        # Create callback sink
        self.callback_sink = callback_sink(rx_callback)

        # Simple connection: input -> OFDM -> callback_sink
        self.connect(self, self.ofdm_rx)
        self.connect(self.ofdm_rx, self.callback_sink)

        # Connect probe to input for carrier sensing
        self.connect(self, self.probe)

        print("[DEBUG] Simplified OFDM path with callback sink connected successfully")

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
