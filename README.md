# Haydn Kernel for Droidspaces (GitHub Actions Build)

Xiaomi Redmi K40 Pro (haydn, M2012K11C) 专用内核，开启 Droidspaces 所需的命名空间和文件系统支持，通过 GitHub Actions 云端编译。

## ✅ 当前状态（已验证）

编译已成功并在真机验证：

- **GitHub Actions**：Run #b930733 编译成功（commit `b930733`）
- **临时启动**：`fastboot boot test-final.img` 正常进入系统，无 bootloop
- **Droidspaces v7.1.0 Check Requirements**：**全部 REQUIRED 功能 [✓]**
  - Root privileges、Linux version、PID namespace、Mount namespace、UTS namespace、IPC namespace、pivot_root、/proc、/sys、Seccomp —— 全部通过
  - devtmpfs（推荐项）亦已开启

可选项（非必需）保持关闭：Macvlan、IPv6 NAT、CPU limit（CFS_BANDWIDTH）、Process limit（CGROUP_PIDS）、User namespaces。其中 CFS_BANDWIDTH / CGROUP_PIDS 会破坏 kABI 导致 vendor 模块拒载 → bootloop，已在配置片段中明确禁用；USER_NS 关闭符合 Droidspaces 硬化建议。

## 支持机型

本项目基于 LineageOS haydn 内核源码 (`android_kernel_xiaomi_sm8350`, `lineage-23.2`)，该源码同时服务于以下机型（共享同一内核代码库）：

| 机型 | 代号 | 型号 | 备注 |
|------|------|------|------|
| Redmi K40 Pro | haydn (variant2) | M2012K11C | 本项目主测机型 |
| Mi 11i（国际版） | haydn (variant1) | M2011K10G | 同内核源码，内核配置可通用 |

> Mi 11i 与 Redmi K40 Pro 共享 `android_kernel_xiaomi_sm8350` 内核源码，本项目编出的内核 Image 在两款机型上配置相同。但 dtbo 分区和部分分区布局可能存在差异，Mi 11i 用户刷入前请务必先用 `fastboot boot` 临时验证，确认无误后再正式刷入。

## 背景

Droidspaces 检查在 stock LineageOS 内核中缺少两项 **MUST HAVE** 功能：

- [✗] PID namespace (`CONFIG_PID_NS`)
- [✗] IPC namespace (`CONFIG_IPC_NS`)

此外还缺少推荐项 `CONFIG_DEVTMPFS`（硬件访问模式）。

本项目在 LineageOS 官方 haydn 内核 (`android_kernel_xiaomi_sm8350`, `lineage-23.2`, Linux 5.4 GKI) 基础上，开启上述选项并通过 GitHub Actions 编译产出 uncompressed `Image`（5.4 kernel 无 `Image.gz-dtb` 规则，dtbo 走分离分区）和 AnyKernel3 可刷 zip，供你本地打包 `boot.img` 刷入。

## ⚠️ 重要风险提示

1. **Redmi K40 Pro ≠ Redmi K40 Pro+**：不要使用任何号称 "Pro+" 的预编译内核或 boot.img，硬件不同（主摄、快充、部分驱动），刷入可能导致相机失效、充电异常或无法开机。
2. **GKI bootloop**：haydn 内核是 **5.4 GKI**，直接在 defconfig 开启 `CONFIG_PID_NS` / `CONFIG_IPC_NS` / `CONFIG_SYSVIPC` **会导致 vendor 模块 ABI 不匹配，引发 bootloop**。本项目已在编译前自动打 kABI 补丁，请务必保留 `patches/gki/` 中的补丁文件。
3. **Root 要求**：Droidspaces 必须有 root。刷入内核后，请确保你的系统已 root（Magisk / KernelSU / APatch / LineageOS `WITH_SU=true`），并授予 Droidspaces root 权限。
4. **A/B 分区设备**：haydn 是 A/B 分区设备，测试建议先用 `fastboot boot boot.img` 临时启动验证，确认无误后再 `fastboot flash boot` 或 `fastboot flash boot_b` 正式刷入。
5. **dtbo 保持原样**：haydn 使用 `BOARD_KERNEL_SEPARATED_DTBO=true`，dtbo 是独立分区。本项目改动仅为内核配置、不修改 DTS，stock dtbo 依然有效，**请勿重刷 dtbo**。
6. **工具链约束**：GKI 内核必须用 Android clang（LTO+CFI+SCS）编译，否则 vendor 模块（带 CFI+SCS）加载时内核崩溃 → black screen/bootloop。本项目使用 Neutron Clang 06092026（clang 24）+ `LLVM=1 LLVM_IAS=1`，与成功参考项目 quilluna 完全一致。

```
haydn-droidspaces-kernel/
├── .github/workflows/build-haydn.yml   # GitHub Actions 编译流程
├── configs/haydn-droidspaces.fragment   # Droidspaces 所需内核配置片段（MUST HAVE 覆盖项）
├── configs/haydn-stock.config           # 从 stock boot.img IKCONFIG 提取的完整基准配置（含 LTO/CFI/SCS=y 用户值）
├── configs/anykernel.haydn.sh           # AnyKernel3 脚本（AK3 模板格式，仅刷 boot，不触碰 dtbo）
├── patches/gki/                         # GKI kABI 补丁（必须，防止 bootloop）
│   ├── 001.GKI-below-6.12-fix_sysvipc_kabi_6_7_8.patch
│   └── 002.5.10_or_lower_use_android_abi_padding_for_posix_mqueue.patch
├── scripts/pack-boot.sh                 # 本地打包 boot.img + fastboot 测试/刷入
├── scripts/apply_gki_kabi.py            # kABI 补丁应用脚本（官方 1_2_3 槽位，haydn 已占用 6/7/8）
└── README.md
```

## 必须手动添加的文件（kABI 补丁）

已包含真实补丁，无需额外下载。`patches/gki/` 目录下的两个文件已从 Droidspaces-OSS 官方仓库下载并替换占位内容。

## 使用方法

### 1. 推送到 GitHub 触发编译

在 GitHub 上创建一个新仓库（公开或私有均可），将本文件夹的全部内容推送上去：

```bash
cd /root/haydn-droidspaces-kernel
git init
git add .
git commit -m "feat: haydn droidspaces kernel build with GKI kABI patches"
git remote add origin https://github.com/<你的用户名>/haydn-droidspaces-kernel.git
git push -u origin main
```

推送后，GitHub Actions 会自动开始编译（在 **Actions → Build Haydn Kernel for Droidspaces** 查看进度）。

### 2. 下载产物

编译完成后，进入 **Actions → 最近一次运行 → Artifacts**，下载 `haydn-kernel-droidspaces`，得到：

- `Image` — 内核镜像（未压缩 ARM64 Image，5.4 GKI 内核无 `Image.gz-dtb` 规则，dtbo 走分离分区）
- `haydn-droidspaces-kernel.zip` — AnyKernel3 可刷 zip（仅刷 boot 分区，不触碰 dtbo）

### 3. 本地打包 boot.img 并刷入

在你的 Linux 主机上，安装工具：

```bash
sudo apt-get install android-tools-fastboot android-tools-adb mkbootimg
```

备份当前 boot 分区（A/B 设备建议备份 boot_a 和 boot_b）：

```bash
# 设备进入 fastboot 模式
adb reboot bootloader

# 从设备提取当前 boot 做备份
su -c "dd if=/dev/block/by-name/boot_b of=/sdcard/boot_b-backup.img"
adb pull /sdcard/boot_b-backup.img ./boot_b-backup.img
```

打包新 boot.img（使用新 Image + 原 Magisk ramdisk，可参考 scripts/pack-boot.sh）：

```bash
cd /root/haydn-droidspaces-kernel/scripts

# 仅打包（或按 pack-boot.sh 用法）
./pack-boot.sh --kernel Image --boot boot.img pack

# 临时启动测试（不刷入，推荐先执行，失败重启即恢复）
fastboot boot boot.img

# 确认能正常进入系统后，正式刷入 B 槽（A 槽保留当前可用镜像做备份）
fastboot flash boot_b boot.img
```

### 4. 验证 Droidspaces

1. 在设备上安装 Droidspaces APK
2. 授予 root 权限
3. 打开 **设置 → Requirements → Check Requirements**
4. 确认以下项变为 `[✓]`：
   - PID namespace
   - IPC namespace
   - devtmpfs（推荐项）

若任一 REQUIRED 项仍为 `[✗]`，请在设备上执行 `zcat /proc/config.gz | grep PID_NS` 确认是否为 `y`（haydn 无 `/proc/config.gz` 时需从 IKCONFIG 提取）。

## 故障排查

| 现象 | 可能原因 | 解决方案 |
|------|---------|---------|
| 编译失败，找不到 defconfig | 文件名不是 `lahaina-qgki_defconfig` | 查看 Actions 日志中 `Available defconfigs` 输出 |
| 编译 OOM（内存不足） | GitHub Actions 2GB runner | 已添加 8GB swap 步骤 |
| 刷入后 bootloop | 未打 kABI 补丁或补丁不匹配 | 确认 `patches/gki/` 中两个补丁文件存在且为真实内容 |
| 刷入后黑屏/无 logo | **工具链不匹配**：Ubuntu clang 14 或 Neutron clang 带 glibc patch 会静默关闭 LTO/CFI/SCS，vendor 模块加载崩溃 | 必须用 Neutron Clang 06092026 + `LLVM=1 LLVM_IAS=1`，**不加 glibc patch**，config 阶段直接用 `haydn-stock.config` 用户值，不跑 `olddefconfig`（避免 kconfig 探测重置 LTO/CFI/SCS） |
| 刷入后相机/充电异常 | 误用了 Pro+ 的内核或 dtbo | 确认只使用本项目针对 K40 Pro (M2012K11C) 编译的产物 |
| Droidspaces 仍显示 PID_NS/IPC_NS 缺失 | 内核配置未生效 | 在设备上执行 `zcat /proc/config.gz \| grep PID_NS` 确认是否为 `y`（haydn 无 `/proc/config.gz` 时需从 IKCONFIG 提取） |
| boot.img 打包失败 | mkbootimg 版本不支持 `--header_version` | 升级 `android-tools-mkbootimg` 或使用 AOSP 的 mkbootimg |

## 与其他项目的对比改进

| 项目 | 改进点 |
|------|--------|
| `charan-gn/guacamole-droidspaces-kernel` | 使用 LineageOS 预编译 clang 工具链（非系统 GCC/Clang，避免不启动） |
| `onyx-oss/konoha-kernel-gki` | GitHub Actions 创建 8GB swap 防止 OOM |
| `daglaroglou/android_kernel_samsung_a54x` | 使用 `scripts/config` 精确修改内核配置，避免重复/冲突行 |
| 通用 GKI 项目 | 加入 `--header_version 3` 和 haydn 专用内核 cmdline |

## 许可证

内核源码遵循 GPL-2.0，本项目构建脚本和配置片段遵循同等开源精神。
