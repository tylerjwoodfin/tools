#!/usr/bin/env python

import time
from tplight import LB130


def main():

    # create an instance of the light with its IP address
    light = LB130("192.168.1.236")

    # fetch the details for the light
    print("Device ID: " + light.device_id)
    print("Alias: " + light.alias)
    print("Wattage: " + str(light.wattage))
    print("Current Temp: " + str(light.temperature))

    # set the transition period for any changes to 1 seconds
    light.transition_period = 0

    # Store current variables
    hue = light.hue
    brightness = light.brightness
    saturation = light.saturation # y-axis on app
    temperature = light.temperature #x-axis on app
    
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
    
if __name__ == "__main__":
    main()
