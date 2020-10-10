import socket
import sys

messages = [ 'This is the message. ',
             'It will be sent ',
             'in parts.',
             ]
server_address = ('127.0.0.1', 10000)

# Create a TCP/IP socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(server_address)

# Send Message
s.send("my God, it works!")

# Read responses on both sockets
for s in socks:
    data = s.recv(1024)
    print >>sys.stderr, '%s: received "%s"' % (s.getsockname(), data)
    if not data:
        print >>sys.stderr, 'closing socket', s.getsockname()
        s.close()

