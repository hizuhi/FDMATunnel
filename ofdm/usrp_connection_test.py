#!/usr/bin/env python3
"""
USRP连接专项测试
"""

import subprocess
import sys
import time

def run_command(cmd, timeout=10):
    """运行命令并返回结果"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, 
                              text=True, timeout=timeout)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "命令超时"

def test_network_connectivity():
    """测试网络连接"""
    print("=" * 60)
    print("测试1: 网络连接检查")
    print("=" * 60)
    
    # 检查网络接口
    print("检查网络接口...")
    ret, out, err = run_command("ip addr show")
    if ret == 0:
        for line in out.split('\n'):
            if '192.168.10' in line or 'eth' in line or 'enp' in line:
                print(f"  {line.strip()}")
    
    # Ping USRP
    print(f"\nPing USRP (192.168.10.2)...")
    ret, out, err = run_command("ping -c 3 192.168.10.2", timeout=15)
    if ret == 0:
        print("✅ USRP网络连接正常")
        print(out)
    else:
        print("❌ USRP网络连接失败")
        print(f"错误: {err}")
        return False
    
    return True

def test_uhd_detection():
    """测试UHD设备检测"""
    print("\n" + "=" * 60)
    print("测试2: UHD设备检测")
    print("=" * 60)
    
    # 通用设备扫描
    print("扫描所有UHD设备...")
    ret, out, err = run_command("uhd_find_devices", timeout=20)
    print(f"返回码: {ret}")
    if out:
        print("输出:")
        print(out)
    if err:
        print("错误:")
        print(err)
    
    # 特定IP设备检测
    print(f"\n检测特定USRP (192.168.10.2)...")
    ret, out, err = run_command('uhd_find_devices --args="addr=192.168.10.2"', timeout=20)
    print(f"返回码: {ret}")
    if out:
        print("输出:")
        print(out)
    if err:
        print("错误:")
        print(err)
    
    if ret == 0 and "192.168.10.2" in out:
        print("✅ USRP设备检测成功")
        return True
    else:
        print("❌ USRP设备检测失败")
        return False

def test_usrp_probe():
    """测试USRP探测"""
    print("\n" + "=" * 60)
    print("测试3: USRP设备探测")
    print("=" * 60)
    
    print("探测USRP设备信息...")
    ret, out, err = run_command('uhd_usrp_probe --args="addr=192.168.10.2"', timeout=30)
    print(f"返回码: {ret}")
    
    if ret == 0:
        print("✅ USRP探测成功")
        # 提取关键信息
        lines = out.split('\n')
        for line in lines:
            if any(keyword in line.lower() for keyword in 
                   ['device', 'mboard', 'rx', 'tx', 'freq', 'rate']):
                print(f"  {line.strip()}")
        return True
    else:
        print("❌ USRP探测失败")
        if out:
            print("输出:")
            print(out)
        if err:
            print("错误:")
            print(err)
        return False

def test_gnuradio_usrp():
    """测试GNU Radio USRP模块"""
    print("\n" + "=" * 60)
    print("测试4: GNU Radio USRP模块")
    print("=" * 60)
    
    try:
        from gnuradio import uhd
        print("✅ GNU Radio UHD模块导入成功")
        
        # 尝试创建USRP source
        print("创建USRP source...")
        usrp_source = uhd.usrp_source(
            ",".join(("addr=192.168.10.2",)),
            uhd.stream_args(
                cpu_format="fc32",
                channels=range(1),
            ),
        )
        print("✅ USRP source创建成功")
        
        # 设置参数
        print("设置USRP参数...")
        usrp_source.set_samp_rate(25000)
        usrp_source.set_center_freq(20e6, 0)
        print("✅ USRP参数设置成功")
        
        return True
        
    except Exception as e:
        print(f"❌ GNU Radio USRP测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_firewall_and_permissions():
    """测试防火墙和权限"""
    print("\n" + "=" * 60)
    print("测试5: 防火墙和权限检查")
    print("=" * 60)
    
    # 检查防火墙状态
    print("检查防火墙状态...")
    ret, out, err = run_command("sudo ufw status")
    if ret == 0:
        print(f"防火墙状态: {out.strip()}")
    
    # 检查用户组
    print("检查用户组...")
    ret, out, err = run_command("groups")
    if ret == 0:
        groups = out.strip()
        print(f"当前用户组: {groups}")
        if 'usrp' in groups or 'dialout' in groups:
            print("✅ 用户组权限正常")
        else:
            print("⚠️  可能需要添加到usrp或dialout组")
    
    # 检查网络配置
    print("检查网络路由...")
    ret, out, err = run_command("ip route show")
    if ret == 0:
        for line in out.split('\n'):
            if '192.168.10' in line:
                print(f"  {line.strip()}")
    
    return True

def main():
    """主测试函数"""
    print("USRP连接专项诊断")
    print("=" * 60)
    
    tests = [
        ("网络连接", test_network_connectivity),
        ("UHD设备检测", test_uhd_detection),
        ("USRP设备探测", test_usrp_probe),
        ("GNU Radio USRP", test_gnuradio_usrp),
        ("防火墙和权限", test_firewall_and_permissions),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n开始测试: {test_name}")
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ 测试异常: {e}")
            results[test_name] = False
        
        time.sleep(1)  # 短暂延迟
    
    # 输出总结
    print("\n" + "=" * 60)
    print("测试结果总结")
    print("=" * 60)
    
    for test_name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name:15} : {status}")
    
    # 诊断建议
    print("\n" + "=" * 60)
    print("诊断建议")
    print("=" * 60)
    
    if not results.get("网络连接", False):
        print("🔧 网络连接问题:")
        print("   1. 检查网线连接")
        print("   2. 检查网络接口配置")
        print("   3. 确认USRP电源和启动状态")
    elif not results.get("UHD设备检测", False):
        print("🔧 UHD检测问题:")
        print("   1. 检查UHD版本兼容性")
        print("   2. 检查USRP固件版本")
        print("   3. 尝试重启USRP设备")
    elif not results.get("USRP设备探测", False):
        print("🔧 USRP探测问题:")
        print("   1. USRP可能正在被其他程序使用")
        print("   2. 检查USRP固件状态")
        print("   3. 尝试冷启动USRP")
    elif not results.get("GNU Radio USRP", False):
        print("🔧 GNU Radio集成问题:")
        print("   1. 检查GNU Radio和UHD版本匹配")
        print("   2. 检查Python绑定")
        print("   3. 重新安装gr-uhd模块")
    else:
        print("🎯 基础连接正常，问题可能在于:")
        print("   1. USRP参数配置")
        print("   2. 采样率设置")
        print("   3. 频率范围")
        print("   4. 增益设置")

if __name__ == "__main__":
    main()
