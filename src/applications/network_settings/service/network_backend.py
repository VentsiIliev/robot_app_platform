"""OS network adapters extracted from the standalone network manager.

No Qt dependencies belong in this module; it runs behind the shared service.
"""

import sys
import os
import re
import html
import tempfile
import subprocess
import ipaddress

def run_command(command):
    kwargs = {
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "ignore",
        "timeout": 30,
    }

    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    try:
        return subprocess.run(command, **kwargs)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Network command timed out") from None


def prefix_to_netmask(prefix):
    network = ipaddress.IPv4Network(f"0.0.0.0/{prefix}")
    return str(network.netmask)


def netmask_to_prefix(mask):
    network = ipaddress.IPv4Network(f"0.0.0.0/{mask}")
    return str(network.prefixlen)


def split_nmcli(line):
    """
    Split nmcli terse output while respecting escaped ':' characters.
    """

    result = []
    current = []
    escaped = False

    for char in line:
        if escaped:
            current.append(char)
            escaped = False

        elif char == "\\":
            escaped = True

        elif char == ":":
            result.append("".join(current))
            current = []

        else:
            current.append(char)

    result.append("".join(current))

    return result



class LinuxBackend:

    # --------------------------------------------------------
    # Wi-Fi
    # --------------------------------------------------------

    def scan_wifi(self):

        # Request scan.
        run_command([
            "nmcli",
            "device",
            "wifi",
            "rescan"
        ])

        result = run_command([
            "nmcli",
            "-t",
            "-f",
            "IN-USE,SSID,SIGNAL,SECURITY",
            "device",
            "wifi",
            "list"
        ])

        if result.returncode != 0:
            raise RuntimeError(
                result.stderr or result.stdout
            )

        networks = {}

        for line in result.stdout.splitlines():

            parts = split_nmcli(line)

            if len(parts) < 4:
                continue

            in_use = parts[0].strip()
            ssid = parts[1].strip()
            signal = parts[2].strip()
            security = parts[3].strip()

            if not ssid:
                continue

            try:
                strength = int(signal)
            except Exception:
                strength = 0

            secure = security not in ("", "--")
            connected = in_use == "*"

            existing = networks.get(ssid)

            if (
                existing is None
                or strength > existing["strength"]
            ):
                networks[ssid] = {
                    "ssid": ssid,
                    "signal": signal,
                    "strength": strength,
                    "secure": secure,
                    "connected": connected,
                }

            elif connected:
                existing["connected"] = True

        return sorted(
            networks.values(),
            key=lambda n: n["strength"],
            reverse=True
        )

    def connect_wifi(self, ssid, password=None):

        command = [
            "nmcli",
            "device",
            "wifi",
            "connect",
            ssid
        ]

        if password:
            command.extend([
                "password",
                password
            ])

        result = run_command(command)

        if result.returncode != 0:
            raise RuntimeError(
                result.stderr or result.stdout
            )

    def disconnect_wifi(self):

        devices = self.get_devices()

        for device in devices:

            if (
                device["type"] == "wifi"
                and device["state"] == "connected"
            ):
                result = run_command([
                    "nmcli",
                    "device",
                    "disconnect",
                    device["device"]
                ])

                if result.returncode != 0:
                    raise RuntimeError(
                        result.stderr or result.stdout
                    )

                return

        raise RuntimeError(
            "No connected Wi-Fi interface found."
        )

    # --------------------------------------------------------
    # Devices
    # --------------------------------------------------------

    def get_devices(self):

        result = run_command([
            "nmcli",
            "-t",
            "-f",
            "DEVICE,TYPE,STATE,CONNECTION",
            "device",
            "status"
        ])

        if result.returncode != 0:
            raise RuntimeError(
                result.stderr or result.stdout
            )

        devices = []

        for line in result.stdout.splitlines():

            parts = split_nmcli(line)

            if len(parts) < 4:
                continue

            devices.append({
                "device": parts[0],
                "type": parts[1],
                "state": parts[2],
                "connection": parts[3],
            })

        return devices

    def get_wired(self):

        devices = self.get_devices()

        return [
            d for d in devices
            if d["type"] == "ethernet"
        ]

    # --------------------------------------------------------
    # Connection settings
    # --------------------------------------------------------

    def get_connection_settings(self, connection):

        result = run_command([
            "nmcli",
            "-g",
            (
                "ipv4.method,"
                "ipv4.addresses,"
                "ipv4.gateway,"
                "ipv4.dns"
            ),
            "connection",
            "show",
            connection
        ])

        if result.returncode != 0:
            raise RuntimeError(
                result.stderr or result.stdout
            )

        lines = result.stdout.splitlines()

        while len(lines) < 4:
            lines.append("")

        method = lines[0].strip()
        address = lines[1].strip()
        gateway = lines[2].strip()
        dns = lines[3].strip()

        ip = ""
        prefix = ""

        if "/" in address:
            ip, prefix = address.split("/", 1)

        dns = dns.replace(";", ", ")

        return {
            "mode": (
                "manual"
                if method == "manual"
                else "auto"
            ),
            "ip": ip,
            "prefix": prefix,
            "gateway": gateway,
            "dns": dns,
        }

    def apply_settings(self, connection, settings):

        if settings["mode"] == "auto":

            command = [
                "nmcli",
                "connection",
                "modify",
                connection,

                "ipv4.method",
                "auto",

                "ipv4.addresses",
                "",

                "ipv4.gateway",
                "",
            ]

        else:

            address = (
                f'{settings["ip"]}/'
                f'{settings["prefix"]}'
            )

            command = [
                "nmcli",
                "connection",
                "modify",
                connection,

                "ipv4.method",
                "manual",

                "ipv4.addresses",
                address,

                "ipv4.gateway",
                settings["gateway"],
            ]

        result = run_command(command)

        if result.returncode != 0:
            raise RuntimeError(
                result.stderr or result.stdout
            )

        # DNS
        dns = settings["dns"].replace(",", " ")

        result = run_command([
            "nmcli",
            "connection",
            "modify",
            connection,
            "ipv4.dns",
            dns
        ])

        if result.returncode != 0:
            raise RuntimeError(
                result.stderr or result.stdout
            )

        # Reactivate connection.
        result = run_command([
            "nmcli",
            "connection",
            "up",
            connection
        ])

        if result.returncode != 0:
            raise RuntimeError(
                result.stderr or result.stdout
            )

    def disconnect_device(self, device):

        result = run_command([
            "nmcli",
            "device",
            "disconnect",
            device
        ])

        if result.returncode != 0:
            raise RuntimeError(
                result.stderr or result.stdout
            )

    def connect_device(self, device):

        result = run_command([
            "nmcli",
            "device",
            "connect",
            device
        ])

        if result.returncode != 0:
            raise RuntimeError(
                result.stderr or result.stdout
            )

    def forget_wifi(self, ssid):
        # Find saved Wi-Fi connections and their configured SSIDs.
        result = run_command([
            "nmcli",
            "-t",
            "-f",
            "NAME,UUID,TYPE",
            "connection",
            "show"
        ])

        if result.returncode != 0:
            raise RuntimeError(
                result.stderr or result.stdout
            )

        found = False

        for line in result.stdout.splitlines():
            parts = split_nmcli(line)

            if len(parts) < 3:
                continue

            name = parts[0]
            uuid = parts[1]
            connection_type = parts[2]

            if connection_type not in (
                    "802-11-wireless",
                    "wifi"
            ):
                continue

            # Read the actual SSID because the connection
            # profile name does not have to equal the SSID.
            info = run_command([
                "nmcli",
                "-g",
                "802-11-wireless.ssid",
                "connection",
                "show",
                uuid
            ])

            saved_ssid = info.stdout.strip()

            if saved_ssid == ssid:
                delete = run_command([
                    "nmcli",
                    "connection",
                    "delete",
                    "uuid",
                    uuid
                ])

                if delete.returncode != 0:
                    raise RuntimeError(
                        delete.stderr or delete.stdout
                    )

                found = True

        if not found:
            raise RuntimeError(
                f'No saved profile found for "{ssid}".'
            )

# ============================================================
# Windows backend
# ============================================================

class WindowsBackend:

    # --------------------------------------------------------
    # Wi-Fi
    # --------------------------------------------------------

    def scan_wifi(self):

        result = run_command([
            "netsh",
            "wlan",
            "show",
            "networks",
            "mode=bssid"
        ])

        if result.returncode != 0:
            raise RuntimeError(
                result.stderr or result.stdout
            )

        networks = []

        current = None

        for line in result.stdout.splitlines():

            match = re.match(
                r"\s*SSID\s+\d+\s*:\s*(.*)",
                line
            )

            if match:

                if current and current["ssid"]:
                    networks.append(current)

                current = {
                    "ssid": match.group(1).strip(),
                    "signal": "",
                    "strength": 0,
                    "secure": True,
                    "connected": False,
                }

                continue

            if not current:
                continue

            if "Authentication" in line:

                auth = line.split(
                    ":", 1
                )[-1].strip()

                current["secure"] = (
                    "open" not in auth.lower()
                )

            elif "Signal" in line and not current["signal"]:

                value = (
                    line.split(":", 1)[-1]
                    .replace("%", "")
                    .strip()
                )

                current["signal"] = value

                try:
                    current["strength"] = int(value)
                except Exception:
                    pass

        if current and current["ssid"]:
            networks.append(current)

        connected = self.current_wifi_ssid()

        for network in networks:
            network["connected"] = (
                network["ssid"] == connected
            )

        # Remove duplicate SSIDs.
        unique = {}

        for network in networks:

            old = unique.get(network["ssid"])

            if (
                old is None
                or network["strength"] > old["strength"]
            ):
                unique[network["ssid"]] = network

        return sorted(
            unique.values(),
            key=lambda n: n["strength"],
            reverse=True
        )

    def current_wifi_ssid(self):

        result = run_command([
            "netsh",
            "wlan",
            "show",
            "interfaces"
        ])

        match = re.search(
            r"^\s*SSID\s*:\s*(.+)$",
            result.stdout,
            re.MULTILINE
        )

        if match:
            return match.group(1).strip()

        return None

    def connect_wifi(
        self,
        ssid,
        password=None,
        secure=True
    ):

        self.create_wifi_profile(
            ssid,
            password or "",
            secure
        )

        result = run_command([
            "netsh",
            "wlan",
            "connect",
            f"name={ssid}",
            f"ssid={ssid}"
        ])

        if result.returncode != 0:
            raise RuntimeError(
                result.stderr or result.stdout
            )

    def create_wifi_profile(
        self,
        ssid,
        password,
        secure
    ):

        safe_ssid = html.escape(ssid)

        if secure:

            safe_password = html.escape(password)

            security = f"""
<security>
    <authEncryption>
        <authentication>WPA2PSK</authentication>
        <encryption>AES</encryption>
        <useOneX>false</useOneX>
    </authEncryption>

    <sharedKey>
        <keyType>passPhrase</keyType>
        <protected>false</protected>
        <keyMaterial>{safe_password}</keyMaterial>
    </sharedKey>
</security>
"""

        else:

            security = """
<security>
    <authEncryption>
        <authentication>open</authentication>
        <encryption>none</encryption>
        <useOneX>false</useOneX>
    </authEncryption>
</security>
"""

        xml = f"""<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">

    <name>{safe_ssid}</name>

    <SSIDConfig>
        <SSID>
            <name>{safe_ssid}</name>
        </SSID>
    </SSIDConfig>

    <connectionType>ESS</connectionType>
    <connectionMode>auto</connectionMode>

    <MSM>
        {security}
    </MSM>

</WLANProfile>
"""

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".xml",
            delete=False,
            encoding="utf-8"
        ) as file:

            file.write(xml)
            filename = file.name

        try:

            result = run_command([
                "netsh",
                "wlan",
                "add",
                "profile",
                f"filename={filename}",
                "user=current"
            ])

            if result.returncode != 0:
                raise RuntimeError(
                    result.stderr or result.stdout
                )

        finally:

            try:
                os.remove(filename)
            except OSError:
                pass

    def disconnect_wifi(self):

        result = run_command([
            "netsh",
            "wlan",
            "disconnect"
        ])

        if result.returncode != 0:
            raise RuntimeError(
                result.stderr or result.stdout
            )

    # --------------------------------------------------------
    # Interfaces
    # --------------------------------------------------------

    def get_interfaces(self):

        result = run_command([
            "netsh",
            "interface",
            "show",
            "interface"
        ])

        interfaces = []

        for line in result.stdout.splitlines():

            # Example:
            # Enabled Connected Dedicated Ethernet

            match = re.match(
                r"\s*(Enabled|Disabled)\s+"
                r"(Connected|Disconnected)\s+"
                r"(\S+)\s+(.+)$",
                line,
                re.IGNORECASE
            )

            if not match:
                continue

            interfaces.append({
                "admin": match.group(1),
                "state": match.group(2),
                "type": match.group(3),
                "name": match.group(4).strip(),
            })

        return interfaces

    def get_wired(self):

        interfaces = self.get_interfaces()

        wired = []

        for interface in interfaces:

            name = interface["name"]

            # Avoid showing Wi-Fi in wired tab.
            if (
                "wi-fi" in name.lower()
                or "wireless" in name.lower()
            ):
                continue

            wired.append({
                "device": name,
                "connection": name,
                "state": interface["state"].lower(),
                "type": "ethernet",
            })

        return wired

    # --------------------------------------------------------
    # IPv4 settings
    # --------------------------------------------------------

    def get_connection_settings(self, interface):

        result = run_command([
            "netsh",
            "interface",
            "ipv4",
            "show",
            "config",
            f"name={interface}"
        ])

        output = result.stdout

        dhcp = re.search(
            r"DHCP enabled:\s*Yes",
            output,
            re.IGNORECASE
        )

        ip_match = re.search(
            r"IP Address:\s*([0-9.]+)",
            output,
            re.IGNORECASE
        )

        prefix_match = re.search(
            r"Subnet Prefix:\s*[^/]+/(\d+)",
            output,
            re.IGNORECASE
        )

        gateway_match = re.search(
            r"Default Gateway:\s*([0-9.]+)",
            output,
            re.IGNORECASE
        )

        dns_servers = []

        dns_match = re.search(
            r"DNS servers configured through DHCP:\s*([0-9.]+)",
            output,
            re.IGNORECASE
        )

        if not dns_match:
            dns_match = re.search(
                r"Statically Configured DNS Servers:\s*([0-9.]+)",
                output,
                re.IGNORECASE
            )

        if dns_match:
            dns_servers.append(dns_match.group(1))

        return {
            "mode": "auto" if dhcp else "manual",
            "ip": (
                ip_match.group(1)
                if ip_match
                else ""
            ),
            "prefix": (
                prefix_match.group(1)
                if prefix_match
                else ""
            ),
            "gateway": (
                gateway_match.group(1)
                if gateway_match
                else ""
            ),
            "dns": ", ".join(dns_servers),
        }

    def apply_settings(self, interface, settings):

        if settings["mode"] == "auto":

            result = run_command([
                "netsh",
                "interface",
                "ipv4",
                "set",
                "address",
                f"name={interface}",
                "source=dhcp"
            ])

            if result.returncode != 0:
                raise RuntimeError(
                    result.stderr or result.stdout
                )

        else:

            mask = prefix_to_netmask(
                int(settings["prefix"])
            )

            command = [
                "netsh",
                "interface",
                "ipv4",
                "set",
                "address",
                f"name={interface}",
                "source=static",
                f"address={settings['ip']}",
                f"mask={mask}",
            ]

            if settings["gateway"]:
                command.append(
                    f"gateway={settings['gateway']}"
                )

            result = run_command(command)

            if result.returncode != 0:
                raise RuntimeError(
                    result.stderr or result.stdout
                )

        # DNS
        dns_servers = [
            dns.strip()
            for dns in settings["dns"].split(",")
            if dns.strip()
        ]

        if not dns_servers:

            if settings["mode"] == "auto":

                result = run_command([
                    "netsh",
                    "interface",
                    "ipv4",
                    "set",
                    "dnsservers",
                    f"name={interface}",
                    "source=dhcp"
                ])

                if result.returncode != 0:
                    raise RuntimeError(
                        result.stderr or result.stdout
                    )

        else:

            result = run_command([
                "netsh",
                "interface",
                "ipv4",
                "set",
                "dnsservers",
                f"name={interface}",
                "source=static",
                f"address={dns_servers[0]}",
                "validate=no"
            ])

            if result.returncode != 0:
                raise RuntimeError(
                    result.stderr or result.stdout
                )

            for index, dns in enumerate(
                dns_servers[1:],
                start=2
            ):

                result = run_command([
                    "netsh",
                    "interface",
                    "ipv4",
                    "add",
                    "dnsservers",
                    f"name={interface}",
                    f"address={dns}",
                    f"index={index}",
                    "validate=no"
                ])

                if result.returncode != 0:
                    raise RuntimeError(
                        result.stderr or result.stdout
                    )

    def disconnect_device(self, interface):

        result = run_command([
            "netsh",
            "interface",
            "set",
            "interface",
            f"name={interface}",
            "admin=disabled"
        ])

        if result.returncode != 0:
            raise RuntimeError(
                result.stderr or result.stdout
            )

    def connect_device(self, interface):

        result = run_command([
            "netsh",
            "interface",
            "set",
            "interface",
            f"name={interface}",
            "admin=enabled"
        ])

        if result.returncode != 0:
            raise RuntimeError(
                result.stderr or result.stdout
            )

    def forget_wifi(self, ssid):
        result = run_command([
            "netsh",
            "wlan",
            "delete",
            "profile",
            f"name={ssid}"
        ])

        if result.returncode != 0:
            raise RuntimeError(
                result.stderr or result.stdout
            )

# ============================================================
# Main UI
# ============================================================
