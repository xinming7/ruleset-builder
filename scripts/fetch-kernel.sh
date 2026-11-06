#!/usr/bin/env bash
# 从上游下载内核，解包成 kernel-v1 里的固定资产名，自检 + canary 编译后（可选）上传。
#
# 用法:
#   scripts/fetch-kernel.sh mihomo            # 只下载/校验，产物落在 dist/
#   scripts/fetch-kernel.sh sing-box --upload # 校验通过后覆盖 kernel-v1 的资产
#
# 环境变量:
#   KERNEL_RELEASE  目标 Release tag（默认 kernel-v1）
#   OUT_DIR         暂存目录（默认 dist）
#   GITHUB_OUTPUT   存在时把 sha256 写入该文件，否则打印到 stdout
#
# 退出码: 0 成功；1 上游资产缺失/校验失败；2 参数错误
set -euo pipefail

KERNEL="${1:-}"
UPLOAD="${2:-}"
KERNEL_RELEASE="${KERNEL_RELEASE:-kernel-v1}"
OUT_DIR="${OUT_DIR:-dist}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

case "$KERNEL" in
  mihomo|sing-box) ;;
  *) echo "用法: $0 <mihomo|sing-box> [--upload]" >&2; exit 2 ;;
esac

log() { echo "[${KERNEL}] $*"; }
emit() {
  if [ -n "${GITHUB_OUTPUT:-}" ]; then
    echo "$1=$2" >> "$GITHUB_OUTPUT"
  else
    echo "$1=$2"
  fi
}

case "$KERNEL" in
  mihomo)
    REPO="MetaCubeX/mihomo"
    OUT_NAME="mihomo-linux-amd64"
    # GOAMD64 v1 基线：v2/v3 变体在部分 runner 上会 SIGILL
    asset_name() { echo "mihomo-linux-amd64-v1-$1.gz"; }
    stage() { gunzip -c "$1" > "$2"; }
    verify() { "$1" -v; }
    canary() {
      "$1" convert-ruleset domain yaml "${REPO_ROOT}/mihomo/domain/custom_ai.yaml" /tmp/canary.mrs
      test -s /tmp/canary.mrs
      log "canary ok: $(wc -c < /tmp/canary.mrs) bytes"
    }
    ;;
  sing-box)
    REPO="SagerNet/sing-box"
    OUT_NAME="sing-box-linux-amd64"
    asset_name() { echo "sing-box-${1#v}-linux-amd64.tar.gz"; }
    stage() {
      local tmp
      tmp="$(mktemp -d)"
      tar -xzf "$1" -C "$tmp" --strip-components=1
      cp "${tmp}/sing-box" "$2"
      rm -rf "$tmp"
    }
    # 上游 tar 里除二进制还有 libcronet.so（不是 DT_NEEDED，只在 cronet 传输时 dlopen）。
    # 这里只把单文件拷进干净目录，模拟下游构建流程"只有一个资产文件"的真实条件。
    verify() {
      local iso
      iso="$(mktemp -d)"
      cp "$1" "${iso}/sing-box"
      ( cd "$iso" && ./sing-box version )
      rm -rf "$iso"
    }
    canary() {
      local iso
      iso="$(mktemp -d)"
      cp "$1" "${iso}/sing-box"
      ( cd "$iso" && ./sing-box rule-set compile -o /tmp/canary.srs "${REPO_ROOT}/singbox/rules/custom_direct.json" )
      test -s /tmp/canary.srs
      log "canary ok: $(wc -c < /tmp/canary.srs) bytes"
      rm -rf "$iso"
    }
    ;;
esac

log "查询 ${REPO} 最新稳定版"
LATEST="$(gh api "repos/${REPO}/releases/latest" --jq .tag_name)"
if [ -z "$LATEST" ] || [ "$LATEST" = "null" ]; then
  echo "::error::无法获取 ${REPO} 的 releases/latest" >&2
  exit 1
fi
ASSET="$(asset_name "$LATEST")"
log "上游 ${LATEST}，目标资产 ${ASSET}"

if ! gh api "repos/${REPO}/releases/latest" --jq '.assets[].name' | grep -Fxq "$ASSET"; then
  echo "::error::上游未找到预期资产 ${ASSET}（命名规则可能已变更），不覆盖现有内核" >&2
  gh api "repos/${REPO}/releases/latest" --jq '.assets[].name' | grep -i 'linux-amd64' >&2 || true
  exit 1
fi

mkdir -p "$OUT_DIR"
gh release download "$LATEST" -R "$REPO" -p "$ASSET" -O "${OUT_DIR}/download.${KERNEL}"
stage "${OUT_DIR}/download.${KERNEL}" "${OUT_DIR}/${OUT_NAME}"
chmod +x "${OUT_DIR}/${OUT_NAME}"

log "自检"
verify "${OUT_DIR}/${OUT_NAME}"
log "canary 编译"
canary "${OUT_DIR}/${OUT_NAME}"

SHA="$(sha256sum "${OUT_DIR}/${OUT_NAME}" | awk '{print $1}')"
log "sha256=${SHA}"
emit latest "$LATEST"
emit sha256 "$SHA"

if [ "$UPLOAD" = "--upload" ]; then
  gh release upload "$KERNEL_RELEASE" "${OUT_DIR}/${OUT_NAME}" --clobber
  log "已覆盖 Release ${KERNEL_RELEASE} 中的 ${OUT_NAME}"
fi
