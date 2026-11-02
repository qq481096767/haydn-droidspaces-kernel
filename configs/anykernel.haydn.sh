#!/system/bin/sh
# AnyKernel3 — Haydn Droidspaces Kernel (boot-only flash)
# Follows the osm0sis/AnyKernel3 template: ak3-core.sh + split_boot/write_boot.
# Config-only kernel change (no DTS edits): dtbo is left untouched.
kernel.string=Haydn Droidspaces Kernel (PID_NS + IPC_NS)
do.systemcheck=1
do.modules=0
do.cleanup=1
do.cleanuponabort=0
supported.versions=13,14,15,16
supported.patchlevels=
block=auto
is_slot_device=1
ramdisk_compression=auto

. /tmp/anykernel/tools/ak3-core.sh;

split_boot;
write_boot;
