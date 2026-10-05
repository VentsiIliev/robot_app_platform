#!/usr/bin/env bash
set -euo pipefail

PROVISION_ONLY=false
if [[ ${1:-} == --provision-only && $# -eq 1 ]]; then
    PROVISION_ONLY=true
elif [[ $# -ne 0 ]]; then
    echo "Usage: $0 [--provision-only]" >&2
    exit 2
fi

# ============================================================
# PL PROJECT Remote Support Installer
# Ubuntu 24.04 / amd64
#
# Supports:
#   - Fresh installation
#   - Existing RustDesk installation
#   - Partially installed/broken RustDesk package
#   - Missing package dependencies
#   - Ubuntu unattended upgrades / APT lock contention
#
# Installs:
#   PL PROJECT Remote Support v1.4.9-plproject.1
#
# Based on RustDesk 1.4.9
# ============================================================

RELEASE="v1.4.9-plproject.1"
PACKAGE="rustdesk-1.4.9.deb"
EXPECTED_VERSION="1.4.9"

DOWNLOAD_URL="https://github.com/VentsiIliev/plproject_remote_support/releases/download/${RELEASE}/${PACKAGE}"

# Maximum time to wait for Ubuntu's package manager.
# 900 seconds = 15 minutes.
APT_LOCK_TIMEOUT=900

TMP_DIR="$(mktemp -d)"
DEB="${TMP_DIR}/${PACKAGE}"

cleanup() {
    rm -rf "$TMP_DIR"
}
trap cleanup EXIT


# ============================================================
# Helper: wait for APT/dpkg
# ============================================================

wait_for_apt() {

    local waited=0

    while sudo fuser \
        /var/lib/dpkg/lock-frontend \
        /var/lib/dpkg/lock \
        /var/cache/apt/archives/lock \
        /var/lib/apt/lists/lock \
        >/dev/null 2>&1
    do

        if [ "$waited" -eq 0 ]; then
            echo
            echo "Ubuntu package manager is currently busy."
            echo "Waiting for the running update/install process to finish..."
        fi

        if [ "$waited" -ge "$APT_LOCK_TIMEOUT" ]; then
            echo
            echo "ERROR: Ubuntu package manager is still busy after"
            echo "${APT_LOCK_TIMEOUT} seconds."
            echo
            echo "A system update or another package installation may"
            echo "still be running."
            echo
            echo "The installer did NOT remove any package-manager locks."
            exit 1
        fi

        # Print a status message every 10 seconds.

        if [ $((waited % 10)) -eq 0 ]; then
            echo "  Waiting for package manager... ${waited}s"
        fi

        sleep 2
        waited=$((waited + 2))
    done

    if [ "$waited" -gt 0 ]; then
        echo "Package manager is available."
        echo
    fi
}


# ============================================================
# Header
# ============================================================

echo
echo "============================================================"
echo " PL PROJECT Remote Support Installer"
echo " Release: ${RELEASE}"
echo "============================================================"
echo


# ------------------------------------------------------------
# 1. Architecture check
# ------------------------------------------------------------

ARCH="$(dpkg --print-architecture)"

if [ "$ARCH" != "amd64" ]; then
    echo "ERROR: This build requires amd64."
    echo "Detected architecture: $ARCH"
    exit 1
fi

echo "[1/8] Architecture: $ARCH"


# ------------------------------------------------------------
# 2. Required tools
# ------------------------------------------------------------

echo
echo "[2/8] Checking required tools..."

# fuser is normally provided by psmisc on Ubuntu.
# We use it to safely determine whether apt/dpkg is busy.

if ! command -v fuser >/dev/null 2>&1; then

    echo "Installing required package: psmisc"

    # We cannot use wait_for_apt yet because fuser itself is missing.
    # apt-get's lock timeout handles this bootstrap case.

    sudo apt-get \
        -o DPkg::Lock::Timeout="$APT_LOCK_TIMEOUT" \
        update

    sudo apt-get \
        -o DPkg::Lock::Timeout="$APT_LOCK_TIMEOUT" \
        install -y psmisc
fi


if ! command -v wget >/dev/null 2>&1; then

    echo "Installing required package: wget"

    wait_for_apt

    sudo apt-get \
        -o DPkg::Lock::Timeout="$APT_LOCK_TIMEOUT" \
        update

    wait_for_apt

    sudo apt-get \
        -o DPkg::Lock::Timeout="$APT_LOCK_TIMEOUT" \
        install -y wget
fi

echo "Required tools are available."


# ------------------------------------------------------------
# 3. Download release
# ------------------------------------------------------------

echo
echo "[3/8] Downloading PL PROJECT Remote Support..."

wget \
    --https-only \
    --show-progress \
    -O "$DEB" \
    "$DOWNLOAD_URL"

echo
echo "Download complete."


# ------------------------------------------------------------
# 4. Verify Debian package
# ------------------------------------------------------------

echo
echo "[4/8] Verifying package..."

PKG_NAME="$(dpkg-deb -f "$DEB" Package)"
PKG_VERSION="$(dpkg-deb -f "$DEB" Version)"
PKG_ARCH="$(dpkg-deb -f "$DEB" Architecture)"
PKG_MAINTAINER="$(dpkg-deb -f "$DEB" Maintainer)"

echo "Package:      $PKG_NAME"
echo "Version:      $PKG_VERSION"
echo "Architecture: $PKG_ARCH"
echo "Maintainer:   $PKG_MAINTAINER"


if [ "$PKG_NAME" != "rustdesk" ]; then
    echo
    echo "ERROR: Unexpected package name: $PKG_NAME"
    exit 1
fi


if [ "$PKG_VERSION" != "$EXPECTED_VERSION" ]; then
    echo
    echo "ERROR: Unexpected package version."
    echo "Expected: $EXPECTED_VERSION"
    echo "Found:    $PKG_VERSION"
    exit 1
fi


if [ "$PKG_ARCH" != "amd64" ]; then
    echo
    echo "ERROR: Unexpected package architecture: $PKG_ARCH"
    exit 1
fi


if [ "$PKG_MAINTAINER" != "PL PROJECT" ]; then
    echo
    echo "ERROR: Package is not the expected PL PROJECT build."
    echo "Maintainer: $PKG_MAINTAINER"
    exit 1
fi

echo "Package verification passed."


# ------------------------------------------------------------
# 5. Remove obsolete PL PROJECT tray-hiding prototype
# ------------------------------------------------------------

echo
echo "[5/8] Cleaning previous PL PROJECT components..."

if systemctl list-unit-files 2>/dev/null |
    grep -q '^rustdesk-hide-tray\.service'; then

    sudo systemctl disable --now \
        rustdesk-hide-tray.service \
        >/dev/null 2>&1 || true
fi


sudo rm -f \
    /etc/systemd/system/rustdesk-hide-tray.service


sudo rm -f \
    /etc/systemd/system/multi-user.target.wants/rustdesk-hide-tray.service


sudo systemctl daemon-reload

echo "Cleanup complete."


# ------------------------------------------------------------
# 6. Stop existing RustDesk
# ------------------------------------------------------------

echo
echo "[6/8] Preparing installation..."


# A fresh PC will not have this service yet.
# Therefore failure here is expected and harmless.

sudo systemctl stop rustdesk.service \
    >/dev/null 2>&1 || true


# Stop old GUI/tray/server processes belonging to the current
# desktop user.
#
# This prevents an old process from remaining in memory after
# upgrading the executable.

pkill -u "$USER" -x rustdesk \
    >/dev/null 2>&1 || true


sleep 2

echo "Ready for installation."


# ------------------------------------------------------------
# 7. Install package
# ------------------------------------------------------------

echo
echo "[7/8] Installing PL PROJECT Remote Support..."


# First wait until Ubuntu's package manager is completely free.
#
# This handles unattended-upgrades, Software Updater and other
# package operations that may be running in the background.

wait_for_apt


# ------------------------------------------------------------
# First dpkg installation attempt
# ------------------------------------------------------------

DPKG_LOG="${TMP_DIR}/dpkg-install.log"


set +e

sudo dpkg -i "$DEB" 2>&1 | tee "$DPKG_LOG"

DPKG_RESULT=${PIPESTATUS[0]}

set -e


# ------------------------------------------------------------
# If dpkg failed, determine why
# ------------------------------------------------------------

if [ "$DPKG_RESULT" -ne 0 ]; then

    echo

    # --------------------------------------------------------
    # Package manager became busy between our check and dpkg.
    # This is a race condition, so wait and retry.
    # --------------------------------------------------------

    if grep -qiE \
        'lock.*another process|could not get lock|unable to acquire.*lock' \
        "$DPKG_LOG"; then

        echo "Ubuntu package manager became busy."
        echo "Waiting and retrying installation..."

        wait_for_apt

        sudo dpkg -i "$DEB"

    else

        # ----------------------------------------------------
        # Most common remaining cause is a missing dependency.
        # Example:
        #
        #   rustdesk depends on libxdo3 | libxdo4
        #
        # Let APT resolve the dependency automatically.
        # ----------------------------------------------------

        echo "Package requires additional dependencies."
        echo "Resolving dependencies automatically..."

        wait_for_apt

        sudo apt-get \
            -o DPkg::Lock::Timeout="$APT_LOCK_TIMEOUT" \
            update

        wait_for_apt

        sudo apt-get \
            -o DPkg::Lock::Timeout="$APT_LOCK_TIMEOUT" \
            install -f -y

    fi
fi


# ------------------------------------------------------------
# Complete any pending package configuration
# ------------------------------------------------------------

wait_for_apt

sudo dpkg --configure -a


# ------------------------------------------------------------
# Verify package state
# ------------------------------------------------------------

echo
echo "Verifying installed package..."


INSTALL_STATUS="$(
    dpkg-query \
        -W \
        -f='${db:Status-Status}' \
        rustdesk 2>/dev/null || true
)"


if [ "$INSTALL_STATUS" != "installed" ]; then

    echo
    echo "ERROR: RustDesk did not reach the installed state."
    echo "Package status: ${INSTALL_STATUS:-unknown}"

    exit 1
fi


INSTALLED_VERSION="$(
    dpkg-query \
        -W \
        -f='${Version}' \
        rustdesk 2>/dev/null || true
)"


if [ "$INSTALLED_VERSION" != "$EXPECTED_VERSION" ]; then

    echo
    echo "ERROR: Incorrect RustDesk version installed."
    echo "Expected: $EXPECTED_VERSION"
    echo "Found:    ${INSTALLED_VERSION:-unknown}"

    exit 1
fi


# ------------------------------------------------------------
# Verify installed files
# ------------------------------------------------------------

if [ ! -x /usr/share/rustdesk/rustdesk ]; then

    echo
    echo "ERROR: RustDesk executable is missing:"
    echo "/usr/share/rustdesk/rustdesk"

    exit 1
fi


if [ ! -e /usr/bin/rustdesk ]; then

    echo
    echo "ERROR: /usr/bin/rustdesk is missing."

    exit 1
fi


if [ ! -f /usr/lib/systemd/system/rustdesk.service ]; then

    echo
    echo "ERROR: rustdesk.service is missing."

    exit 1
fi


echo "Package installation verified."

# The robot platform owns customer consent and service startup in this mode.
if [[ "$PROVISION_ONLY" == true ]]; then
    sudo systemctl daemon-reload
    echo "PL PROJECT package provisioned; robot controller manages remote access."
    exit 0
fi


# ------------------------------------------------------------
# Enable and start RustDesk service
# ------------------------------------------------------------

echo
echo "Enabling PL PROJECT Remote Support service..."


sudo systemctl daemon-reload

sudo systemctl enable rustdesk.service

sudo systemctl restart rustdesk.service


sleep 4


# ------------------------------------------------------------
# Verify service
# ------------------------------------------------------------

if ! systemctl is-active --quiet rustdesk.service; then

    echo
    echo "ERROR: rustdesk.service failed to start."
    echo
    echo "Service status:"
    echo

    sudo systemctl status \
        rustdesk.service \
        --no-pager || true

    exit 1
fi


echo "RustDesk service is running."


# ------------------------------------------------------------
# 8. Launch fresh GUI
# ------------------------------------------------------------

echo
echo "[8/8] Starting PL PROJECT Remote Support..."


if [ -n "${DISPLAY:-}" ]; then

    nohup /usr/bin/rustdesk \
        >/dev/null 2>&1 &

    sleep 2

else

    echo "No graphical DISPLAY detected."
    echo "System service is running."
    echo "GUI was not launched automatically."

fi


# ------------------------------------------------------------
# Final verification
# ------------------------------------------------------------

echo
echo "============================================================"
echo " Installation complete"
echo "============================================================"
echo


echo "Package:"

dpkg-query \
    -W \
    -f='  ${Package} ${Version} ${Architecture} ${db:Status-Status}\n' \
    rustdesk


echo
echo "RustDesk version:"

/usr/bin/rustdesk --version || true


echo
echo "Service:"

echo -n "  enabled: "
systemctl is-enabled rustdesk.service || true

echo -n "  active:  "
systemctl is-active rustdesk.service || true


echo
echo "RustDesk ID:"

/usr/bin/rustdesk --get-id || true


echo
echo "Processes:"

ps -ef | grep '[r]ustdesk' || true


echo
echo "============================================================"
echo " PL PROJECT Remote Support ${RELEASE}"
echo " installed successfully."
echo "============================================================"
echo
