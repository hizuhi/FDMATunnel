# TUNTAP
IFF_TUN = 0x0001  # tunnel IP packets
IFF_TAP = 0x0002  # tunnel ethernet frames
IFF_NO_PI = 0x1000  # don't pass extra packet info
IFF_ONE_QUEUE = 0x2000  # beats me ;)
TUNSETIFF = 0x400454CA
TUN_IP = "10.0.0.1"

SRC_ADDR = "10.0.0.1"

# USRP params
NUM_USRP = 1
ADDR_USRPS = ["addr=192.168.10.2"]
# 双机通信配置 - 发送和接收使用不同频率
TXFREQ_USRPS = [25e6]  # Server发送频率
RXFREQ_USRPS = [20e6]  # Server接收频率
BAND_USRPS = [25e3]

# -------- UD params -------
# trans data by USRP 1/2
DEST_ADDRS = ["10.0.0.2"]

# packet params
HEADER_LEN = 10

CTL_NORM = 0
CTL_ACK = 1
CTL_CHANGE_BW = 2
CTL_DUMMY = 3

# ARQ params
WAIT_INTERVAL = 0.016

# debug
DEBUG = 1
