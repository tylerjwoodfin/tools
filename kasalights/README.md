# kasalights

A simple tool to control my condo's light bulbs

## usage

- `python3 main.py {device name} {on/off}`
  - When first run (or when `securedata -> 'lights'` is deleted), it will discover devices on the current network.

## dependencies

- [python-kasa](https://pypi.org/project/python-kasa/)
- [securedata](https://github.com/tylerjwoodfin/securedata)
