#!/usr/bin/env python3
"""Apply official Droidspaces GKI kABI patches to haydn 5.4 kernel source.

haydn 5.4 kernel already has:
- task_struct: ANDROID_KABI_RESERVE(1)..(8) at end of struct (tab-indented)
- user_struct: ANDROID_KABI_RESERVE(1), (2) at end of struct (tab-indented)

Follows official Droidspaces patches:
- 001.GKI-below-6.12-fix_sysvipc_kabi_1_2_3.patch  (uses slots 1,2,3 - NOT 6,7,8!)
- 002.5.10_or_lower_use_android_abi_padding_for_posix_mqueue.patch

Key insight: haydn already pre-defines RESERVE(6/7/8), so we MUST use the 1_2_3 slot patch.
The 1_2_3 patch replaces RESERVE(1-3) with an #ifdef CONFIG_SYSVIPC block that uses
ANDROID_KABI_USE(1) and _ANDROID_KABI_REPLACE(RESERVE(2); RESERVE(3)) to relocate
sysvsem/sysvshm into existing padding without breaking ABI.
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

    # 2. Replace RESERVE(1-8) block with #ifdef CONFIG_SYSVIPC block (slots 1-3)
    #    followed by RESERVE(4-8) unchanged.
    #    Haydn uses tab indentation.
    old_block = ("\tANDROID_KABI_RESERVE(1);\n"
                 "\tANDROID_KABI_RESERVE(2);\n"
                 "\tANDROID_KABI_RESERVE(3);\n"
                 "\tANDROID_KABI_RESERVE(4);\n"
                 "\tANDROID_KABI_RESERVE(5);\n"
                 "\tANDROID_KABI_RESERVE(6);\n"
                 "\tANDROID_KABI_RESERVE(7);\n"
                 "\tANDROID_KABI_RESERVE(8);\n")
    new_block = ("\t#ifdef CONFIG_SYSVIPC\n"
                 "\t\tANDROID_KABI_USE(1, struct sysv_sem sysvsem);\n"
                 "\t\t_ANDROID_KABI_REPLACE(ANDROID_KABI_RESERVE(2); ANDROID_KABI_RESERVE(3), struct sysv_shm sysvshm);\n"
                 "\t#else\n"
                 "\t\tANDROID_KABI_RESERVE(1);\n"
                 "\t\tANDROID_KABI_RESERVE(2);\n"
                 "\t\tANDROID_KABI_RESERVE(3);\n"
                 "\t#endif\n"
                 "\tANDROID_KABI_RESERVE(4);\n"
                 "\tANDROID_KABI_RESERVE(5);\n"
                 "\tANDROID_KABI_RESERVE(6);\n"
                 "\tANDROID_KABI_RESERVE(7);\n"
                 "\tANDROID_KABI_RESERVE(8);\n")
    if old_block in content:
        content = content.replace(old_block, new_block)
        print("  sched.h: replaced RESERVE(1-8) block with 1_2_3 slot CONFIG_SYSVIPC block")
    else:
        print("WARNING: could not find exact RESERVE(1-8) tab-indented block in sched.h")
        # Debug: show what's actually there
        import re as _re
        m = _re.search(r"\tANDROID_KABI_RESERVE\(1\);.*?\tANDROID_KABI_RESERVE\(8\);", content, _re.DOTALL)
        if m:
            print("  Found block (repr):", repr(m.group()[:200]))

    with open(path, "w") as f:
        f.write(content)
    print("patched", path)


def apply_user_h(path):
    with open(path, "r") as f:
        content = f.read()

    # 1. Comment out mq_bytes inside CONFIG_POSIX_MQUEUE block.
    #    haydn has an intervening comment line "/* protected by mq_lock */"
    #    between the #ifdef and the declaration, so match the declaration itself.
    content = re.sub(
        r"^(\s*)unsigned long mq_bytes;.*$",
        r"\1// unsigned long mq_bytes;  // covered by ANDROID_KABI_USE(1)",
        content,
        flags=re.MULTILINE,
    )

    # 2. Replace RESERVE(1);RESERVE(2); block with #ifdef CONFIG_POSIX_MQUEUE block
    old_block = "\tANDROID_KABI_RESERVE(1);\n\tANDROID_KABI_RESERVE(2);\n"
    new_block = ("\t#if defined(CONFIG_POSIX_MQUEUE)\n"
                 "\t\tANDROID_KABI_USE(1, unsigned long mq_bytes);\n"
                 "\t\tANDROID_KABI_RESERVE(2);\n"
                 "\t#else\n"
                 "\t\tANDROID_KABI_RESERVE(1);\n"
                 "\t\tANDROID_KABI_RESERVE(2);\n"
                 "\t#endif\n")
    if old_block in content:
        content = content.replace(old_block, new_block)
        print("  user.h: replaced RESERVE(1/2) block with CONFIG_POSIX_MQUEUE block")
    else:
        print("WARNING: could not find exact RESERVE(1/2) tab-indented block in user.h")

    with open(path, "w") as f:
        f.write(content)
    print("patched", path)


if __name__ == "__main__":
    apply_sched_h("include/linux/sched.h")
    apply_user_h("include/linux/sched/user.h")

    # 3. Fix "TRACE_INCLUDE_PATH . -> trace file not found" globally:
    #    every directory whose trace header uses TRACE_INCLUDE_PATH "." needs
    #    -I$(src) in its Makefile so define_trace.h can resolve "./<file>.h".
    import os
    fixed_dirs = []
    for root, dirs, files in os.walk("."):
        if "/.git" in root or root.startswith("./.git"):
            continue
        for fn in files:
            if not fn.endswith(".h"):
                continue
            p = os.path.join(root, fn)
            try:
                with open(p, "r", errors="ignore") as f:
                    txt = f.read()
            except OSError:
                continue
            if "#define TRACE_INCLUDE_PATH ." in txt:
                mkfile = os.path.join(root, "Makefile")
                mk = ""
                if os.path.exists(mkfile):
                    with open(mkfile, "r", errors="ignore") as f:
                        mk = f.read()
                if "ccflags-y" not in mk:
                    with open(mkfile, "a") as f:
                        f.write("ccflags-y += -I$(src)\n")
                    fixed_dirs.append(root)
                break  # one trace header per directory is enough
    for d in fixed_dirs:
        print("patched", d + "/Makefile", "(added ccflags-y += -I$(src))")
    if not fixed_dirs:
        print("INFO: no additional TRACE_INCLUDE_PATH directories needed fixing")

    print("GKI KABI patches applied successfully (1_2_3 slot)")
