#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
Control class for TP-Link A19-LB130 RBGW WiFi bulb
'''

import datetime
import socket
import json
import sys


class LB130(object):
    '''
    Methods for controlling the LB130 bulb
    '''

    encryption_key = 0xAB

    __udp_ip = "10.0.0.130"
    __udp_port = 9999
    __on_off = 0
    __transition_period = 0
    __hue = 0
    __saturation = 0
    __brightness = 0
    __color_temp = 0
    __connected = False

    __alias = ""
    device_id = ""
    lamp_beam_angle = 0
    min_voltage = 0
    max_voltage = 0
    wattage = 0
    incandescent_equivalent = 0
    max_lumens = 0
    color_rendering_index = 0

    # Public Methods

    def __init__(self, ip_address):
        '''
        Initialise the bulb with an ip address
        '''

        # validate the ip address
        ip_array = ip_address.split(".")
        valid_ip = True
        try:
            if len(ip_array) == 4:
                for ipval in ip_array:
                    if int(ipval) < 0 or int(ipval) > 255:
                        valid_ip = False
            else:
                valid_ip = False
        except (RuntimeError, TypeError, ValueError):
            valid_ip = False

        if valid_ip:
            self.__udp_ip = ip_address

            # Parse the sysinfo JSON message to get the
            # status of the various parameters

            try:
                data = json.loads(self.status())
                col1 = 'system'
                col2 = 'get_sysinfo'
                col3 = 'light_state'
                self.__alias = data[col1][col2]['alias']
                self.__on_off = int(data[col1][col2][col3]['on_off'])
                self.__hue = int(data[col1][col2][col3]['hue'])
                self.__saturation = int(data[col1][col2][col3]['saturation'])
                self.__brightness = int(data[col1][col2][col3]['brightness'])
                self.__color_temp = int(data[col1][col2][col3]['color_temp'])
                self.device_id = str(data[col1][col2]['deviceId'])
            except (RuntimeError, TypeError, ValueError) as exception:
                raise Exception(exception)

            # Parse the light details JSON message to get the
            # status of the various parameters

            try:
                data = json.loads(self.light_details())
                col1 = 'smartlife.iot.smartbulb.lightingservice'
                col2 = 'get_light_details'
                inc = 'incandescent_equivalent'
                colour = 'color_rendering_index'
                self.lamp_beam_angle = int(data[col1][col2]['lamp_beam_angle'])
                self.min_voltage = int(data[col1][col2]['min_voltage'])
                self.max_voltage = int(data[col1][col2]['max_voltage'])
                self.wattage = int(data[col1][col2]['wattage'])
                self.incandescent_equivalent = int(data[col1][col2][inc])
                self.max_lumens = int(data[col1][col2]['max_lumens'])
                self.color_rendering_index = str(data[col1][col2][colour])
            except (RuntimeError, TypeError, ValueError) as exception:
                raise Exception(exception)

        else:
            raise ValueError('Invalid IPv4 IP address.')

    def status(self):
        '''
        Get the connection status from the bulb
        '''
        message = "{\"system\":{\"get_sysinfo\":{}}}"
        return self.__fetch_data(message)

    def light_details(self):
        '''
        Get the light details from the bulb
        '''
        message = "{\"smartlife.iot.smartbulb.lightingservice\":\
                   {\"get_light_details\":\"\"}}"
        return self.__fetch_data(message)

    def on(self):
        '''
        Set the bulb to an on state
        '''
        __bulb_on_off = 1
        self.__update("{\"smartlife.iot.smartbulb.lightingservice\":{\""
                      "transition_light_state\":{\"ignore_default\":1,\""
                      "transition_period\":" +
                      str(self.__transition_period) + ",\"on_off\":1}}}")

    def off(self):
        '''
        Set the bulb to an off state
        '''
        __bulb_on_off = 0
        self.__update("{\"smartlife.iot.smartbulb.lightingservice\":{\""
                      "transition_light_state\":{\"ignore_default\":1,\"transition_period\""
                      ":" + str(self.__transition_period) + ",\"on_off\":0}}}")


    def reboot(self):
        '''
        Reboot the bulb
        '''
        self.__update("{\"smartlife.iot.common.system\":{\"reboot\":\
                      {\"delay\":1}}}")

    @property
    def alias(self):
        '''
        Get the device alias
        '''
        return self.__alias

    @alias.setter
    def alias(self, name):
        '''
        Set the device alias
        '''
        self.__update("{\"smartlife.iot.common.system\":{\"set_dev_alias\"\
                      :{\"alias\":\"" + name + "\"}}}")

    @property
    def time(self):
        '''
        Get the date and time from the device
        '''
        message = "{\"smartlife.iot.common.timesetting\":{\"get_time\":{}}}"
        device_time = datetime
        data = json.loads(self.__fetch_data(message))
        col1 = 'smartlife.iot.common.timesetting'
        device_time.year = data[col1]['get_time']['year']
        device_time.month = data[col1]['get_time']['month']
        device_time.day = data[col1]['get_time']['mday']
        device_time.hour = data[col1]['get_time']['hour']
        device_time.minute = data[col1]['get_time']['min']
        device_time.second = data[col1]['get_time']['sec']
        return device_time

    @time.setter
    def time(self, date):
        '''
        Set the date and time on the device
        '''
        if isinstance(date, datetime.datetime):
            self.__update("{\"smartlife.iot.common.timesetting\":{\"set_time\"\
                          :{\"year\":" + str(date.year) +
                          ",\"month\":" + str(date.month) +
                          ",\"mday\":" + str(date.day) +
                          ",\"hour\":" + str(date.hour) +
                          ",\"min\":" + str(date.minute) +
                          ",\"sec\":" + str(date.second) +
                          "}}}")
        else:
            raise ValueError('Invalid type: must pass a datetime object')
        return

    @property
    def timezone(self):
        '''
        Get the timezone from the device
        '''
        message = "{\"smartlife.iot.common.timesetting\":\
                   {\"get_timezone\":{}}}"

        data = json.loads(self.__fetch_data(message))
        col1 = 'smartlife.iot.common.timesetting'
        timezone = data[col1]['get_timezone']['index']
        return timezone

    @timezone.setter
    def timezone(self, timezone):
        '''
        Set the timezone on the device
        '''
        if timezone >= 0 and timezone <= 109:
            date = self.time
            self.__update("{\"smartlife.iot.common.timesetting\":\
                          {\"set_timezone\":{\"index\":" + str(timezone) +
                          ",\"year\":" + str(date.year) +
                          ",\"month\":" + str(date.month) +
                          ",\"mday\":" + str(date.day) +
                          ",\"hour\":" + str(date.hour) +
                          ",\"min\":" + str(date.minute) +
                          ",\"sec\":" + str(date.second) + "}}}")
        else:
            raise ValueError('Timezone out of range: 0 to 109')
        return

    @property
    def transition_period(self):
        '''
        Get the bulb transition period
        '''
        return self.__transition_period

    @transition_period.setter
    def transition_period(self, period):
        '''
        Set the bulb transition period
        '''
        if period >= 0 and period <= 100000:
            self.__transition_period = period
        else:
            raise ValueError('transition_period out of range: 0 to 100000')

    @property
    def hue(self):
        '''
        Get the bulb hue
        '''
        return self.__hue

    @hue.setter
    def hue(self, hue):
        '''
        Set the bulb hue
        '''
        if hue >= 0 and hue <= 360:
            self.__hue = hue
            self.__update("{\"smartlife.iot.smartbulb.lightingservice\":\
                          {\"transition_light_state\":{\"ignore_default\":\
                          1,\"transition_period\":" +
                          str(self.__transition_period) +
                          ",\"hue\":" + str(self.__hue) + "\
                          ,\"color_temp\":0}}}")
        else:
            raise ValueError('hue out of range: 0 to 360')

    @property
    def saturation(self):
        '''
        Get the bulb saturation
        '''
        return self.__saturation

    @saturation.setter
    def saturation(self, saturation):
        '''
        Set the bulb saturation
        '''
        if saturation >= 0 and saturation <= 100:
            self.__saturation = saturation
            self.__update("{\"smartlife.iot.smartbulb.lightingservice\":\
                          {\"transition_light_state\":{\"ignore_default\":1,\"\
                          transition_period\":" +
                          str(self.__transition_period) + ",\"saturation\":" +
                          str(self.__saturation) + ",\"color_temp\":0}}}")
        else:
            raise ValueError('saturation value out of range: 0 to 100')

    @property
    def brightness(self):
        '''
        Get the bulb brightness
        '''
        return self.__brightness

    @brightness.setter
    def brightness(self, brightness):
        '''
        Set the bulb brightness
        '''
        if brightness >= 0 and brightness <= 100:
            self.__brightness = brightness
            self.__update("{\"smartlife.iot.smartbulb.lightingservice\":\
                          {\"transition_light_state\":{\"ignore_default\":1,\"\
                          transition_period\":" +
                          str(self.__transition_period) +
                          ",\"brightness\":" + str(self.__brightness) + "}}}")
        else:
            raise ValueError('brightness out of range: 0 to 100')

    @property
    def temperature(self):
        '''
        Get the bulb color temperature
        '''
        return self.__color_temp

    @temperature.setter
    def temperature(self, temperature):
        '''
        Set the bulb color temperature
        '''
        if temperature >= 2500 and temperature <= 9000:
            self.__color_temp = temperature
            self.__update("{\"smartlife.iot.smartbulb.lightingservice\":\
                          {\"transition_light_state\":{\"ignore_default\":\
                          1,\"transition_period\":" +
                          str(self.__transition_period) + ",\"color_temp\":" +
                          str(self.__color_temp) + "}}}")
        else:
            raise ValueError('temperature out of range: 2500 to 9000')

    @property
    def hsb(self):
        '''
        Get the bulb hue, saturation, and brightness
        '''
        return (self.__hue, self.__saturation, self.__brightness)

    @hsb.setter
    def hsb(self, hsb):
        '''
        Set the bulb hue, saturation, and brightness
        '''
        try:
            hue, saturation, brightness = hsb
        except ValueError:
            raise ValueError("Pass an iterable with hue, saturation, and brightness")

        if hue >= 0 and hue <= 360 and saturation >= 0 and saturation <= 100 and brightness >= 0 and brightness <= 100:
            self.__hue = hue
            self.__saturation = saturation
            self.__brightness = brightness
            self.__update("{\"smartlife.iot.smartbulb.lightingservice\":\
                          {\"transition_light_state\":{\"ignore_default\":\
                          1,\"transition_period\":" +
                          str(self.__transition_period) +
                          ",\"hue\":" + str(self.__hue) +
                          ",\"saturation\":" + str(self.__saturation) +
                          ",\"brightness\":" + str(self.__brightness) +
                          ",\"color_temp\":0}}}")
        else:
            raise ValueError('hue, saturation, or brightness out of range')


    # private methods

    @staticmethod
    def __encrypt(value, key):
        '''
        Encrypt the command string
        '''
        valuelist = list(value)

        for i in range(len(valuelist)):
            var = ord(valuelist[i])
            valuelist[i] = chr(var ^ int(key))
            key = ord(valuelist[i])
        if sys.version_info >= (3,0):
            return bytearray("".join(valuelist).encode("latin_1")) # python 3 fix
        else:
            return "".join(valuelist)

    @staticmethod
    def __decrypt(value, key):
        '''
        Decrypt the command string
        '''
        valuelist = list(value.decode("latin_1"))

        for i in range(len(valuelist)):
            var = ord(valuelist[i])
            valuelist[i] = chr(var ^ key)
            key = var

        return "".join(valuelist)

    def __update(self, message):
        '''
        Update the bulbs status
        '''
        enc_message = self.__encrypt(message, self.encryption_key)
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(5)
            sock.sendto(enc_message, (self.__udp_ip, self.__udp_port))
            data_received = False
            dec_data = ""
            while True:
                data, addr = sock.recvfrom(1024)  # buffer size is 1024 bytes
                dec_data = self.__decrypt(data, self.encryption_key)
                if "}}}" in dec_data:  # end of sysinfo message
                    data_received = True
                    break

            if data_received:
                if "\"err_code\":0" in dec_data:
                    return
                else:
                    raise RuntimeError("Bulb returned error: " + dec_data)
            else:
                raise RuntimeError("Error connecting to bulb, Update1")
        except:
            raise RuntimeError("Error connecting to bulb, Update")

    def __fetch_data(self, message):
        '''
        Fetch data from the device
        '''
        enc_message = self.__encrypt(message, self.encryption_key)

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(5)
            sock.sendto(enc_message, (self.__udp_ip, self.__udp_port))
            data_received = False
            dec_data = ""
            while True:
                data, addr = sock.recvfrom(1024)  # buffer size is 1024 bytes
                dec_data = self.__decrypt(data, self.encryption_key)
                if "}}}" in dec_data:  # end of sysinfo message
                    data_received = True
                    break

            if data_received:
                if "\"err_code\":0" in dec_data:
                    return dec_data
                else:
                    raise RuntimeError("Bulb returned error: " + dec_data)
            else:
                raise RuntimeError("Error connecting to bulb, FetchData1")
        except:
            raise RuntimeError("Error connecting to bulb, FetchData")
