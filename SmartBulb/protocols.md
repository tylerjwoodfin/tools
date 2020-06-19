# TP-Link A19-LB130 Wifi Bulb Command Protocol

Commands are sent to the light bulb IP address, Port 9999 using a JSON formatted string.  The string is encrypted by XORing each byte with the previous plain text byte.  

tplight.py contains the encryption and decrytion routines.

## smartlife.iot.common.system

#### reboot

reboot the device

Command:

```
{"smartlife.iot.common.system":{"reboot":{"delay":1}}}
```  

Returns:

```
{"smartlife.iot.common.system":{"reboot":{"err_code":0}}}
```

#### set_dev_alias

Set the name or alias for the device

Command:

```
{"smartlife.iot.common.system":{"set_dev_alias":{"alias":"Kitchen Light"}}}
```

Returns:

```
{"smartlife.iot.common.system":{"set_dev_alias":{"err_code":0}}}
```

## system

#### get_info

Gets the system information for the light bulb.

Command:

```
{"system":{"get_sysinfo":""}}
```

Returns:

```
{"system":{"get_sysinfo":{"sw_ver":"1.5.5 Build 170623 Rel.090105","hw_ver":"1.0","model":"LB130(EU)","description":"Smart Wi-Fi LED Bulb with Color Changing","alias":"Aaaa","mic_type":"IOT.SMARTBULB","dev_state":"normal","mic_mac":"50C7BF5E9C8F","deviceId":"80123265DD825560B3CAA1C3B1B12956187286B1","oemId":"D5C424D3C480911C980ECDD56C27988F","hwId":"111E35908497A05512E259BB76801E10","is_factory":false,"disco_ver":"1.0","ctrl_protocols":{"name":"Linkie","version":"1.0"},"light_state":{"on_off":1,"mode":"normal","hue":30,"saturation":100,"color_temp":0,"brightness":7},"is_dimmable":1,"is_color":1,"is_variable_color_temp":1,"preferred_state":[{"index":0,"hue":0,"saturation":0,"color_temp":2700,"brightness":50},{"index":1,"hue":0,"saturation":75,"color_temp":0,"brightness":100},{"index":2,"hue":120,"saturation":75,"color_temp":0,"brightness":100},{"index":3,"hue":240,"saturation":75,"color_temp":0,"brightness":100}],"rssi":-57,"active_mode":"none","heapsize":316848,"err_code":0}}}
```

## smartlife.iot.common.schedule

The scheduler allows you to set events which will run at a scheduled date and time.

#### get_rules

Get a list of the rules present on the device

Command:

```
{"smartlife.iot.common.schedule":{"get_rules":""}}
```

Returns:

```
{"smartlife.iot.common.schedule":{"get_rules":{"rule_list":[{"id":"CF652E0D1D57B0BC12D978822F4456CA","name":"name","enable":1,"wday":[1,0,1,0,1,0,0],"stime_opt":0,"smin":780,"sact":2,"s_light":{"on_off":1,"mode":"customize_preset","hue":129,"saturation":21,"color_temp":0,"brightness":17},"etime_opt":-1,"emin":0,"eact":-1,"repeat":1}],"enable":1,"err_code":0}}}
```

#### add_rule

Add a new rule to the scheduler.

Command:

```
{"smartlife.iot.common.schedule":{"add_rule":{"name":"name","repeat":1,"wday":[1,0,1,0,1,0,0],"stime_opt":0,"eact":-1,"smin":780,"s_light":{"saturation":21,"hue":129,"brightness":17,"color_temp":0,"mode":"customize_preset","on_off":1},"enable":1,"day":24,"year":2017,"month":8,"sact":2,"emin":-1,"etime_opt":-1},"set_overall_enable":{"enable":1}}}
```

Returns:

```
{"smartlife.iot.common.schedule":{"add_rule":{"id":"CF652E0D1D57B0BC12D978822F4456CA","err_code":0},"set_overall_enable":{"err_code":0}}}
```

#### delete_rule

Delete a rule from the scheduler

Command:
```
{"smartlife.iot.common.schedule":{"delete_rule":{"id":"CF652E0D1D57B0BC12D978822F4456CA"}}}
```

Returns
```
{"smartlife.iot.common.schedule":{"delete_rule":{"err_code":0}}}
```

#### get_next_action

## smartlife.iot.common.timesetting

#### get_time

Gets the date and time from the device

Command:

```
{"smartlife.iot.common.timesetting":{"get_time":{}}}
```

Returns:

```
{"smartlife.iot.common.timesetting":{"get_time":{"year":2017,"month":8,"mday":24,"hour":20,"min":10,"sec":19,"err_code":0}}}
```

#### set_time

Sets the date and time for the device

Command:

```
{"smartlife.iot.common.timesetting":{"set_time":{"year":2017,"month":8,"mday":24,"hour":20,"min":10,"sec":19}}}
```

Returns:

```
{"smartlife.iot.common.timesetting":{"set_time":{"err_code":0}}}
```

#### get_timezone

Gets the timezone code for the device

Command:

```
{"smartlife.iot.common.timesetting":{"get_timezone":{}}}
```

Returns:

```
{"smartlife.iot.common.timesetting":{"get_timezone":{"index":39,"err_code":0}}}
```

#### set_timezone

Set the timezone code for the device

Command:

```
{"smartlife.iot.common.timesetting":{"set_timezone":{"index":39,"hour":18,"year":2017,"min":26,"month":8,"sec":42,"mday":25}}}
```

Returns:

```
{"smartlife.iot.common.timesetting":{"set_timezone":{"err_code":0}}}
```

## smartlife.iot.common.emeter

#### get_daystat

Get the daily power usage in wh for the specified month

Command:

```
{"smartlife.iot.common.emeter":{"get_daystat":{"year":2017,"month":8}}}
```

Returns:

```
{"smartlife.iot.common.emeter":{"get_daystat":{"day_list":[{"year":2017,"month":8,"day":2,"energy_wh":0},{"year":2017,"month":8,"day":3,"energy_wh":0},{"year":2017,"month":8,"day":9,"energy_wh":2},{"year":2017,"month":8,"day":12,"energy_wh":3},{"year":2017,"month":8,"day":14,"energy_wh":0},{"year":2017,"month":8,"day":15,"energy_wh":3},{"year":2017,"month":8,"day":16,"energy_wh":3},{"year":2017,"month":8,"day":17,"energy_wh":4},{"year":2017,"month":8,"day":23,"energy_wh":0},{"year":2017,"month":8,"day":24,"energy_wh":14},{"year":2017,"month":8,"day":25,"energy_wh":0},{"year":2017,"month":8,"day":26,"energy_wh":0}],"err_code":0}}}
```

## smartlife.iot.smartbulb.lightingservice

#### get_light_state

Get the status and values for the hue, saturation, brightness and colour temperature

Command:

```
{"smartlife.iot.smartbulb.lightingservice":{"get_light_state":""}}
```

Returns:

```
{"smartlife.iot.smartbulb.lightingservice":{"get_light_state":{"on_off":1,"mode":"normal","hue":30,"saturation":100,"color_temp":0,"brightness":7,"err_code":0}}}
```

#### transition_light_state

Set the status and values for the hue, saturation, brightness and colour temperature.  The transition period for changing to the new state can be defined using the transition_period variable.

Command:

```
{"smartlife.iot.smartbulb.lightingservice":{"transition_light_state":{"ignore_default":1,"transition_period":150,"mode":"normal","hue":120,"on_off":1,"saturation":65,"color_temp":0,"brightness":10}}}
```

Returns:

```
{"smartlife.iot.smartbulb.lightingservice":{"transition_light_state":{"on_off":1,"mode":"normal","hue":120,"saturation":65,"color_temp":0,"brightness":10,"err_code":0}}}
```


#### get_light_details

Get the system details for the device such as min and max voltages, lamp beam angle and maximum lumens.

Command:

```
{"smartlife.iot.smartbulb.lightingservice":{"get_light_details":""}}
```

Returns:

```
{"smartlife.iot.smartbulb.lightingservice":{"get_light_details":{"lamp_beam_angle":150,"min_voltage":110,"max_voltage":120,"wattage":10,"incandescent_equivalent":60,"max_lumens":800,"color_rendering_index":80,"err_code":0}}}
```

#### get_default_behavior

Get the default behavior for the device when it powers on.

Command:

```
{"smartlife.iot.smartbulb.lightingservice":{"get_default_behavior":""}}
```

Returns:

```
{"smartlife.iot.smartbulb.lightingservice":{"get_default_behavior":{"soft_on":{"mode":"last_status"},"hard_on":{"mode":"last_status"},"err_code":0}}}
```

## Wifi Setup

#### get_scaninfo

Scan for nearby Access Points

Command:

```
{"netif":{"get_scaninfo":{"refresh":1}}}
```

#### set_stainfo

Connect to an access point with a specified SSID, password and key type.

Command:

```
{"netif":{"set_stainfo":{"ssid":"WiFi","password":"123","key_type":3}}}
```