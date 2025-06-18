import socket
from constant_server import *
import _thread
import time

def recv_data(server):
	while 1:
		data, addr = server.recvfrom(10*1024)
		print("%s: %s" % (addr, data))
		print("Recv: %.6f" % time.time())


s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
# host = socket.gethostname() # hostname or IP addr

s.bind((host, port))

# start recv data
# thread.start_new_thread(recv_data, (s,))

clients = ['0', '1']

try:
	while 1:
		'''
		while 1:
			client = raw_input("To whom: ")
			if client in clients:
				break
		'''
		if DEBUG:
			client = "0"
		client = int(client)
		# msg = raw_input("Your message: ")
		for msg in range(100):
			s.sendto(str(msg), (dest_host[client], dest_port[client]))
			print("Send : %d \n Send time: %.6f" % (msg, time.time()))
		print('here')
		break
except:
	pass

s.close()
