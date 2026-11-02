#!/usr/bin/env python3
"""Apply GKI KABI padding patches to haydn 5.4 kernel source.

Strictly follows the official Droidspaces GKI patches:
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
        # Comment out sysvsem/sysvshm fields inside CONFIG_SYSVIPC block in task_struct
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

    # Insert ABI padding after ANDROID_KABI_RESERVE(5) in task_struct
    # Official patch: use slots 6, 7, 8 with _ANDROID_KABI_REPLACE
    # Only insert if not already patched (avoid duplicate on re-runs)
    if "#ifdef CONFIG_SYSVIPC\n\tANDROID_KABI_USE(6, struct sysv_sem" not in content:
        content = content.replace(
            "ANDROID_KABI_RESERVE(5);\n",
            "ANDROID_KABI_RESERVE(5);\n\n"
            "#ifdef CONFIG_SYSVIPC\n"
            "\tANDROID_KABI_USE(6, struct sysv_sem sysvsem);\n"
            "\t_ANDROID_KABI_REPLACE(ANDROID_KABI_RESERVE(7); ANDROID_KABI_RESERVE(8), struct sysv_shm sysvshm);\n"
            "#else\n"
            "\tANDROID_KABI_RESERVE(6);\n"
            "\tANDROID_KABI_RESERVE(7);\n"
            "\tANDROID_KABI_RESERVE(8);\n"
            "#endif\n",
        )

    with open(path, "w") as f:
        f.write(content)
    print("patched", path)


def apply_user_h(path):
    with open(path, "r") as f:
        content = f.read()

    # Comment out mq_bytes line inside CONFIG_POSIX_MQUEUE
    content = re.sub(
        r"^(\s*)unsigned long mq_bytes.*$",
        r"\1// unsigned long mq_bytes;  // How many bytes can be allocated to mqueue?",
        content,
        flags=re.MULTILINE,
    )

    # Insert ABI padding after struct ratelimit_state ratelimit;
    # Official patch: use slot 1 for mq_bytes, then RESERVE(2)
    if "ANDROID_KABI_USE(1, unsigned long mq_bytes)" not in content:
        content = content.replace(
            "struct ratelimit_state ratelimit;\n",
            "struct ratelimit_state ratelimit;\n\n"
            "#if defined(CONFIG_POSIX_MQUEUE)\n"
            "\tANDROID_KABI_USE(1, unsigned long mq_bytes);\n"
            "\tANDROID_KABI_RESERVE(2);\n"
            "\tANDROID_OEM_DATA_ARRAY(1, 2);\n"
            "#else\n"
            "\tANDROID_KABI_RESERVE(1);\n"
            "\tANDROID_KABI_RESERVE(2);\n"
            "\tANDROID_OEM_DATA_ARRAY(1, 2);\n"
            "#endif\n",
        )

    with open(path, "w") as f:
        f.write(content)
    print("patched", path)


if __name__ == "__main__":
    apply_sched_h("include/linux/sched.h")
    apply_user_h("include/linux/sched/user.h")
    print("GKI KABI patches applied successfully")
