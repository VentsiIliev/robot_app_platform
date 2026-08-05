from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Callable

from src.applications.ethercat_diagnostics.service.i_ethercat_diagnostics_service import (
    EthercatDiagnosticsSnapshot,
    EthercatSlaveStatus,
    IEthercatDiagnosticsService,
)


@dataclass(frozen=True)
class _CommandResult:
    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


class IghEthercatDiagnosticsService(IEthercatDiagnosticsService):
    """EtherCAT diagnostics provider using the IgH `ethercat` command-line tool."""

    _SLAVE_LINE = re.compile(
        r"^\s*(?P<ring>\d+)\s+"
        r"(?P<alias>\d+):(?P<rel>\d+)\s+"
        r"(?P<state>\S+)\s+"
        r"(?P<flag>[+E])\s+"
        r"(?P<name>.*)$"
    )

    def __init__(
        self,
        *,
        executable: str = "ethercat",
        master: str | None = None,
        timeout_s: float = 2.0,
        runner: Callable[..., subprocess.CompletedProcess] | None = None,
    ) -> None:
        self._executable = executable
        self._master = str(master).strip() if master is not None else ""
        self._timeout_s = float(timeout_s)
        self._runner = runner or subprocess.run

    def refresh(self) -> EthercatDiagnosticsSnapshot:
        if shutil.which(self._executable) is None:
            return EthercatDiagnosticsSnapshot(
                master_state="unavailable",
                master_message=f"EtherCAT command not found: {self._executable}",
                raw={"success": False, "error": "command_not_found", "executable": self._executable},
            )

        master = self._run("master")
        slaves = self._run("slaves")
        crc = self._run("crc")

        raw = {
            "provider": "igh_cli",
            "commands": {
                "master": self._command_raw(master),
                "slaves": self._command_raw(slaves),
                "crc": self._command_raw(crc),
            },
        }

        if master.returncode != 0 and slaves.returncode != 0:
            message = self._first_error(master, slaves) or "IgH EtherCAT diagnostics failed"
            return EthercatDiagnosticsSnapshot(master_state="error", master_message=message, raw=raw)

        slave_rows = self.parse_slaves(slaves.stdout)
        crc_summary = self.parse_crc(crc.stdout)
        master_state = self._master_state(master, slaves, slave_rows)
        message = self._master_message(master_state, slave_rows, crc_summary, master, slaves)
        raw["crc_summary"] = crc_summary
        return EthercatDiagnosticsSnapshot(
            master_state=master_state,
            master_message=message,
            slaves=tuple(slave_rows),
            raw=raw,
        )

    def supports_reset_errors(self) -> bool:
        return shutil.which(self._executable) is not None

    def reset_errors(self) -> tuple[bool, str]:
        result = self._run("crc", "reset")
        if result.returncode == 0:
            return True, "EtherCAT CRC/error counters reset"
        return False, result.stderr.strip() or result.stdout.strip() or "Failed to reset EtherCAT errors"

    def _run(self, *args: str) -> _CommandResult:
        command = [self._executable]
        if self._master:
            command.extend(["--master", self._master])
        command.extend(args)
        try:
            completed = self._runner(
                command,
                capture_output=True,
                text=True,
                timeout=self._timeout_s,
                check=False,
            )
            return _CommandResult(
                args=tuple(command),
                returncode=int(completed.returncode),
                stdout=str(completed.stdout or ""),
                stderr=str(completed.stderr or ""),
            )
        except Exception as exc:
            return _CommandResult(tuple(command), 1, "", str(exc))

    @classmethod
    def parse_slaves(cls, output: str) -> list[EthercatSlaveStatus]:
        slaves = []
        for line in str(output or "").splitlines():
            match = cls._SLAVE_LINE.match(line)
            if match is None:
                continue
            state = match.group("state")
            flag = match.group("flag")
            error = "" if flag == "+" else "Slave scan or configuration failed"
            ring_position = int(match.group("ring"))
            slaves.append(
                EthercatSlaveStatus(
                    slave_id=ring_position,
                    name=match.group("name").strip(),
                    state=state,
                    online=True,
                    operational=state.upper() == "OP" and flag == "+",
                    error=error,
                    details={
                        "ring_position": ring_position,
                        "alias": int(match.group("alias")),
                        "relative_position": int(match.group("rel")),
                        "error_flag": flag,
                    },
                )
            )
        return slaves

    @staticmethod
    def parse_crc(output: str) -> dict:
        summary = {"raw": str(output or ""), "has_errors": False}
        for token in re.findall(r"\b\d+\b", str(output or "")):
            if int(token) > 0:
                summary["has_errors"] = True
                break
        return summary

    @staticmethod
    def _master_state(master: _CommandResult, slaves: _CommandResult, slave_rows: list[EthercatSlaveStatus]) -> str:
        if master.returncode != 0 or slaves.returncode != 0:
            return "error"
        if not slave_rows:
            return "no_slaves"
        if all(slave.operational is True for slave in slave_rows):
            return "operational"
        return "not_ready"

    @staticmethod
    def _master_message(
        master_state: str,
        slaves: list[EthercatSlaveStatus],
        crc_summary: dict,
        master: _CommandResult,
        slave_result: _CommandResult,
    ) -> str:
        if master_state == "error":
            return IghEthercatDiagnosticsService._first_error(master, slave_result) or "IgH EtherCAT diagnostics failed"
        if master_state == "no_slaves":
            return "No EtherCAT slaves detected"
        if crc_summary.get("has_errors"):
            return "EtherCAT CRC/error counters report errors"
        if master_state == "operational":
            return "All EtherCAT slaves are OP"
        not_ready = sum(1 for slave in slaves if slave.operational is not True)
        return f"{not_ready} EtherCAT slave(s) are not OP"

    @staticmethod
    def _first_error(*results: _CommandResult) -> str:
        for result in results:
            message = result.stderr.strip() or result.stdout.strip()
            if result.returncode != 0 and message:
                return message
        return ""

    @staticmethod
    def _command_raw(result: _CommandResult) -> dict:
        return {
            "args": list(result.args),
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
