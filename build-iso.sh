#!/bin/bash
# Spec Hunter USB — ISO Builder
#
# Builds a bootable Alpine Linux ISO with all collector dependencies.
# Output: releases/spec-hunter-v1.0.iso
#
# Runs inside a linux/amd64 Alpine container (see Dockerfile) or any
# x86_64 Linux. Not macOS: xorriso extraction removes the old loop-mount
# requirement, but initramfs must be built for x86_64 with matching Alpine
# packages — the Docker path guarantees that.
#
# Usage: ./build-iso.sh [version]
#   version defaults to "v1.0"

set -euo pipefail

VERSION="${1:-v1.0}"
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
WORK_DIR="/tmp/spec-hunter-build"
RELEASE_DIR="${PROJECT_ROOT}/releases"
ISO_NAME="spec-hunter-${VERSION}.iso"
ALPINE_ISO_URL="https://dl-cdn.alpinelinux.org/alpine/v3.21/releases/x86_64/alpine-standard-3.21.3-x86_64.iso"
ALPINE_ISO_FILE="alpine-standard.iso"

# xorriso both unpacks and repacks the ISO (no loop-mount needed).
REQUIRED_TOOLS="wget xorriso cpio gzip"
MISSING=""
for tool in $REQUIRED_TOOLS; do
    if ! command -v "$tool" &>/dev/null; then
        MISSING="$MISSING $tool"
    fi
done

if [ -n "${MISSING// }" ]; then
    echo "ERROR: Missing required tools:${MISSING}"
    echo "Install with: apk add xorriso cpio gzip wget"
    exit 1
fi

echo "=== Spec Hunter USB ISO Builder ==="
echo "Version: ${VERSION}"
echo "Output:  ${RELEASE_DIR}/${ISO_NAME}"
echo ""

# Clean and prepare
rm -rf "${WORK_DIR}"
mkdir -p "${WORK_DIR}" "${RELEASE_DIR}"

# --- Step 1: Download Alpine ISO ---
echo "[1/6] Downloading Alpine Linux ISO..."
if [ -f "${WORK_DIR}/${ALPINE_ISO_FILE}" ]; then
    echo "  Already downloaded, skipping."
else
    wget -q --show-progress -O "${WORK_DIR}/${ALPINE_ISO_FILE}" "${ALPINE_ISO_URL}"
fi

# --- Step 2: Extract ISO (container-safe: xorriso unpacks, no loop mount) ---
echo "[2/6] Extracting ISO..."
mkdir -p "${WORK_DIR}/iso"

xorriso -osirrox on -indev "${WORK_DIR}/${ALPINE_ISO_FILE}" -extract / "${WORK_DIR}/iso/" >/dev/null 2>&1
chmod -R u+w "${WORK_DIR}/iso"

# Extract initramfs
mkdir -p "${WORK_DIR}/initramfs"
cd "${WORK_DIR}/initramfs" || exit 1
gunzip -c "${WORK_DIR}/iso/boot/initramfs-lts" | cpio -idm 2>/dev/null || true
cd "${PROJECT_ROOT}"

# --- Step 3: Customize initramfs ---
echo "[3/6] Customizing initramfs..."

INITRAMFS="${WORK_DIR}/initramfs"

# Add collector files
mkdir -p "${INITRAMFS}/opt/spec-hunter/collector"
cp -r "${PROJECT_ROOT}/collector/"* "${INITRAMFS}/opt/spec-hunter/collector/"
cp "${PROJECT_ROOT}/requirements.txt" "${INITRAMFS}/opt/spec-hunter/"
cp "${PROJECT_ROOT}/config.yaml" "${INITRAMFS}/opt/spec-hunter/" 2>/dev/null || true

# Dependencies: install Alpine's own musl/x86_64 packages INTO the initramfs
# root via apk --root. Never pip-install from the build host — host packages
# are the wrong libc/arch and break imports in the booted initramfs.
#
# Package set = every external tool the collectors invoke (from the 8
# collector/*.py files): dmidecode (identity/ram), lscpu (cpu), lsblk/
# smartctl/nvme (storage), upower (battery), lshw/ip/hciconfig/btmgmt
# (network), v4l2-ctl (camera), plus the boot hook's wpa_supplicant/dhcpcd.
# Root cause of the earlier "unable to select packages": `--initdb` creates a
# FRESH apk db in the target root, and the target had no /etc/apk/repositories,
# so apk had no package index and resolved NOTHING. Explicit -X repos make the
# target self-sufficient without copying any host files.
# edid-decode is NOT in Alpine 3.21 (main/community) — with repos present it is
# the one unresolvable name (build aborted correctly). display.py falls back to
# /sys/class/drm/*/edid parsing without it (resolution → N/A, manufacturer
# still collected), so it is omitted deliberately.
# python3 is explicit — the booted Alpine standard ISO ships no interpreter,
# and collectors run under `#!/usr/bin/env python3`.
# FAIL FAST: an ISO without python3/tools is useless — a missing package must
# abort the build, not emit a broken image.
apk add --root "${INITRAMFS}" --initdb --no-cache \
    -X https://dl-cdn.alpinelinux.org/alpine/v3.21/main \
    -X https://dl-cdn.alpinelinux.org/alpine/v3.21/community \
    python3 py3-requests py3-yaml \
    dmidecode smartmontools nvme-cli util-linux \
    lshw iproute2 bluez v4l-utils upower \
    wpa_supplicant dhcpcd \
    || { echo "ERROR: apk add failed — collector tools missing, aborting"; exit 1; }

# Create auto-start script
mkdir -p "${INITRAMFS}/etc/local.d"
cat > "${INITRAMFS}/etc/local.d/collector.start" << 'SCRIPT'
#!/bin/sh
# Spec Hunter USB — Auto-run on boot

echo "=== Spec Hunter USB Collector ==="
echo "Starting hardware collection..."

# Wait for devices to settle
sleep 3

# Check for config
if [ ! -f /opt/spec-hunter/config.yaml ]; then
    echo "ERROR: config.yaml not found in /opt/spec-hunter/"
    echo "Create one with endpoint URL, API key, and WiFi credentials."
    sleep 30
    poweroff
fi

# Connect WiFi if ssid configured
SSID=$(grep -A3 "^wifi:" /opt/spec-hunter/config.yaml | grep "ssid:" | cut -d'"' -f2 2>/dev/null || echo "")
if [ -n "$SSID" ] && [ "$SSID" != "" ]; then
    echo "Connecting to WiFi: $SSID"
    PASS=$(grep -A3 "^wifi:" /opt/spec-hunter/config.yaml | grep "password:" | cut -d'"' -f2 2>/dev/null || echo "")
    if [ -n "$PASS" ]; then
        wpa_passphrase "$SSID" "$PASS" > /etc/wpa_supplicant/wpa_supplicant.conf
        # Kodung_5G is WPA3-Personal (SAE). wpa_passphrase writes only the
        # PSK; on pure-SAE networks an explicit key_mgmt is needed for some
        # versions. This covers WPA2/WPA3-transition AND pure-SAE.
        echo "key_mgmt=WPA-PSK SAE" >> /etc/wpa_supplicant/wpa_supplicant.conf
        # WiFi interface isn't always wlan0 (wl*/wlp* on modern systems) —
        # detect the wireless NIC from sysfs.
        IFACE=$(ls /sys/class/net 2>/dev/null | grep -E '^wl' | head -1)
        [ -z "$IFACE" ] && IFACE="wlan0"
        echo "WiFi interface: $IFACE"
        wpa_supplicant -B -i "$IFACE" -c /etc/wpa_supplicant/wpa_supplicant.conf
        dhcpcd "$IFACE"
    fi
fi

# Run collector
python3 /opt/spec-hunter/collector/main.py
SCRIPT
chmod +x "${INITRAMFS}/etc/local.d/collector.start"

# Enable local service
if [ -f "${INITRAMFS}/etc/init.d/local" ]; then
    mkdir -p "${INITRAMFS}/etc/runlevels/default"
    ln -sf /etc/init.d/local "${INITRAMFS}/etc/runlevels/default/local" 2>/dev/null || true
fi

# Add marker file
mkdir -p "${INITRAMFS}/opt/spec-hunter"
echo "${VERSION}" > "${INITRAMFS}/opt/spec-hunter/VERSION"

# --- Step 4: Repack initramfs ---
echo "[4/6] Repacking initramfs..."
cd "${INITRAMFS}" || exit 1
find . | cpio -o -H newc 2>/dev/null | gzip -9 > "${WORK_DIR}/iso/boot/initramfs-lts"
cd "${PROJECT_ROOT}"

# --- Step 5: Build ISO ---
echo "[5/6] Building ISO..."

xorriso -as mkisofs \
    -isohybrid-mbr /usr/share/syslinux/isohdpfx.bin \
    -c boot/syslinux/boot.cat \
    -b boot/syslinux/isolinux.bin \
    -no-emul-boot \
    -boot-load-size 4 \
    -boot-info-table \
    -eltorito-alt-boot \
    -e boot/grub/efi.img \
    -no-emul-boot \
    -isohybrid-gpt-basdat \
    -o "${RELEASE_DIR}/${ISO_NAME}" \
    "${WORK_DIR}/iso/"

# --- Step 6: Report ---
if [ -f "${RELEASE_DIR}/${ISO_NAME}" ]; then
    echo ""
    echo "[6/6] === Build Complete ==="
    echo "ISO: ${RELEASE_DIR}/${ISO_NAME}"
    echo "Size: $(du -h "${RELEASE_DIR}/${ISO_NAME}" | cut -f1)"
    echo ""
    echo "Write to USB with:"
    echo "  sudo dd if=${RELEASE_DIR}/${ISO_NAME} of=/dev/sbX bs=4M conv=fsync status=progress"
    echo ""
    echo "Then boot an x86_64 laptop from the USB."
else
    echo "ERROR: ISO build failed"
    exit 1
fi

# Cleanup
rm -rf "${WORK_DIR}"