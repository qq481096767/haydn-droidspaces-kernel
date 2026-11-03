#!/system/bin/sh
# AnyKernel3 — Haydn Droidspaces Kernel (boot-only flash)
# Follows the osm0sis/AnyKernel3 official template structure:
# config lines live inside properties() { '...' } so the shell never
# executes them, and ak3-core.sh is sourced by relative path because
# update-binary has already cd'd into $AKHOME before `ash anykernel.sh`.

### AnyKernel setup
# global properties
properties() { '
kernel.string=Haydn Droidspaces Kernel PID_NS-IPC_NS
do.devicecheck=0
do.modules=0
do.systemless=0
do.cleanup=1
do.cleanuponabort=0
supported.versions=
supported.patchlevels=
supported.vendorpatchlevels=
'; } # end properties


### AnyKernel install
## boot-only flash: replace kernel in the current slot, keep ramdisk/dtb
. tools/ak3-core.sh;

split_boot;
write_boot;
