# ReadMe
# Usage: this runs as a service named TylerDotCloud on my Raspberry Pi. If not, then add it as a service using steps here: https://medium.com/@benmorel/creating-a-linux-service-with-systemd-611b5c8b91d6
# This is a constantly-running local server on Port 10000. If I run the associated client.py to send a message, this responds accordingly.
# Right now, it's set up for my Smart bulb to send an alert, but I can also use it in the future for some sort of voice command system.
# Lots of potential!

import select
import socket
import sys
import Queue
import time
import os
import json

# import from SmartBulb folder
sys.path.append('/home/pi/Tools/SmartBulb')
from tplight import LB130

# Bulb setup
light=LB130("192.168.1.236")
light.transition_period = 0

# Create a TCP/IP socket
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setblocking(0)

# Bind the socket to the port
server_address = ('127.0.0.1', 10000)
print >> sys.stderr, 'starting up on %s port %s' % server_address
server.bind(server_address)

# Listen for incoming connections
server.listen(5)

# Sockets from which we expect to read
inputs = [server]
# Sockets to which we expect to write
outputs = []
# Outgoing message queues (socket:Queue)
message_queues = {}

while inputs:

    # Wait for at least one of the sockets to be ready for processing
    # print >> sys.stderr, '\nwaiting for the next event'
    readable, writable, exceptional = select.select(inputs, outputs, inputs)

    # Handle inputs
    for s in readable:

        if s is server:
            # A "readable" server socket is ready to accept a connection
            connection, client_address = s.accept()
            print >> sys.stderr, 'new connection from', client_address
            connection.setblocking(0)
            inputs.append(connection)

            # Give the connection a queue for data we want to send
            message_queues[connection] = Queue.Queue()
        else:
            data = s.recv(1024)
            if data:
                # Hello -> Alert
                if(data == "hello"):
                    lightWasOff = False
                    
                    try:
                        light.status()
                    except:
                        light.on() # light was off (hence the error), so turn it on
                        lightWasOff = True
                        
                    
                    # Store current variables
                    hue = light.hue
                    brightness = light.brightness
                    saturation = light.saturation # y-axis on app
                    temperature = light.temperature #x-axis on app
                    isLightOn = json.loads(light.status())['system']['get_sysinfo']['light_state']['on_off']

                    # Cycle Red and Blue
                    light.hue = 255
                    light.saturation = 100
                    time.sleep(1)
                    light.hue = 0
                    time.sleep(1)
                    light.hue = 255
                    time.sleep(1)
    
                    # Restore variables
                    light.hue = hue
                    light.brightness = brightness
                    light.saturation = saturation
                    light.temperature = max(temperature,4000)
                    
                    if(lightWasOff):
                        light.off()

                # A readable client socket has data
                print >> sys.stderr, 'received "%s" from %s' % \
                                     (data, s.getpeername())
                message_queues[s].put(data)
                # Add output channel for response
                if s not in outputs:
                    outputs.append(s)
#            else:
                # Interpret empty result as closed connection
#                print >> sys.stderr, 'closing', client_address, \
#                    'after reading no data'

                # Stop listening for input on the connection
#                if s in outputs:
#                    outputs.remove(s)
#                inputs.remove(s)
#                s.close()

                # Remove message queue
#                del message_queues[s]

    # Handle outputs
    for s in writable:
        try:
            next_msg = message_queues[s].get_nowait()
        except Queue.Empty:
            # No messages waiting so stop checking for writability.
            print >> sys.stderr, 'output queue for', s.getpeername(), 'is empty'
            outputs.remove(s)
        else:
            print >> sys.stderr, 'sending "%s" to %s' % (next_msg,
                                                         s.getpeername())
            s.send("--" + next_msg + "--")

    # Handle "exceptional conditions"
    for s in exceptional:
        print >> sys.stderr, 'handling exceptional condition for', \
            s.getpeername()
        # Stop listening for input on the connection
        inputs.remove(s)
        if s in outputs:
            outputs.remove(s)
        s.close()

        # Remove message queue
        del message_queues[s]
