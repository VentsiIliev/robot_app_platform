
"""
motor_cli.y_pixels — interactive terminal runner for MotorService.

Usage:
    python src/engine/hardware/motor/motor_cli.y_pixels --port COM5 --slave 10
    python src/engine/hardware/motor/motor_cli.y_pixels --port /dev/ttyUSB0 --slave 10 --motors 0 2 4 6

Commands (once the REPL starts):
    open                          open persistent connection
    close                         close persistent connection
    status                        show connection state
    list                          list configured motor addresses
    on  <addr> [speed]            turn motor on  (default speed 10000)
    off <addr>                    turn motor off
    speed <addr> <speed>          set speed without full start/stop
    health <addr>                 health check single motor
    health_all                    health check all configured motors
    help                          show this list
    quit / exit / q               exit
"""

from __future__ import annotations

import argparse
import sys
import os

# ── make sure project root is on sys.path ─────────────────────────────────────
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.engine.hardware.communication.modbus.modbus import ModbusConfig
from src.engine.hardware.motor.models.motor_config import MotorConfig
from src.engine.hardware.motor.modbus.modbus_motor_factory import build_modbus_motor_service

# ── defaults ──────────────────────────────────────────────────────────────────
_DEFAULT_SPEED      = 10000
_RAMP_STEPS         = 1
_INITIAL_RAMP_SPEED = 5000
_INITIAL_RAMP_DUR   = 1.0
_REVERSE_SPEED      = 1000
_REVERSE_DUR        = 1.0
_REVERSE_RAMP_STEPS = 1

_HELP = """
Commands:
  open                     open persistent connection
  close                    close persistent connection
  status                   show connection state
  list                     list configured motor addresses
  on  <addr> [speed]       turn on  (default speed {speed})
  off <addr>               turn off
  speed <addr> <speed>     set speed live
  health <addr>            single motor health check
  health_all               all motors health check
  help                     this message
  quit / exit / q          quit
""".format(speed=_DEFAULT_SPEED)


def _build_service(args):
    modbus_cfg = ModbusConfig(
        port          = args.port,
        slave_address = args.slave,
        baudrate      = args.baudrate,
        bytesize      = args.bytesize,
        stopbits      = args.stopbits,
        parity        = args.parity,
        timeout       = args.timeout,
    )
    error_prefixes = dict(zip(args.motors, range(1, len(args.motors) + 1)))
    motor_cfg = MotorConfig(
        health_check_trigger_register = args.hc_trigger,
        motor_error_count_register    = args.hc_count,
        motor_error_registers_start   = args.hc_errors_start,
        motor_addresses               = args.motors,
        address_to_error_prefix       = error_prefixes,
        health_check_delay_s          = args.hc_delay,
    )
    return build_modbus_motor_service(modbus_cfg, motor_cfg)


def _run_repl(svc):
    print(_HELP)
    while True:
        try:
            raw = input("motor> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not raw:
            continue

        parts = raw.split()
        cmd   = parts[0].lower()

        if cmd in ("quit", "exit", "q"):
            break

        elif cmd == "help":
            print(_HELP)

        elif cmd == "open":
            svc.open()
            print(f"  connected: {svc.is_healthy()}")

        elif cmd == "close":
            svc.close()
            print(f"  connected: {svc.is_healthy()}")

        elif cmd == "status":
            print(f"  connected: {svc.is_healthy()}")
            print(f"  addresses: {svc.motor_addresses}")

        elif cmd == "list":
            for addr in svc.motor_addresses:
                print(f"  address {addr}")

        elif cmd == "on":
            if len(parts) < 2:
                print("  usage: on <addr> [speed]")
                continue
            addr  = int(parts[1])
            speed = int(parts[2]) if len(parts) > 2 else _DEFAULT_SPEED
            ok = svc.turn_on(
                motor_address               = addr,
                speed                       = speed,
                ramp_steps                  = _RAMP_STEPS,
                initial_ramp_speed          = _INITIAL_RAMP_SPEED,
                initial_ramp_speed_duration = _INITIAL_RAMP_DUR,
            )
            print(f"  turn_on addr={addr} speed={speed} → {'OK' if ok else 'FAILED'}")

        elif cmd == "off":
            if len(parts) < 2:
                print("  usage: off <addr>")
                continue
            addr = int(parts[1])
            ok = svc.turn_off(
                motor_address    = addr,
                speed_reverse    = _REVERSE_SPEED,
                reverse_duration = _REVERSE_DUR,
                ramp_steps       = _REVERSE_RAMP_STEPS,
            )
            print(f"  turn_off addr={addr} → {'OK' if ok else 'FAILED'}")

        elif cmd == "speed":
            if len(parts) < 3:
                print("  usage: speed <addr> <speed>")
                continue
            addr, speed = int(parts[1]), int(parts[2])
            ok = svc.set_speed(addr, speed)
            print(f"  set_speed addr={addr} speed={speed} → {'OK' if ok else 'FAILED'}")

        elif cmd == "health":
            if len(parts) < 2:
                print("  usage: health <addr>")
                continue
            addr  = int(parts[1])
            state = svc.health_check(addr)
            print(f"  {state}")

        elif cmd == "health_all":
            snap = svc.health_check_all_configured()
            for addr, state in snap.motors.items():
                print(f"  {state}")
            if not snap.motors:
                print("  (no motors configured)")

        else:
            print(f"  unknown command '{cmd}' — type 'help'")

    svc.close()
    print("bye.")


def main():
    p = argparse.ArgumentParser(description="Interactive MotorService CLI")

    # ── connection ────────────────────────────────────────────────────
    p.add_argument("--port",     default="/dev/ttyUSB0",  help="Serial port (default: COM5)")
    p.add_argument("--slave",    type=int, default=1, help="Modbus slave address (default: 10)")
    p.add_argument("--baudrate", type=int, default=115200)
    p.add_argument("--bytesize", type=int, default=8)
    p.add_argument("--stopbits", type=int, default=1)
    p.add_argument("--parity",   default="N")
    p.add_argument("--timeout",  type=float, default=0.03)

    # ── motor topology ────────────────────────────────────────────────
    p.add_argument("--motors", type=int, nargs="+", default=[0, 2, 4, 6],
                   help="Motor addresses (default: 0 2 4 6)")

    # ── health check registers ────────────────────────────────────────
    p.add_argument("--hc-trigger",      type=int,   default=17,  dest="hc_trigger")
    p.add_argument("--hc-count",        type=int,   default=20,  dest="hc_count")
    p.add_argument("--hc-errors-start", type=int,   default=21,  dest="hc_errors_start")
    p.add_argument("--hc-delay",        type=float, default=3.0, dest="hc_delay",
                   help="Seconds to wait after health check trigger (default: 3.0)")

    # ── auto-connect ──────────────────────────────────────────────────
    p.add_argument("--connect", action="store_true",
                   help="Open connection immediately on start")

    args = p.parse_args()

    svc = _build_service(args)

    print(f"Motor CLI  port={args.port}  slave={args.slave}  motors={args.motors}")

    if args.connect:
        svc.open()
        print(f"Connected: {svc.is_healthy()}")

    _run_repl(svc)


if __name__ == "__main__":
    main()

