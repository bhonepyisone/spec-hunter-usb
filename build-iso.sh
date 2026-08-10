#!/bin/bash
# Spec Hunter USB — ISO Builder
#
# Builds a bootable Alpine Linux ISO with all collector dependencies.
# Output: releases/spec-hunter-v1.0.iso
#
# Prerequisites: sudo, wget, rsync, xorriso (or mkisofs)
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

REQUIRED_TOOLS="wget unsquashfs mksquashfs xorriso rsync"
MISSING=""
for tool in $REQUIRED_TOOLS; do
    if ! command -v "$tool" &>/dev/null; then
        MISSING="$MISSING $tool"
    fi
done

# Fallback: use genisoimage if xorriso not available
if echo "$MISSING" | grep -q "xorriso"; then
    if command -v genisoimage &>/dev/null; then
        MKISOFS="genisoimage"
        MISSING=$(echo "$MISSING" | sed 's/xorriso//')
    elif command -v mkisofs &>/dev/null; then
        MKISOFS="mkisofs"
        MISSING=$(echo "$MISSING" | sed 's/xorriso//')
    else
        MKISOFS=""
    fi
else
    MKISOFS="xorriso"
fi

if [ -n "${MISSING// }" ]; then
    echo "ERROR: Missing required tools:${MISSING}"
    echo "Install with: sudo apk add squashfs-tools xorriso rsync wget"
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
echo "[1/5] Downloading Alpine Linux ISO..."
if [ -f "${WORK_DIR}/${ALPINE_ISO_FILE}" ]; then
    echo "  Already downloaded, skipping."
else
    wget -q --show-progress -O "${WORK_DIR}/${ALPINE_ISO_FILE}" "${ALPINE_ISO_URL}"
fi

# --- Step 2: Extract ISO ---
echo "[2/5] Extracting ISO..."
mkdir -p "${WORK_DIR}/iso"
mkdir -p "${WORK_DIR}/iso-mount"

mount -o loop "${WORK_DIR}/${ALPINE_ISO_FILE}" "${WORK_DIR}/iso-mount"
rsync -a "${WORK_DIR}/iso-mount/" "${WORK_DIR}/iso/"
umount "${WORK_DIR}/iso-mount"
rmdir "${WORK_DIR}/iso-mount"

# Extract initramfs
mkdir -p "${WORK_DIR}/initramfs"
cd "${WORK_DIR}/initramfs"
gunzip -c "${WORK_DIR}/iso/boot/initramfs-lts" | cpio -idm 2>/dev/null || true
cd "${PROJECT_ROOT}"

# --- Step 3: Customize initramfs ---
echo "[3/5] Customizing initramfs..."

INITRAMFS="${WORK_DIR}/initramfs"

# Add collector files
mkdir -p "${INITRAMFS}/opt/spec-hunter/collector"
cp -r "${PROJECT_ROOT}/collector/"* "${INITRAMFS}/opt/spec-hunter/collector/"
cp "${PROJECT_ROOT}/requirements.txt" "${INITRAMFS}/opt/spec-hunter/"
cp "${PROJECT_ROOT}/config.yaml" "${INITRAMFS}/opt/spec-hunter/" 2>/dev/null || true

# Install Python packages into initramfs
python3 -m pip install --target="${INITRAMFS}/opt/spec-hunter/lib" \
    -r "${PROJECT_ROOT}/requirements.txt" 2>/dev/null || \
    echo "  WARNING: pip install failed — run 'pip install -r requirements.txt' manually"

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
        wpa_supplicant -B -i wlan0 -c /etc/wpa_supplicant/wpa_supplicant.conf
        dhcpcd wlan0
    fi
fi

# Run collector
export PYTHONPATH="/opt/spec-hunter/lib:$PYTHONPATH"
python3 /opt/spec-hunter/collector/main.py
SCRIPT
chmod +x "${INITRAMFS}/etc/local.d/collector.start"

# Enable local service
if [ -f "${INITRAMFS}/etc/init.d/local" ]; then
    # Add local to boot runlevel
    mkdir -p "${INITRAMFS}/etc/runlevels/default"
    ln -sf /etc/init.d/local "${INITRAMFS}/etc/runlevels/default/local" 2>/dev/null || true
fi

# Add marker file
mkdir -p "${INITRAMFS}/opt/spec-hunter"
echo "${VERSION}" > "${INITRAMFS}/opt/spec-hunter/VERSION"

# --- Step 4: Repack initramfs ---
echo "[4/5] Repacking initramfs..."
cd "${INITRAMFS}"
find . | cpio -o -H newc 2>/dev/null | gzip -9 > "${WORK_DIR}/iso/boot/initramfs-lts"
cd "${PROJECT_ROOT}"

# --- Step 5: Build ISO ---
echo "[5/5] Building ISO..."

ISO_ARGS=""
if [ "$MKISOFS" = "xorriso" ]; then
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
elif [ "$MKISOFS" = "genisoimage" ]; then
    genisoimage \
        -b boot/syslinux/isolinux.bin \
        -c boot/syslinux/boot.cat \
        -no-emul-boot \
        -boot-load-size 4 \
        -boot-info-table \
        -eltorito-alt-boot \
        -e boot/grub/efi.img \
        -no-emul-boot \
        -o "${RELEASE_DIR}/${ISO_NAME}" \
        "${WORK_DIR}/iso/"
else
    mkisofs \
        -b boot/syslinux/isolinux.bin \
        -c boot/syslinux/boot.cat \
        -no-emul-boot \
        -boot-load-size 4 \
        -boot-info-table \
        -o "${RELEASE_DIR}/${ISO_NAME}" \
        "${WORK_DIR}/iso/"
fi

# Write to USB helper
if [ -f "${RELEASE_DIR}/${ISO_NAME}" ]; then
    echo ""
    echo "=== Build Complete ==="
    echo "ISO: ${RELEASE_DIR}/${ISO_NAME}"
    echo "Size: $(du -h "${RELEASE_DIR}/${ISO_NAME}" | cut -f1)"
    echo ""
    echo "Write to USB with:"
    echo "  sudo dd if=${RELEASE_DIR}/${ISO_NAME} of=/dev/sdX bs=4M status=progress && sync"
    echo ""
    echo "Or use:"
    echo "  sudo dd if=${RELEASE_DIR}/${ISO_NAME} of=/dev/sdX bs=4M conv=fsync status=progress"
else
    echo "ERROR: ISO build failed"
    exit 1
fi

# Cleanup
rm -rf "${WORK_DIR}"
