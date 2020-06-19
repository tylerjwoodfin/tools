# TP-Link A19-LB130 Wifi Bulb Python Library

The tplight.py python library contains a class LB130 and methods for controlling the TP-Link A19-LB130 Wifi bulb.

A demo file demo.py is included which shows how to use the class.

Create an instance of the LB130 class with the IP address for the bulb

```
light = LB130("10.0.0.130")
```

## Methods

```
status()
```

Get the connection status from the bulb.  Returns a JSON formatted string with all of the available parameters.  

```
light_details()
```

Get the light details from the bulb including min and max voltage, wattage and colour rendering index.  Returns a JSON formatted string with all of the available parameters.  

```
on()
```

Set the bulbs state to on.

```
off()
```

Set the bulbs state to off.

```
reboot()
```

Reboot the bulb.

```
alias(name)
```

Get or set the alias name for the bulb.

```
time(date)
```

Get or set the date and time on the bulb.  Takes and returns a date as a datetime object.

```
timezone(timezone)
```

Get or set the timezone for the bulb.  Value between 0 and 109.  See timezones.md for a list of available timezones.

```
transition_period(period)
```

Get or set the transition period for any changes made to the bulbs colour or brightness.  Value in milliseconds between 0 and 10000.

```
hue(hue)
```

Get or set the bulbs hue.  Value between 0 and 360.

```
saturation(saturation)
```

Get or set the colour saturation for the bulb.  Value between 0 and 100.

```
brightness(brightness)
```

Get or set the brightness.  Value between 0 and 100.

```
hsb((hue, saturation, brightness))
```

Get or set the bulbs hue, saturation, and brightness.

```
temperature(temperature)
```

Get or set the colour temperature.  Value between 2500 and 9000.
