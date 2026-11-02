#!/usr/bin/env bash
#
# pack-boot.sh — 将云端编译的 Image.gz-dtb 打包成 haydn boot.img 并刷入
#
# 使用场景：
#   1. GitHub Actions 编译完成后，下载 Artifacts 得到 Image.gz-dtb 和 dtbo.img
#   2. 在本地 Linux 主机运行此脚本，将新内核打包进当前设备的 boot.img
#   3. 先用 fastboot boot 临时启动测试，确认无误后再 fastboot flash boot 正式刷入
#
# ⚠️ 风险提示：
#   - haydn 是 A/B 分区设备，刷错分区或内核不兼容会导致无法开机（bootloop）
#   - 刷入前务必备份当前 boot.img 和重要数据
#   - 本脚本仅负责打包 boot.img，不负责编译内核
#
# 适用设备：Xiaomi Redmi K40 Pro (haydn, M2012K11C), Linux 5.4 GKI
#
# 依赖工具：fastboot, adb, mkbootimg, cpio, gzip, python3
#

set -euo pipefail

# ==================== 配置区（根据你的设备实际情况调整） ====================

# 内核基地址（与原 boot.img 一致，haydn 通常为 0x80000000）
BOARD_KERNEL_BASE="0x80000000"
# 页面大小
BOARD_KERNEL_PAGESIZE="4096"
# 内核偏移
BOARD_KERNEL_OFFSET="0x00008000"
# Ramdisk 偏移
BOARD_RAMDISK_OFFSET="0x01000000"
# Tags 偏移
BOARD_TAGS_OFFSET="0x00000100"
# boot.img header 版本（haydn 为 A/B 设备，需要 header v3）
BOARD_BOOT_HEADER_VERSION="3"
# 内核命令行（与 stock boot.img 一致，缺少会导致 cgroup/memcg 等问题）
BOARD_KERNEL_CMDLINE="androidboot.console=ttyMSM0 androidboot.hardware=qcom androidboot.memcg=1 androidboot.usbcontroller=a600000.dwc3 cgroup.memory=nokmem,nosocket console=ttyMSM0,115200n8 loop.max_part=7 msm_rtb.filter=0x237 service_locator.enable=1 swiotlb=0 pcie_ports=compat iptable_raw.raw_before_defrag=1 ip6table_raw.raw_before_defrag=1"
# 设备名称（用于 fastboot -s，可选）
DEVICE_SERIAL=""

# ==================== 路径 ====================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

IMAGE_GZ_DTB=""
DTBO_IMG=""
RAMDISK_CPIO_GZ=""
EXISTING_BOOT_IMG=""
OUTPUT_BOOT_IMG="boot-droidspaces.img"
ACTION="pack"   # pack | test | flash | full

# ==================== 工具函数 ====================

log() { echo "[pack-boot] $*"; }
warn() { echo "[pack-boot] ⚠️  $*" >&2; }
err() { echo "[pack-boot] ❌ $*" >&2; exit 1; }

check_tool() {
  if ! command -v "$1" >/dev/null 2>&1; then
    err "未找到必需工具: $1，请先安装（例如 sudo apt-get install $2）"
  fi
}

need_root_for_fastboot() {
  # fastboot 通常不需要 sudo，但某些系统需要权限访问 USB
  true
}

# ==================== 参数解析 ====================

usage() {
  cat <<EOF
用法: $0 [选项] <操作>

操作:
  pack       仅打包 boot.img（不刷入）
  test       打包后用 fastboot boot 临时启动测试（推荐先执行）
  flash      打包后用 fastboot flash boot 正式刷入（危险，需确认）
  full       执行 pack -> test，提示后可继续 flash

选项:
  --kernel <文件>        指定 Image.gz-dtb 路径（默认 ./Image.gz-dtb）
  --dtbo <文件>          指定 dtbo.img 路径（默认 ./dtbo.img）
  --ramdisk <文件>       指定 ramdisk.cpio.gz 路径（默认从现有 boot.img 提取）
  --boot <文件>          指定现有 boot.img 路径（用于提取 ramdisk，默认 ./boot.img）
  --output <文件>        输出 boot.img 路径（默认 boot-droidspaces.img）
  --serial <序列号>      fastboot 设备序列号（多设备时必需）
  --base, --pagesize, --kernel-offset, --ramdisk-offset, --tags-offset
                         覆盖默认引导参数
  -h, --help             显示此帮助

示例:
  $0 --kernel Image.gz-dtb --dtbo dtbo.img --boot boot-backup.img pack
  $0 --kernel Image.gz-dtb --dtbo dtbo.img --boot boot-backup.img test
  $0 --kernel Image.gz-dtb --dtbo dtbo.img --boot boot-backup.img flash
EOF
  exit 0
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      pack|test|flash|full) ACTION="$1"; shift ;;
      --kernel) IMAGE_GZ_DTB="$2"; shift 2 ;;
      --dtbo) DTBO_IMG="$2"; shift 2 ;;
      --ramdisk) RAMDISK_CPIO_GZ="$2"; shift 2 ;;
      --boot) EXISTING_BOOT_IMG="$2"; shift 2 ;;
      --output) OUTPUT_BOOT_IMG="$2"; shift 2 ;;
      --serial) DEVICE_SERIAL="$2"; shift 2 ;;
      --base) BOARD_KERNEL_BASE="$2"; shift 2 ;;
      --pagesize) BOARD_KERNEL_PAGESIZE="$2"; shift 2 ;;
      --kernel-offset) BOARD_KERNEL_OFFSET="$2"; shift 2 ;;
      --ramdisk-offset) BOARD_RAMDISK_OFFSET="$2"; shift 2 ;;
      --tags-offset) BOARD_TAGS_OFFSET="$2"; shift 2 ;;
      -h|--help) usage ;;
      *) err "未知参数: $1" ;;
    esac
  done

  # 设置默认路径（相对当前工作目录）
  IMAGE_GZ_DTB="${IMAGE_GZ_DTB:-./Image.gz-dtb}"
  DTBO_IMG="${DTBO_IMG:-./dtbo.img}"
  EXISTING_BOOT_IMG="${EXISTING_BOOT_IMG:-./boot.img}"
  OUTPUT_BOOT_IMG="${OUTPUT_BOOT_IMG:-./boot-droidspaces.img}"
}

# ==================== 环境检查 ====================

check_env() {
  check_tool fastboot "android-tools-fastboot"
  check_tool adb "android-tools-adb"
  check_tool mkbootimg "android-tools-mkbootimg 或 system-image-common"
  check_tool cpio "cpio"
  check_tool gzip "gzip"
  check_tool python3 "python3"

  # 检查 fastboot 是否能看到设备（仅在 test/flash/full 时需要）
  if [[ "$ACTION" != "pack" ]]; then
    log "检查 fastboot 设备连接..."
    if [[ -n "$DEVICE_SERIAL" ]]; then
      FASTBOOT_ARGS=(-s "$DEVICE_SERIAL")
    else
      FASTBOOT_ARGS=()
    fi
    if ! fastboot "${FASTBOOT_ARGS[@]}" devices >/dev/null 2>&1; then
      warn "fastboot 未检测到设备，请确保设备已进入 fastboot 模式并连接 USB"
      warn "可执行：adb reboot bootloader 进入 fastboot"
    fi
  fi
}

# ==================== 从现有 boot.img 提取 ramdisk ====================

extract_ramdisk() {
  local boot_img="$1"
  local out_ramdisk="$2"

  if [[ ! -f "$boot_img" ]]; then
    err "找不到现有 boot.img: $boot_img，无法提取 ramdisk。请用 --boot 指定，或用 --ramdisk 直接提供 ramdisk.cpio.gz"
  fi

  log "从现有 boot.img 提取 ramdisk: $boot_img"

  local tmpdir
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' RETURN

  # 尝试使用 android-image-tools/unmkbootimg 解包
  if command -v unmkbootimg >/dev/null 2>&1; then
    unmkbootimg -i "$boot_img" -o "$tmpdir" >/dev/null 2>&1 || true
  fi

  # 查找 ramdisk 文件（不同工具命名可能不同：ramdisk.cpio.gz、initrd.img、ramdisk.img 等）
  local ramdisk_file=""
  for candidate in "$tmpdir"/ramdisk.cpio.gz "$tmpdir"/initrd.img "$tmpdir"/ramdisk.img "$tmpdir"/ramdisk.cpio; do
    if [[ -f "$candidate" ]]; then
      ramdisk_file="$candidate"
      break
    fi
  done

  if [[ -z "$ramdisk_file" ]]; then
    # 降级：用 mkbootimg --unpack（部分版本支持）
    if mkbootimg --unpack -i "$boot_img" -o "$tmpdir" >/dev/null 2>&1; then
      for candidate in "$tmpdir"/ramdisk.cpio.gz "$tmpdir"/initrd.img "$tmpdir"/ramdisk.img "$tmpdir"/ramdisk.cpio; do
        if [[ -f "$candidate" ]]; then
          ramdisk_file="$candidate"
          break
        fi
      done
    fi
  fi

  if [[ -z "$ramdisk_file" ]]; then
    err "无法从 boot.img 自动提取 ramdisk，请手动提取 ramdisk.cpio.gz 并用 --ramdisk 指定"
  fi

  # 如果是未压缩的 cpio，压缩成 gzip
  if [[ "$ramdisk_file" == *.cpio && ! "$ramdisk_file" == *.gz ]]; then
    log "压缩 ramdisk 为 gzip..."
    gzip -c "$ramdisk_file" > "$out_ramdisk"
  else
    cp "$ramdisk_file" "$out_ramdisk"
  fi

  log "ramdisk 已提取: $out_ramdisk"
}

# ==================== 打包 boot.img ====================

pack_bootimg() {
  log "开始打包 boot.img: $OUTPUT_BOOT_IMG"

  local ramdisk_to_use="$RAMDISK_CPIO_GZ"
  local tmp_ramdisk=""

  if [[ -z "$ramdisk_to_use" || ! -f "$ramdisk_to_use" ]]; then
    tmp_ramdisk="$(mktemp --suffix=.cpio.gz)"
    extract_ramdisk "$EXISTING_BOOT_IMG" "$tmp_ramdisk"
    ramdisk_to_use="$tmp_ramdisk"
  fi

  if [[ ! -f "$IMAGE_GZ_DTB" ]]; then
    err "找不到内核镜像: $IMAGE_GZ_DTB，请用 --kernel 指定 Image.gz-dtb 路径"
  fi

  local dtbo_arg=()
  if [[ -f "$DTBO_IMG" ]]; then
    # ⚠️ 注意：haydn 是 BOARD_KERNEL_SEPARATED_DTBO=true，dtbo 是独立分区，
    # 不应自动嵌入 boot.img。此处默认不传 --dtbo。
    # 如果你明确需要将 dtbo 合并进 boot.img，可取消下面注释：
    # dtbo_arg=(--dtbo "$DTBO_IMG")
    log "发现 dtbo.img: $DTBO_IMG（haydn dtbo 为独立分区，不自动嵌入 boot.img）"
  else
    warn "未找到 dtbo.img: $DTBO_IMG"
  fi

  mkbootimg \
    --kernel "$IMAGE_GZ_DTB" \
    --ramdisk "$ramdisk_to_use" \
    "${dtbo_arg[@]}" \
    --base "$BOARD_KERNEL_BASE" \
    --pagesize "$BOARD_KERNEL_PAGESIZE" \
    --kernel_offset "$BOARD_KERNEL_OFFSET" \
    --ramdisk_offset "$BOARD_RAMDISK_OFFSET" \
    --tags_offset "$BOARD_TAGS_OFFSET" \
    --header_version "$BOARD_BOOT_HEADER_VERSION" \
    --cmdline "$BOARD_KERNEL_CMDLINE" \
    --output "$OUTPUT_BOOT_IMG"

  log "打包完成: $OUTPUT_BOOT_IMG"
  ls -lh "$OUTPUT_BOOT_IMG"

  # 清理临时 ramdisk
  if [[ -n "$tmp_ramdisk" && -f "$tmp_ramdisk" ]]; then
    rm -f "$tmp_ramdisk"
  fi
}

# ==================== fastboot 操作 ====================

fastboot_cmd() {
  if [[ -n "$DEVICE_SERIAL" ]]; then
    fastboot -s "$DEVICE_SERIAL" "$@"
  else
    fastboot "$@"
  fi
}

test_boot() {
  log "进入 fastboot 测试启动模式（不会刷入闪存）"
  warn "请确保设备已进入 fastboot 模式（音量下 + 电源）"
  read -rp "按回车继续，或 Ctrl+C 取消..." _
  fastboot_cmd boot "$OUTPUT_BOOT_IMG"
  log "如果设备正常进入系统，请运行 Droidspaces Check Requirements 验证 PID_NS / IPC_NS"
}

flash_boot() {
  log "⚠️  即将正式刷入 boot.img 到设备"
  warn "这将覆盖当前 boot 分区，如内核不兼容可能导致无法开机"
  warn "请确保已备份当前 boot.img 和重要数据"
  read -rp "输入 'FLASH' 确认正式刷入: " confirm
  if [[ "$confirm" != "FLASH" ]]; then
    log "已取消刷入"
    exit 0
  fi
  fastboot_cmd flash boot "$OUTPUT_BOOT_IMG"
  log "刷入完成，重启设备..."
  fastboot_cmd reboot
}

# ==================== 主流程 ====================

main() {
  parse_args "$@"
  check_env

  case "$ACTION" in
    pack)
      pack_bootimg
      ;;
    test)
      pack_bootimg
      test_boot
      ;;
    flash)
      pack_bootimg
      flash_boot
      ;;
    full)
      pack_bootimg
      test_boot
      echo ""
      warn "测试启动完成。如果设备正常进入系统且 Droidspaces 检查通过，可执行以下命令正式刷入："
      echo "  $0 --kernel ${IMAGE_GZ_DTB} --dtbo ${DTBO_IMG} --boot ${EXISTING_BOOT_IMG} --serial ${DEVICE_SERIAL:-} flash"
      ;;
  esac
}

main "$@"
