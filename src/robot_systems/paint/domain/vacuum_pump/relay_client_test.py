import time

from relay_client import run_command, control_relay

print(run_command("status"))
print(control_relay(0, "on"))
print(run_command("status"))
time.sleep(1)
print(control_relay(0, "off"))
print(run_command("status"))
