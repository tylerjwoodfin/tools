# OVERVIEW

This is a guide to rooting an Android phone after receiving an [OTA] (over-the-air) update.

# PREREQUESITES

- The bootloader must be unlocked.
- You must have ADB installed on your phone. Please Google for instructions, and make sure your phone appears in "adb devices" in your terminal emulator
- Your phone must support "fast boot mode"
- Your phone is backed up, or at least you're comfortable if something goes wrong and you need to restore

# NOTE

I'm not liable for anything that goes wrong, although worst case scenario, you need to factory reset your phone. I hope you've backed everything up properly!

# BEFORE UPDATING:
    - Copy the entire OTA somewhere safe (stored in ~/.ota on your phone), because it's going to be deleted after the update
    - Update your phone using the built-in system updater
    - Extract payload.bin from the OTA using 7Zip or something similar
    - Place payload.bin into the input folder inside payload_dumper-win64
    - Run payload_dumper.exe
    - Move boot.img from the output folder to your phone
        - open Magisk Manager and patch the boot.img you selected
        - Move magisk_patched.img to your PC
    - Place your phone in Fastboot mode and connect it
    - Open a terminal window in the same folder as magisk_patched.img, and run:
        - fastboot flash boot magisk_patched.img
        - fastboot reboot