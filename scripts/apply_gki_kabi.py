#!/usr/bin/env python3
"""Apply GKI KABI padding patches to haydn 5.4 kernel source.

haydn 5.4 kernel ALREADY has ANDROID_KABI_RESERVE(1,2) in user_struct
and ANDROID_KABI_RESERVE(6,7,8) in task_struct, so we only need to
add ANDROID_KABI_USE() to occupy those reserved slots when the
corresponding config is enabled, plus comment out the original field
declarations inside CONFIG_* blocks.

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
            if re.match(r"\s*struct\s+sysv_sem\s+sysvsem;\s*$", line):
                new_lines.append("// " + line)
                continue
            if re.match(r"\s*struct\s+sysv_shm\s+sysvshm;\s*$", line):
                new_lines.append("// " + line)
                continue
        new_lines.append(line)

    content = "".join(new_lines)

    # task_struct already has ANDROID_KABI_RESERVE(6),(7),(8) in haydn 5.4.
    # Only add ANDROID_KABI_USE() when CONFIG_SYSVIPC is enabled.
    # Find the task_struct ABI reserved block end and insert USE there.
    marker = "ANDROID_KABI_RESERVE(8);\n"
    if marker in content and "ANDROID_KABI_USE(6, struct sysv_sem" not in content:
        content = content.replace(
            marker,
            marker + "\n"
            "#ifdef CONFIG_SYSVIPC\n"
            "\tANDROID_KABI_USE(6, struct sysv_sem sysvsem);\n"
            "\tANDROID_KABI_USE(7, struct sysv_shm sysvshm);\n"
            "#endif\n",
        )

    with open(path, "w") as f:
        f.write(content)
    print("patched", path)


def apply_user_h(path):
    with open(path, "r") as f:
        content = f.read()

    # Comment out mq_bytes inside CONFIG_POSIX_MQUEUE block
    content = re.sub(
        r"^(\s*)unsigned long mq_bytes.*$",
        r"\1// unsigned long mq_bytes;  // How many bytes can be allocated to mqueue?",
        content,
        flags=re.MULTILINE,
    )

    # user_struct already has ANDROID_KABI_RESERVE(1),(2) in haydn 5.4.
    # Only add ANDROID_KABI_USE() when CONFIG_POSIX_MQUEUE is enabled.
    marker = "ANDROID_KABI_RESERVE(2);\n"
    if marker in content and "ANDROID_KABI_USE(1, unsigned long mq_bytes)" not in content:
        content = content.replace(
            marker,
            marker + "\n"
            "#ifdef CONFIG_POSIX_MQUEUE\n"
            "\tANDROID_KABI_USE(1, unsigned long mq_bytes);\n"
            "#endif\n",
        )

    with open(path, "w") as f:
        f.write(content)
    print("patched", path)


if __name__ == "__main__":
    apply_sched_h("include/linux/sched.h")
    apply_user_h("include/linux/sched/user.h")
    print("GKI KABI patches applied successfully")
