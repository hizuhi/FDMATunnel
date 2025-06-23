#!/usr/bin/env python3
"""
FDMA Tunnel Debug Test Program
系统性诊断程序，用于定位ping不通的根本原因
"""

import os
import subprocess
import sys

# Add current directory to path
sys.path.append(".")


def test_imports():
    """测试1: 检查所有必要的模块导入"""
    print("=" * 60)
    print("测试1: 模块导入检查")
    print("=" * 60)

    try:
        print("✅ GNU Radio 基础模块导入成功")

        # 检查GNU Radio版本
        import gnuradio

        version = getattr(gnuradio, "version", "unknown")
        print(f"✅ GNU Radio 版本: {version}")

    except Exception as e:
        print(f"❌ GNU Radio 导入失败: {e}")
        return False

    try:
        print("✅ transmit_path 导入成功")
    except Exception as e:
        print(f"❌ transmit_path 导入失败: {e}")
        return False

    try:
        print("✅ receive_path 导入成功")
    except Exception as e:
        print(f"❌ receive_path 导入失败: {e}")
        return False

    try:
        print("✅ UHD 接口导入成功")
    except Exception as e:
        print(f"❌ UHD 接口导入失败: {e}")
        return False

    try:
        import constant_server

        print("✅ 服务器常量导入成功")
        print(f"   SRC_ADDR: {constant_server.SRC_ADDR}")
        print(f"   DEST_ADDRS: {constant_server.DEST_ADDRS}")
        print(f"   TXFREQ_USRPS: {constant_server.TXFREQ_USRPS}")
        print(f"   RXFREQ_USRPS: {constant_server.RXFREQ_USRPS}")
    except Exception as e:
        print(f"❌ 服务器常量导入失败: {e}")
        return False

    return True


def test_flowgraph_creation():
    """测试2: 检查流图创建"""
    print("\n" + "=" * 60)
    print("测试2: 流图创建检查")
    print("=" * 60)

    try:
        # 创建模拟选项
        class MockOptions:
            def __init__(self):
                self.verbose = True
                self.tx_amplitude = 0.1
                self.fft_length = 64
                self.cp_length = 16
                self.log = False
                self.bandwidth = 25e3
                self.tx_freq = 25e6
                self.rx_freq = 20e6
                self.args = "addr=192.168.10.2"
                self.lo_offset = None
                self.tx_gain = None
                self.rx_gain = None
                self.spec = None
                self.antenna = None
                self.clock_source = None

        options = MockOptions()

        # 测试发送路径
        print("创建发送路径...")
        tx_path = transmit_path(options)
        print("✅ 发送路径创建成功")

        # 测试接收路径
        print("创建接收路径...")

        def dummy_callback(ok, payload):
            print(f"接收回调: ok={ok}, len={len(payload) if payload else 0}")

        rx_path = receive_path(dummy_callback, options)
        print("✅ 接收路径创建成功")

        # 测试send_pkt方法
        print("测试数据包发送...")
        result = tx_path.send_pkt("test packet")
        print(f"✅ send_pkt 返回: {result}")

        return True

    except Exception as e:
        print(f"❌ 流图创建失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_tun_interface():
    """测试3: 检查TUN接口创建和配置"""
    print("\n" + "=" * 60)
    print("测试3: TUN接口检查")
    print("=" * 60)

    try:
        from tunnel_server import open_tun_interface, tun_config

        # 检查是否有root权限
        if os.geteuid() != 0:
            print("❌ 需要root权限来创建TUN接口")
            print("   请使用: sudo python3 debug_test.py")
            return False

        print("创建TUN接口...")
        tun_fd, tun_ifname = open_tun_interface("/dev/net/tun")
        print(f"✅ TUN接口创建成功: {tun_ifname}")

        print("配置TUN接口...")
        tun_config(tun_ifname)
        print("✅ TUN接口配置成功")

        # 检查接口状态
        result = subprocess.run(
            ["ip", "addr", "show", tun_ifname], capture_output=True, text=True
        )
        if result.returncode == 0:
            print("✅ TUN接口状态:")
            print(result.stdout)
        else:
            print(f"❌ 无法获取TUN接口状态: {result.stderr}")

        # 检查路由
        result = subprocess.run(["ip", "route", "show"], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ 当前路由表:")
            for line in result.stdout.split("\n"):
                if "10.0.0" in line or tun_ifname in line:
                    print(f"   {line}")

        os.close(tun_fd)
        return True

    except Exception as e:
        print(f"❌ TUN接口测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_usrp_connection():
    """测试4: 检查USRP连接"""
    print("\n" + "=" * 60)
    print("测试4: USRP连接检查")
    print("=" * 60)

    try:
        from uhd_interface import uhd_receiver, uhd_transmitter

        # 测试USRP连接参数
        args = "addr=192.168.10.2"
        bandwidth = 25e3
        tx_freq = 25e6
        rx_freq = 20e6

        print("测试USRP连接参数:")
        print(f"   地址: {args}")
        print(f"   带宽: {bandwidth}")
        print(f"   发送频率: {tx_freq}")
        print(f"   接收频率: {rx_freq}")

        # 尝试创建USRP接收器
        print("创建USRP接收器...")
        try:
            rx = uhd_receiver(
                args, bandwidth, rx_freq, None, None, None, None, None, True
            )
            print("✅ USRP接收器创建成功")
        except Exception as e:
            print(f"❌ USRP接收器创建失败: {e}")
            return False

        # 尝试创建USRP发送器
        print("创建USRP发送器...")
        try:
            tx = uhd_transmitter(
                args, bandwidth, tx_freq, None, None, None, None, None, True
            )
            print("✅ USRP发送器创建成功")
        except Exception as e:
            print(f"❌ USRP发送器创建失败: {e}")
            return False

        return True

    except Exception as e:
        print(f"❌ USRP连接测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_packet_flow():
    """测试5: 检查数据包流程"""
    print("\n" + "=" * 60)
    print("测试5: 数据包流程检查")
    print("=" * 60)

    try:
        from tunnel_server import add_header, parse_header

        # 测试数据包头部处理
        print("测试数据包头部处理...")

        # 创建测试数据包
        pkt_cnt = 1
        src_addr = [10, 0, 0, 1]
        dest_addr = [10, 0, 0, 2]
        control = 0
        payload = b"Hello, World!"

        # 测试添加头部
        header = [pkt_cnt] + src_addr + dest_addr + [control]
        packet_with_header = add_header(header, payload)
        print(f"✅ 添加头部成功, 数据包长度: {len(packet_with_header)}")

        # 测试解析头部
        parsed_header = packet_with_header[:10]  # HEADER_LEN = 10
        parsed_pkt_cnt, parsed_src, parsed_dest, parsed_ctrl = parse_header(
            parsed_header
        )

        print("✅ 头部解析成功:")
        print(f"   包计数: {parsed_pkt_cnt}")
        print(f"   源地址: {parsed_src}")
        print(f"   目标地址: {parsed_dest}")
        print(f"   控制字: {parsed_ctrl}")

        # 验证解析结果
        if (
            parsed_pkt_cnt == pkt_cnt
            and parsed_src == src_addr
            and parsed_dest == dest_addr
            and parsed_ctrl == control
        ):
            print("✅ 头部解析验证成功")
        else:
            print("❌ 头部解析验证失败")
            return False

        return True

    except Exception as e:
        print(f"❌ 数据包流程测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("FDMA Tunnel 系统诊断程序")
    print("=" * 60)

    # 运行所有测试
    tests = [
        ("模块导入", test_imports),
        ("流图创建", test_flowgraph_creation),
        ("TUN接口", test_tun_interface),
        ("USRP连接", test_usrp_connection),
        ("数据包流程", test_packet_flow),
    ]

    results = {}

    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ 测试 '{test_name}' 异常: {e}")
            results[test_name] = False

    # 输出测试总结
    print("\n" + "=" * 60)
    print("测试结果总结")
    print("=" * 60)

    for test_name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name:15} : {status}")

    # 给出诊断建议
    print("\n" + "=" * 60)
    print("诊断建议")
    print("=" * 60)

    if not results.get("模块导入", False):
        print("🔧 建议: 检查GNU Radio安装和Python路径")
    elif not results.get("流图创建", False):
        print("🔧 建议: 检查transmit_path和receive_path实现")
    elif not results.get("TUN接口", False):
        print("🔧 建议: 检查root权限和TUN/TAP驱动")
    elif not results.get("USRP连接", False):
        print("🔧 建议: 检查USRP硬件连接和网络配置")
    elif not results.get("数据包流程", False):
        print("🔧 建议: 检查数据包处理逻辑")
    else:
        print("🎯 所有基础测试通过，问题可能在于:")
        print("   1. OFDM调制解调参数不匹配")
        print("   2. 射频信号传输问题")
        print("   3. 时序同步问题")
        print("   4. 功率或增益设置问题")


if __name__ == "__main__":
    main()
