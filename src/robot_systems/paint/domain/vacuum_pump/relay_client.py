import requests
import json


class RelayClient:
    """
    Client for the Relay Control Server.
    """
    def __init__(self, host="127.0.0.1", port=5002):
        self.base_url = f"http://{host}:{port}"

    def turn_on_y0(self):
        """Turn ON relay Y0"""
        return self._send_request("/relay/y0/on")

    def turn_off_y0(self):
        """Turn OFF relay Y0"""
        return self._send_request("/relay/y0/off")

    def get_y0_status(self):
        """Get the current status of relay Y0"""
        return self._send_request("/relay/y0/status")

    def get_all_status(self):
        """Get status of all inputs and outputs"""
        return self._send_request("/relay/status")

    def set_relay(self, output_num, state):
        """
        Set a specific relay state.

        Args:
            output_num (int): Relay index (0-7)
            state (bool or str): True/'on' or False/'off'
        """
        state_str = "on" if state in [True, "on", "ON", 1, "1"] else "off"
        return self._send_request(f"/relay/{output_num}/{state_str}")

    def _send_request(self, endpoint):
        try:
            response = requests.get(f"{self.base_url}{endpoint}", timeout=2)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}


def run_command(command, host="192.168.222.35", port=5002):
    """
    Run a simple relay command programmatically.

    Args:
        command (str): one of 'on', 'off', 'status', 'all'
        host (str): Relay server host
        port (int): Relay server port

    Returns:
        dict: JSON response from server or error dict
    """
    client = RelayClient(host=host, port=port)
    command = command.lower()

    if command == "on":
        return client.turn_on_y0()
    elif command == "off":
        return client.turn_off_y0()
    elif command == "status":
        return client.get_y0_status()
    elif command == "all":
        return client.get_all_status()
    else:
        return {"success": False, "error": f"Unknown command: {command}"}


def control_relay(output_num, state, host="192.168.222.35", port=5002):
    """
    Control any relay output programmatically.

    Args:
        output_num (int): Relay index (0-7)
        state (bool or str): True/'on' or False/'off'
        host (str): Relay server host
        port (int): Relay server port

    Returns:
        dict: JSON response from server or error dict
    """
    client = RelayClient(host=host, port=port)
    return client.set_relay(output_num, state)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 relay_client.py [on|off|status|all]")
        print("  python3 relay_client.py set <output_num> <on|off>")
        sys.exit(1)

    cmd = sys.argv[1].lower()

    if cmd in ["on", "off", "status", "all"]:
        result = run_command(cmd)

    elif cmd == "set":
        if len(sys.argv) < 4:
            print("Usage: python3 relay_client.py set <output_num> <on|off>")
            sys.exit(1)

        try:
            output_num = int(sys.argv[2])
        except ValueError:
            print("Error: output_num must be an integer")
            sys.exit(1)

        state = sys.argv[3].lower()
        if state not in ["on", "off"]:
            print("Error: state must be 'on' or 'off'")
            sys.exit(1)

        result = control_relay(output_num, state)

    else:
        result = {"success": False, "error": f"Unknown command: {cmd}"}

    print(json.dumps(result, indent=2))