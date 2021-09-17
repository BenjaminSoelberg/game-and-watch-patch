"""
For usage, run:
        python3 patch.py --help
"""

import sys
if sys.version_info[0] < 3 or sys.version_info[1] < 6:
    raise Exception("Must be using at least Python 3.6")


from pathlib import Path
import argparse

from patches import Device, IntFirmware, ExtFirmware
from patches import apply_patches, add_patch_args, validate_patch_args
from patches.exception import InvalidPatchError

import colorama
from colorama import Fore, Back, Style
colorama.init()


def parse_args():
    parser = argparse.ArgumentParser(description="Game and Watch Firmware Patcher.")

    #########################
    # Global configurations #
    #########################
    parser.add_argument('--int-firmware', type=Path, default="internal_flash_backup.bin",
                        help="Input stock internal firmware.")
    parser.add_argument('--ext-firmware', type=Path, default="flash_backup.bin",
                        help="Input stock external firmware.")
    parser.add_argument('--patch', type=Path, default="build/gw_patch.bin",
                        help="Compiled custom code to insert at the end of the internal firmware")
    parser.add_argument('--elf', type=Path, default="build/gw_patch.elf",
                        help="ELF file corresponding to the bin provided by --patch")
    parser.add_argument('--int-output', type=Path, default="build/internal_flash_patched.bin",
                        help="Patched internal firmware.")
    parser.add_argument('--ext-output', type=Path, default="build/external_flash_patched.bin",
                        help="Patched external firmware.")

    parser.add_argument("--extended", action="store_true", default=False,
                        help="256KB internal flash image instead of 128KB.")

    debugging = parser.add_argument_group("debugging")
    debugging.add_argument("--show", action="store_true",
                           help="Show a picture representation of the external patched binary.")
    debugging.add_argument("--debug", action="store_true",
                           help="Install useful debugging fault handlers.")


    ########################
    # Patch configurations #
    ########################
    patches = parser.add_argument_group('patches')
    add_patch_args(patches)

    # Final Validation
    args = parser.parse_args()
    validate_patch_args(parser, args)

    return args


def main():
    args = parse_args()

    device = Device(
        IntFirmware(args.int_firmware, args.elf),
        ExtFirmware(args.ext_firmware)
    )

    # Decrypt the external firmware
    device.crypt()
    # Path("decrypt.bin").write_bytes(device.external)

    # Copy over novel code
    patch = args.patch.read_bytes()
    if len(device.internal) != len(patch):
        raise InvalidPatchError(f"Expected patch length {len(device.internal)}, got {len(patch)}")
    device.internal[device.internal.STOCK_ROM_END:] = patch[device.internal.STOCK_ROM_END:]
    del patch

    if args.extended:
        device.internal.extend(b"\x00" * 0x20000)


    print(Fore.BLUE)
    print("#########################")
    print("# BEGINING BINARY PATCH #")
    print("#########################" + Style.RESET_ALL)

    # Perform all replacements in stock code.
    apply_patches(args, device)

    # Erase the extflash vram region
    device.external[-8192:] = b"\x00" * 8192

    if args.show:
        # Debug visualization
        device.show()

    # Re-encrypt the external firmware
    Path("build/decrypt_flash_patched.bin").write_bytes(device.external)
    device.external.crypt(device.internal.key, device.internal.nonce)

    # Compress, insert, and reference the modified rwdata
    device.internal.compress_rwdata()

    # Save patched firmware
    args.int_output.write_bytes(device.internal)
    args.ext_output.write_bytes(device.external)

    print(Fore.GREEN)
    print( "Binary Patching Complete!")
    print(f"    Internal Firmware Used: {len(device.internal)} bytes")  # TODO: show free amount
    print(f"    External Firmware Used: {len(device.external)} bytes")
    print(Style.RESET_ALL)


if __name__ == "__main__":
    main()
