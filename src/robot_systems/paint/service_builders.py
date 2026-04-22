from __future__ import annotations

import os
from pathlib import Path


def build_vacuum_pump_service(ctx):
    from src.robot_systems.paint.domain.vacuum_pump import RelayVacuumPumpController

    relay_client_path = str(
        Path(__file__).resolve().parent / "domain" / "vacuum_pump" / "relay_client.py"
    )
    return RelayVacuumPumpController(
        relay_client_path=relay_client_path,
        host="192.168.222.35",
        port=5002,
        output_num=0,
    )
