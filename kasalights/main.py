from os import system as run
import kasa
import json
import asyncio
from securedata import securedata

# run("kasa --host 192.168.0.212 --type dimmer off")

dimmers = kasa.Discover()

devices = securedata.getItem("lights") or {}


async def main():

    if devices == {}:
        print("Discovering devices...")
        found_devices = await kasa.Discover.discover()
        # print(found_devices)
        for dev in found_devices:
            devices[found_devices[dev].alias.lower()] = dev

        securedata.setItem("lights", devices)

    device = ''
    devices_keys = devices.keys()
    while device not in devices_keys and f"{device} light" not in devices_keys:
        device = input("\nWhat would you like to toggle?\n")

        if device not in devices_keys and f"{device} light" not in devices_keys:
            print(f"\n\n{device} not in {list(devices_keys)}")

    if not device.endswith("light") and device not in devices_keys:
        device = f"{device} light"

    dimmer = kasa.SmartDimmer(devices[device])

    await dimmer.update()
    print(f"Turning {device} {'off' if dimmer.is_on else 'on'}")

    if dimmer.is_on:
        await dimmer.turn_off()
    else:
        await dimmer.turn_on()

if __name__ == "__main__":
    asyncio.run(main())
