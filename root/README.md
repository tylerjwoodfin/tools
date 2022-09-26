# Overview

- This is a guide to rooting an Android phone on Windows after receiving an [OTA] (over-the-air) update.

# Disclaimer

- I'm not liable for anything that goes wrong, although worst case scenario, you need to factory reset your phone. I hope you've backed everything up properly!

# Dependencies

- Windows
- The bootloader must be unlocked.
- [ADB](https://www.xda-developers.com/install-adb-windows-macos-linux/).
  - Test your installation by plugging your phone in, allowing USB debugging, and verifying your phone appears after running `adb devices`
- Your phone must support "fast boot mode"
- Your phone is backed up, or at least you're comfortable if something goes wrong and you need to restore

# Root Instructions

## Before Updating

- Copy the entire OTA to your Windows PC (stored in ~/.ota on your phone), because it's going to be deleted after the update
- Update your phone using the built-in system updater

## On your PC

- Extract payload.bin from the OTA using 7Zip or something similar
- Place payload.bin into the payload_input folder inside payload_dumper-win64
- Run payload_dumper.exe
- Move boot.img from the output folder to your phone

## On your phone

- open Magisk Manager and patch the boot.img you selected
- Move magisk_patched.img to your PC

## Final Steps

- Place your phone in Fastboot mode and connect it
- Open a terminal in the same folder as magisk_patched.img, and run:
  - `fastboot flash boot magisk_patched.img`
  - `fastboot reboot`
