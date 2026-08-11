#
# Spec Hunter USB — ISO builder container.
# Produces spec-hunter-<version>.iso inside /build (bind-mounted).
#
# Usage:
#   docker build --platform linux/amd64 -t spec-iso .
#   docker run --rm -v "$(pwd):/build" spec-iso v1.0
#
# x86_64 Alpine is non-negotiable: the ISO is an x86_64 Alpine image, and
# build-iso.sh installs Alpine's own py3-*/x86_64 packages into the initramfs
# via apk --root — architecture must match the target.
FROM alpine:3.21

RUN apk add --no-cache xorriso cpio gzip wget bash syslinux

WORKDIR /build

# build-iso.sh downloads the Alpine ISO to /tmp, unpacks it with xorriso,
# injects the collector + deps + auto-start hook into the initramfs, and
# repacks a hybrid (BIOS+UEFI) ISO. syslinux provides isohdpfx.bin for the
# el-torito MBR.
ENTRYPOINT ["/build/build-iso.sh"]