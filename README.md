# Haydn Kernel for Droidspaces (GitHub Actions Build)

Xiaomi Redmi K40 Pro (haydn, M2012K11C) 专用内核，开启 Droidspaces v6.4.0 所需的命名空间和文件系统支持，通过 GitHub Actions 云端编译。

## 背景

Droidspaces 检查在 stock LineageOS 内核中缺少两项 **MUST HAVE** 功能：

- [✗] PID namespace (`CONFIG_PID_NS`)
- [✗] IPC namespace (`CONFIG_IPC_NS`)

此外还缺少推荐项 `CONFIG_DEVTMPFS`（硬件访问模式）。

本项目在 LineageOS 官方 haydn 内核 (`android_kernel_xiaomi_sm8350`, `lineage-23.2`, Linux 5.4 GKI) 基础上，开启上述选项并通过 GitHub Actions 编译产出 `Image.gz-dtb` 和 AnyKernel3 可刷 zip，供你本地打包 `boot.img` 刷入。

## ⚠️ 重要风险提示

1. **Redmi K40 Pro ≠ Redmi K40 Pro+**：不要使用任何号称 "Pro+" 的预编译内核或 boot.img，硬件不同（主摄、快充、部分驱动），刷入可能导致相机失效、充电异常或无法开机。
2. **GKI bootloop**：haydn 内核是 **5.4 GKI**，直接在 defconfig 开启 `CONFIG_PID_NS` / `CONFIG_IPC_NS` / `CONFIG_SYSVIPC` **会导致 vendor 模块 ABI 不匹配，引发 bootloop**。本项目已在编译前自动打 kABI 补丁，请务必保留 `patches/gki/` 中的补丁文件。
3. **Root 要求**：Droidspaces 必须有 root。刷入内核后，请确保你的系统已 root（Magisk / KernelSU / APatch / LineageOS `WITH_SU=true`），并授予 Droidspaces root 权限。
4. **A/B 分区设备**：haydn 是 A/B 分区设备，测试建议先用 `fastboot boot boot.img` 临时启动验证，确认无误后再 `fastboot flash boot` 正式刷入。
5. **dtbo 是独立分区**：haydn 使用 `BOARD_KERNEL_SEPARATED_DTBO=true`，dtbo.img 不应嵌入 boot.img，需单独刷入或保持原样。

## 仓库结构

```
haydn-droidspaces-kernel/
├── .github/workflows/build-haydn.yml   # GitHub Actions 编译流程
├── configs/haydn-droidspaces.fragment   # Droidspaces 所需内核配置片段
├── patches/gki/                         # GKI kABI 补丁（必须，防止 bootloop）
│   ├── 001.GKI-below-6.12-fix_sysvipc_kabi_6_7_8.patch
│   └── 002.5.10_or_lower_use_android_abi_padding_for_posix_mqueue.patch
├── scripts/pack-boot.sh                 # 本地打包 boot.img + fastboot 测试/刷入
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

- `Image.gz-dtb` — 内核镜像（含 dtb）
- `*.dtbo` — 设备树覆盖（独立分区，不自动嵌入 boot.img）
- `haydn-droidspaces-kernel.zip` — AnyKernel3 可刷 zip（可选，直接刷入 recovery/fastboot）

### 3. 本地打包 boot.img 并刷入

在你的 Linux 主机上，安装工具：

```bash
sudo apt-get install android-tools-fastboot android-tools-adb mkbootimg
```

备份当前 boot.img：

```bash
# 设备进入 fastboot 模式
adb reboot bootloader

# 备份 boot 分区
fastboot boot <你现有的 boot.img>   # 先确认能正常启动
# 或者直接从设备提取：
su -c "dd if=/dev/block/by-name/boot of=/sdcard/boot-backup.img"
adb pull /sdcard/boot-backup.img ./boot.img
```

打包新 boot.img：

```bash
cd /root/haydn-droidspaces-kernel/scripts

# 仅打包
./pack-boot.sh --kernel Image.gz-dtb --boot boot.img pack

# 临时启动测试（不刷入，推荐先执行）
./pack-boot.sh --kernel Image.gz-dtb --boot boot.img test

# 确认能正常进入系统后，正式刷入
./pack-boot.sh --kernel Image.gz-dtb --boot boot.img flash
```

### 4. 验证 Droidspaces

1. 在设备上安装 Droidspaces v6.4.0 APK
2. 授予 root 权限
3. 打开 **设置 → Requirements → Check Requirements**
4. 确认以下项变为 `[✓]`：
   - PID namespace
   - IPC namespace
   - devtmpfs（推荐项）

## 与其他项目的对比改进

| 项目 | 改进点 |
|------|--------|
| `charan-gn/guacamole-droidspaces-kernel` | 使用 LineageOS 预编译 clang 工具链（非系统 GCC/Clang，避免不启动） |
| `onyx-oss/konoha-kernel-gki` | GitHub Actions 创建 8GB swap 防止 OOM |
| `daglaroglou/android_kernel_samsung_a54x` | 使用 `scripts/config` 精确修改内核配置，避免重复/冲突行 |
| 通用 GKI 项目 | 加入 `--header_version 3` 和 haydn 专用内核 cmdline |

## 故障排查

| 现象 | 可能原因 | 解决方案 |
|------|---------|---------|
| 编译失败，找不到 defconfig | 文件名不是 `lahaina-qgki_defconfig` | 查看 Actions 日志中 `Available defconfigs` 输出 |
| 编译 OOM（内存不足） | GitHub Actions 2GB runner | 已添加 8GB swap 步骤 |
| 刷入后 bootloop | 未打 kABI 补丁或补丁不匹配 | 确认 `patches/gki/` 中两个补丁文件存在且为真实内容 |
| 刷入后相机/充电异常 | 误用了 Pro+ 的内核或 dtbo | 确认只使用本项目针对 K40 Pro (M2012K11C) 编译的产物 |
| Droidspaces 仍显示 PID_NS/IPC_NS 缺失 | 内核配置未生效 | 在设备上执行 `zcat /proc/config.gz \| grep PID_NS` 确认是否为 `y` |
| boot.img 打包失败 | mkbootimg 版本不支持 `--header_version` | 升级 `android-tools-mkbootimg` 或使用 AOSP 的 mkbootimg |

## 许可证

内核源码遵循 GPL-2.0，本项目构建脚本和配置片段遵循同等开源精神。
