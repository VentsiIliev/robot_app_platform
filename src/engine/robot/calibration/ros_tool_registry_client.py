from __future__ import annotations

import logging
from typing import Sequence

import requests


_logger = logging.getLogger(__name__)


class RosToolRegistryClient:
    """Small REST adapter for ROS2 runtime tool registry and flange-pose endpoints."""

    def __init__(self, server_url: str = "http://localhost:5000", *, timeout_s: float = 5.0):
        self._server_url = str(server_url or "").rstrip("/")
        self._timeout_s = float(timeout_s)

    @property
    def server_url(self) -> str:
        return self._server_url

    def get_tool_registry(self) -> dict | None:
        try:
            response = requests.get(f"{self._server_url}/tool/registry", timeout=self._timeout_s)
            data = response.json()
        except Exception as exc:
            _logger.error("get_tool_registry failed: %s", exc, exc_info=True)
            return None

        if response.status_code >= 400 or data.get("success") is False:
            _logger.warning("get_tool_registry rejected: http=%s body=%s", response.status_code, data)
            return None
        return data

    def update_tool(
        self,
        tool_id: int,
        name: str | None,
        transform: Sequence[float],
        *,
        persist: bool,
    ) -> tuple[bool, str]:
        payload = {
            "name": name,
            "transform": [float(value) for value in transform],
            "persist": bool(persist),
        }
        try:
            response = requests.post(
                f"{self._server_url}/tool/registry/{int(tool_id)}",
                json=payload,
                timeout=self._timeout_s,
            )
            data = response.json()
        except Exception as exc:
            _logger.error("update_tool failed: %s", exc, exc_info=True)
            return False, str(exc)

        if response.status_code >= 400 or data.get("success") is False:
            return False, str(data.get("error") or data.get("message") or f"HTTP {response.status_code}")
        return True, "Tool registry updated"

    def get_current_flange_position(self) -> list[float] | None:
        try:
            response = requests.get(f"{self._server_url}/position/flange", timeout=self._timeout_s)
            data = response.json()
        except Exception as exc:
            _logger.error("get_current_flange_position failed: %s", exc, exc_info=True)
            return None

        position = data.get("position")
        if response.status_code >= 400 or data.get("success") is False or position is None:
            _logger.warning("get_current_flange_position rejected: http=%s body=%s", response.status_code, data)
            return None

        try:
            values = [float(value) for value in position]
        except (TypeError, ValueError):
            _logger.warning("get_current_flange_position invalid position: %s", position)
            return None
        if len(values) != 6:
            _logger.warning("get_current_flange_position expected 6 values, got %s", len(values))
            return None
        return values
