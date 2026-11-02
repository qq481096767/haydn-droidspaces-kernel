#!/usr/bin/env python3
"""Apply GKI KABI padding patches to haydn 5.4 kernel source.

haydn 5.4 kernel ALREADY has:
- task_struct: ANDROID_KABI_RESERVE(1)..(8) at end of struct
- user_struct: ANDROID_KABI_RESERVE(1), (2)

We must:
1. Comment out original sysvsem/sysvshm declarations inside CONFIG_SYSVIPC block
   (they are relocated to ABI reserved slots below)
2. Replace existing ANDROID_KABI_RESERVE(6);(7);(8); in task_struct with
   #ifdef CONFIG_SYSVIPC ... ANDROID_KABI_USE(6)/_ANDROID_KABI_REPLACE(...) ... #else ... RESERVE(6/7/8) ... #endif
3. Comment out mq_bytes inside CONFIG_POSIX_MQUEUE block
4. Replace existing ANDROID_KABI_RESERVE(1);(2); in user_struct with
   #ifdef CONFIG_POSIX_MQUEUE ... ANDROID_KABI_USE(1) ... #else ... RESERVE(1/2) ... #endif

Follows official Droidspaces GKI patches:
- 001.GKI-below-6.12-fix_sysvipc_kabi_6_7_8.patch
- 002.5.10_or_lower_use_android_abi_padding_for_posix_mqueue.patch
"""
import re
import sys


def apply_sched_h(path):
    with open(path, "r") as f:
        content = f.read()

    # 1. Comment out original sysvsem/sysvshm inside CONFIG_SYSVIPC block (~line 1074)
    content = re.sub(
        r"(#ifdef CONFIG_SYSVIPC\n)(\s*)struct sysv_sem\s+sysvsem;\n(\s*)struct sysv_shm\s+sysvshm;\n",
        r"\1\2// struct sysv_sem sysvsem;\n\3// struct sysv_shm sysvshm;\n",
        content,
    )

    # 2. Replace existing ANDROID_KABI_RESERVE(6);(7);(8); with
    #    #ifdef CONFIG_SYSVIPC ... USE(6)/_ANDROID_KABI_REPLACE(...) ... #else ... RESERVE(6/7/8) ... #endif
    old = "ANDROID_KABI_RESERVE(6);\nANDROID_KABI_RESERVE(7);\nANDROID_KABI_RESERVE(8);\n"
    new = ("#ifdef CONFIG_SYSVIPC\n"
           "\tANDROID_KABI_USE(6, struct sysv_sem sysvsem);\n"
           "\t_ANDROID_KABI_REPLACE(ANDROID_KABI_RESERVE(7); ANDROID_KABI_RESERVE(8), struct sysv_shm sysvshm);\n"
           "#else\n"
           "\tANDROID_KABI_RESERVE(6);\n"
           "\tANDROID_KABI_RESERVE(7);\n"
           "\tANDROID_KABI_RESERVE(8);\n"
           "#endif\n")
    if old in content:
        content = content.replace(old, new)
    else:
        print("WARNING: could not find exact RESERVE(6/7/8) block in sched.h")

    with open(path, "w") as f:
        f.write(content)
    print("patched", path)


def apply_user_h(path):
    with open(path, "r") as f:
        content = f.read()

    # 1. Comment out mq_bytes inside CONFIG_POSIX_MQUEUE block
    content = re.sub(
        r"(#ifdef CONFIG_POSIX_MQUEUE\n)(\s*)unsigned long mq_bytes.*\n",
        r"\1\2// unsigned long mq_bytes;  // covered by ANDROID_KABI_RESERVE(1)\n",
        content,
    )

    # 2. Replace existing ANDROID_KABI_RESERVE(1);(2); with
    #    #ifdef CONFIG_POSIX_MQUEUE ... USE(1) ... #else ... RESERVE(1/2) ... #endif
    old = "ANDROID_KABI_RESERVE(1);\nANDROID_KABI_RESERVE(2);\n"
    new = ("#ifdef CONFIG_POSIX_MQUEUE\n"
           "\tANDROID_KABI_USE(1, unsigned long mq_bytes);\n"
           "#else\n"
           "\tANDROID_KABI_RESERVE(1);\n"
           "\tANDROID_KABI_RESERVE(2);\n"
           "#endif\n")
    if old in content:
        content = content.replace(old, new)
    else:
        print("WARNING: could not find exact RESERVE(1/2) block in user.h")

    with open(path, "w") as f:
        f.write(content)
    print("patched", path)


if __name__ == "__main__":
    apply_sched_h("include/linux/sched.h")
    apply_user_h("include/linux/sched/user.h")
    print("GKI KABI patches applied successfully")
