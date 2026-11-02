#!/usr/bin/env python3
"""Apply GKI KABI padding patches to haydn 5.4 kernel source.

Replaces the `patch` command (which failed due to context mismatches)
with direct Python file editing.
"""
import re
import sys


def apply_sched_h(path):
    with open(path, "r") as f:
        lines = f.readlines()

    new_lines = []
    in_sysvipc = False
    for line in lines:
        if "#ifdef CONFIG_SYSVIPC" in line:
            in_sysvipc = True
            new_lines.append(line)
            continue
        if in_sysvipc and "#endif" in line:
            in_sysvipc = False
            new_lines.append(line)
            continue
        if in_sysvipc:
            if re.match(r"\s*struct\s+sysv_sem\s+sysvsem;\s*$", line):
                new_lines.append("// " + line)
                continue
            if re.match(r"\s*struct\s+sysv_shm\s+sysvshm;\s*$", line):
                new_lines.append("// " + line)
                continue
        new_lines.append(line)

    content = "".join(new_lines)

    # Add ABI padding after ANDROID_KABI_RESERVE(4)
    if "ANDROID_KABI_USE(1, struct sysv_sem" not in content:
        content = content.replace(
            "ANDROID_KABI_RESERVE(4);\n",
            "ANDROID_KABI_RESERVE(4);\n\n"
            "#if defined(CONFIG_SYSVIPC)\n"
            "\tANDROID_KABI_USE(1, struct sysv_sem sysvsem);\n"
            "\tANDROID_KABI_USE(1, struct sysv_shm sysvshm);\n"
            "#endif\n",
        )

    with open(path, "w") as f:
        f.write(content)
    print("patched", path)


def apply_user_h(path):
    with open(path, "r") as f:
        content = f.read()

    # Comment out mq_bytes line
    content = re.sub(
        r"^(\s*)unsigned long mq_bytes.*$",
        r"\1// unsigned long mq_bytes;  // How many bytes can be allocated to mqueue?",
        content,
        flags=re.MULTILINE,
    )

    # Add ABI padding after ratelimit_state
    if "ANDROID_KABI_USE(1, unsigned long mq_bytes)" not in content:
        content = content.replace(
            "struct ratelimit_state ratelimit;\n",
            "struct ratelimit_state ratelimit;\n\n"
            "#if defined(CONFIG_POSIX_MQUEUE)\n"
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
