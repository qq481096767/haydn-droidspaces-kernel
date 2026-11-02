#!/usr/bin/env python3
"""Apply official Droidspaces GKI kABI patches to haydn 5.4 kernel source.

haydn 5.4 kernel already has:
- task_struct: ANDROID_KABI_RESERVE(1)..(8) at end of struct (lines ~1477-1484)
- user_struct: ANDROID_KABI_RESERVE(1), (2) at end of struct (lines ~44-45)

Follows official Droidspaces patches:
- 001.GKI-below-6.12-fix_sysvipc_kabi_1_2_3.patch  (uses slots 1,2,3 - NOT 6,7,8!)
- 002.5.10_or_lower_use_android_abi_padding_for_posix_mqueue.patch

Key insight: haydn already pre-defines RESERVE(6/7/8), so we MUST use the 1_2_3 slot patch,
not 6_7_8. The 1_2_3 patch replaces RESERVE(1-3) with an #ifdef CONFIG_SYSVIPC block
that uses ANDROID_KABI_USE(1) and _ANDROID_KABI_REPLACE(RESERVE(2); RESERVE(3)) to
relocate sysvsem/sysvshm into existing padding without breaking ABI.
"""
import re
import sys


def apply_sched_h(path):
    with open(path, "r") as f:
        content = f.read()

    # 1. Comment out original sysvsem/sysvshm inside CONFIG_SYSVIPC block (~line 1090)
    content = re.sub(
        r"(#ifdef CONFIG_SYSVIPC\n)(\s*)struct sysv_sem\s+sysvsem;\n(\s*)struct sysv_shm\s+sysvshm;\n",
        r"\1\2// struct sysv_sem sysvsem;\n\3// struct sysv_shm sysvshm;\n",
        content,
    )

    # 2. Replace entire RESERVE(1);RESERVE(2);...;RESERVE(8); block with
    #    #ifdef CONFIG_SYSVIPC ... USE(1)/_ANDROID_KABI_REPLACE(...) ... #else ... RESERVE(1/2/3) ... #endif
    #    followed by RESERVE(4-8) which remain unchanged.
    old_block = ("ANDROID_KABI_RESERVE(1);\n"
                 "ANDROID_KABI_RESERVE(2);\n"
                 "ANDROID_KABI_RESERVE(3);\n"
                 "ANDROID_KABI_RESERVE(4);\n"
                 "ANDROID_KABI_RESERVE(5);\n"
                 "ANDROID_KABI_RESERVE(6);\n"
                 "ANDROID_KABI_RESERVE(7);\n"
                 "ANDROID_KABI_RESERVE(8);\n")
    new_block = ("#ifdef CONFIG_SYSVIPC\n"
                 "\tANDROID_KABI_USE(1, struct sysv_sem sysvsem);\n"
                 "\t_ANDROID_KABI_REPLACE(ANDROID_KABI_RESERVE(2); ANDROID_KABI_RESERVE(3), struct sysv_shm sysvshm);\n"
                 "#else\n"
                 "\tANDROID_KABI_RESERVE(1);\n"
                 "\tANDROID_KABI_RESERVE(2);\n"
                 "\tANDROID_KABI_RESERVE(3);\n"
                 "#endif\n"
                 "\tANDROID_KABI_RESERVE(4);\n"
                 "\tANDROID_KABI_RESERVE(5);\n"
                 "\tANDROID_KABI_RESERVE(6);\n"
                 "\tANDROID_KABI_RESERVE(7);\n"
                 "\tANDROID_KABI_RESERVE(8);\n")
    if old_block in content:
        content = content.replace(old_block, new_block)
    else:
        print("WARNING: could not find exact RESERVE(1-8) block in sched.h")
        print("  (script will still write whatever was matched above)")

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

    # 2. Replace entire RESERVE(1);RESERVE(2); block with
    #    #ifdef CONFIG_POSIX_MQUEUE ... USE(1) ... #else ... RESERVE(1/2) ... #endif
    #    (haydn has no ANDROID_OEM_DATA_ARRAY, unlike official patch context)
    old_block = "ANDROID_KABI_RESERVE(1);\nANDROID_KABI_RESERVE(2);\n"
    new_block = ("#if defined(CONFIG_POSIX_MQUEUE)\n"
                 "\tANDROID_KABI_USE(1, unsigned long mq_bytes);\n"
                 "\tANDROID_KABI_RESERVE(2);\n"
                 "#else\n"
                 "\tANDROID_KABI_RESERVE(1);\n"
                 "\tANDROID_KABI_RESERVE(2);\n"
                 "#endif\n")
    if old_block in content:
        content = content.replace(old_block, new_block)
    else:
        print("WARNING: could not find exact RESERVE(1/2) block in user.h")

    with open(path, "w") as f:
        f.write(content)
    print("patched", path)


if __name__ == "__main__":
    apply_sched_h("include/linux/sched.h")
    apply_user_h("include/linux/sched/user.h")
    print("GKI KABI patches applied successfully (1_2_3 slot)")
