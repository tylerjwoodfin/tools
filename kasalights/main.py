from os import system as run
import kasa
import sys
import asyncio
from securedata import securedata

dimmers = kasa.Discover()

devices = securedata.getItem("lights") or {}
devices_keys = devices.keys()


async def main():

    # discover devices
    if devices == {}:
        print("Discovering devices...")
        found_devices = await kasa.Discover.discover()
        # print(found_devices)
        for dev in found_devices:
            devices[found_devices[dev].alias.lower()] = dev

        securedata.setItem("lights", devices)

    # parse args
    device = ''
    operation = ''
    if len(sys.argv) >= 2:
        if 'on' in sys.argv[1:]:
            operation = 'on'
        elif 'off' in sys.argv[1:]:
            operation = 'off'

        # handle "all"
        if 'all' in sys.argv[1:]:
            for device in devices:
                await switch(device, operation)
            sys.exit(0)

        device = ' '.join(
            list(filter(lambda x: x != 'on' and x != 'off', sys.argv[1:])))

    while device not in devices_keys and f"{device} light" not in devices_keys:
        device = input("\nWhat would you like to toggle?\n")

        if device not in devices_keys and f"{device} light" not in devices_keys:
            print(f"\n\n{device} not in {list(devices_keys)}")

    switch(device, operation or "toggle")


async def switch(device, operation):
    if device not in devices_keys and f"{device} light" not in devices_keys:
        print(f"\n\n{device} not in {list(devices_keys)}")
        return

    if not device.endswith("light") and device not in devices_keys:
        device = f"{device} light"

    # get dimmer state
    dimmer = kasa.SmartDimmer(devices[device])
    await dimmer.update()

    # handle toggle
    if operation == 'toggle':
        if dimmer.is_on:
            operation == 'off'
        else:
            operation == 'on'

    # handle already on/off
    if dimmer.is_on and operation == 'on' or dimmer.is_off and operation == 'off':
        print(f"The {device} is already {operation}")
        return

    print(f"Turning {device} {'off' if dimmer.is_on else 'on'}")

    if dimmer.is_on and operation != 'on':
        await dimmer.turn_off()
    elif operation != 'off':
        await dimmer.turn_on()

if __name__ == "__main__":
    asyncio.run(main())
