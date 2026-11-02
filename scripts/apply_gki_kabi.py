#!/usr/bin/env python3
"""Apply GKI KABI padding patches to haydn 5.4 kernel source.

haydn 5.4 kernel ALREADY has ANDROID_KABI_RESERVE(6,7,8) in task_struct
and ANDROID_KABI_RESERVE(1,2) in user_struct. We only need to:
1. Comment out the original field declarations inside CONFIG_SYSVIPC /
   CONFIG_POSIX_MQUEUE blocks (so they don't conflict with the reserved
   slots when the config is enabled).
2. Do NOT add any ANDROID_KABI_USE() or ANDROID_KABI_RESERVE() macros -
   they already exist and adding them causes "redeclares" compile errors.

Follows the spirit of official Droidspaces GKI patches:
- patches/gki/001.GKI-below-6.12-fix_sysvipc_kabi_6_7_8.patch
- patches/gki/002.5.10_or_lower_use_android_abi_padding_for_posix_mqueue.patch
"""
import re
import sys


def apply_sched_h(path):
    with open(path, "r") as f:
        lines = f.readlines()

    new_lines = []
    in_sysvipc_block = False
    for line in lines:
        if "#ifdef CONFIG_SYSVIPC" in line:
            in_sysvipc_block = True
            new_lines.append(line)
            continue
        if in_sysvipc_block and "#endif" in line:
            in_sysvipc_block = False
            new_lines.append(line)
            continue
        if in_sysvipc_block:
            # Comment out original declarations so they don't conflict
            # with the existing ANDROID_KABI_RESERVE slots when
            # CONFIG_SYSVIPC is enabled.
            if re.match(r"\s*struct\s+sysv_sem\s+sysvsem;\s*$", line):
                new_lines.append("// " + line)
                continue
            if re.match(r"\s*struct\s+sysv_shm\s+sysvshm;\s*$", line):
                new_lines.append("// " + line)
                continue
        new_lines.append(line)

    content = "".join(new_lines)
    with open(path, "w") as f:
        f.write(content)
    print("patched", path)


def apply_user_h(path):
    with open(path, "r") as f:
        content = f.read()

    # Comment out mq_bytes inside CONFIG_POSIX_MQUEUE block - the existing
    # ANDROID_KABI_RESERVE(1) slot already covers it when enabled.
    content = re.sub(
        r"^(\s*)unsigned long mq_bytes.*$",
        r"\1// unsigned long mq_bytes;  // covered by ANDROID_KABI_RESERVE(1)",
        content,
        flags=re.MULTILINE,
    )

    with open(path, "w") as f:
        f.write(content)
    print("patched", path)


if __name__ == "__main__":
    apply_sched_h("include/linux/sched.h")
    apply_user_h("include/linux/sched/user.h")
    print("GKI KABI patches applied successfully")
