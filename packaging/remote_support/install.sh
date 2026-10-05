#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 && $# -ne 3 ]]; then
    echo "Usage: sudo $0 ROBOT_UI_USER [--vendor-installer PATH]" >&2
    exit 2
fi
vendor_installer=""
if [[ $# -eq 3 ]]; then
    if [[ $2 != --vendor-installer || ! -f $3 ]]; then
        echo "Provide --vendor-installer followed by a trusted installer file" >&2
        exit 2
    fi
    vendor_installer=$(realpath -- "$3")
fi
if [[ ${EUID} -ne 0 ]]; then
    echo "Run this installer as root" >&2
    exit 2
fi

ui_user=$1
if [[ ! $ui_user =~ ^[a-z_][a-z0-9_-]*$ ]] || [[ $ui_user == root ]] || ! id -u "$ui_user" >/dev/null 2>&1; then
    echo "ROBOT_UI_USER must be an existing local user" >&2
    exit 2
fi
if [[ -z "$vendor_installer" && $(systemctl show --property=LoadState --value rustdesk.service) != loaded ]]; then
    echo "Install the system rustdesk.service unit first" >&2
    exit 1
fi

source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_dir=$(cd -- "$source_dir/../.." && pwd)
state_dir=/var/lib/plproject/remote-support
controller_source="$source_dir/controller.py"
if [[ ! -f "$controller_source" ]]; then
    controller_source="$repo_dir/src/engine/remote_support/controller.py"
fi
if [[ ! -f "$controller_source" ]]; then
    echo "Remote support controller payload is missing" >&2
    exit 1
fi
command -v python3 >/dev/null

install -d -o root -g root -m 0755 /var/lib/plproject
install -d -o root -g root -m 0700 "$state_dir"
if [[ -f "$state_dir/enabled" ]]; then
    chown root:root "$state_dir/enabled"
    chmod 0600 "$state_dir/enabled"
fi

install -d -o root -g root -m 0755 /usr/local/libexec
install -o root -g root -m 0755 \
    "$controller_source" \
    /usr/local/libexec/plproject-remote-support
install -o root -g root -m 0644 \
    "$source_dir/plproject-remote-support.service" \
    /etc/systemd/system/plproject-remote-support.service
socket_temp=$(mktemp)
trap 'rm -f "$socket_temp"' EXIT
sed "s/@UI_USER@/$ui_user/g" "$source_dir/plproject-remote-support.socket.in" > "$socket_temp"
install -o root -g root -m 0644 "$socket_temp" \
    /etc/systemd/system/plproject-remote-support.socket
install -d -o root -g root -m 0755 /etc/systemd/system/rustdesk.service.d
install -o root -g root -m 0644 \
    "$source_dir/rustdesk.service.d/plproject-remote-support.conf" \
    /etc/systemd/system/rustdesk.service.d/plproject-remote-support.conf

systemctl daemon-reload
if [[ -n "$vendor_installer" ]]; then
    # Gate package post-install startup before provisioning the branded build.
    # The vendor installer must support --provision-only.
    USER="$ui_user" bash "$vendor_installer" --provision-only
    systemctl daemon-reload
    if [[ $(systemctl show --property=LoadState --value rustdesk.service) != loaded ]]; then
        echo "Vendor installer did not install rustdesk.service" >&2
        exit 1
    fi
fi
if [[ ! -f "$state_dir/enabled" ]]; then
    # First installation defaults to OFF; the condition now blocks restarts.
    systemctl stop rustdesk.service
else
    systemctl enable --now rustdesk.service
fi
systemctl stop plproject-remote-support.service 2>/dev/null || true
systemctl enable plproject-remote-support.socket
systemctl restart plproject-remote-support.socket
echo "Remote support controller installed for $ui_user"
echo "Current desired state: $(test -f "$state_dir/enabled" && echo ON || echo OFF)"
