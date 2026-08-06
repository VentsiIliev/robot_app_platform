import os

from src.engine.robot.drivers.client_adapters.fake import FakeRobotClient
from src.engine.robot.drivers.client_adapters.http_websocket import HttpWebSocketRobotClient


def should_use_fake_robot_client(server_url: str | None) -> bool:
    normalized = str(server_url or "").strip().lower()
    return normalized in {"fake", "mock", "test", "sim"} or normalized.startswith(
        ("fake://", "mock://", "test://", "sim://")
    )


def build_robot_client(server_url="http://localhost:5000", ip=None, transport=None):
    if should_use_fake_robot_client(server_url):
        return FakeRobotClient(server_url=server_url, ip=ip)

    selected_transport = str(
        transport or os.environ.get("ROBOT_CLIENT_TRANSPORT") or "http_websocket"
    ).strip().lower()
    if selected_transport in {"http_websocket", "http+websocket", "hybrid", "default"}:
        return HttpWebSocketRobotClient(server_url=server_url, ip=ip)

    raise ValueError(
        f"Unsupported robot client transport '{selected_transport}'. "
        "Available transports: http_websocket"
    )


