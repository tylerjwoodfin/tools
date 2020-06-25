import socket
import sys

server_address = ('127.0.0.1', 10000)

# Create a TCP/IP socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(server_address)

# Send Message
s.send("hello")

# Read response
data = s.recv(1024)
print >>sys.stderr, '%s: received "%s"' % (s.getsockname(), data)
if not data:
    print >>sys.stderr, 'closing socket', s.getsockname()
    s.close()

