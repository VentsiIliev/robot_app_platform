from __future__ import annotations
import logging
from enum import Enum
from typing import Callable, Dict

from src.engine.core.i_health_checkable import IHealthCheckable

_logger = logging.getLogger("ServiceHealthRegistry")


class ServiceHealthRegistry:
    """
    Maps service names to health check callables.

    Resolution order when check(name) is called:
      1. Explicitly registered callable  → called directly
      2. Service implements IHealthCheckable → is_healthy() called
      3. No check registered, service not health-checkable → False

    Usage:
        registry = ServiceHealthRegistry()
        registry.register("robot",  lambda: robot_svc.is_healthy())
        registry.register("weight", lambda: weight_svc.is_healthy())

        # later passed as service_checker to BaseProcess:
        GlueProcess(service_checker=registry.check, ...)
    """

    def __init__(self) -> None:
        self._checks: Dict[Enum, Callable[[], bool]] = {}

    def register(self, service_name: Enum, check: Callable[[], bool]) -> ServiceHealthRegistry:
        self._checks[service_name] = check
        return self

    def register_service(self, service_name: Enum, service: object) -> ServiceHealthRegistry:
        """Auto-register a service — uses is_healthy() if IHealthCheckable, else always True."""
        if isinstance(service, IHealthCheckable):
            self._checks[service_name] = service.is_healthy
        else:
            self._checks[service_name] = lambda: True
        return self

    def check(self, service_name: Enum) -> bool:
        fn = self._checks.get(service_name)
        if fn is None:
            _logger.debug("No health check registered for '%s' — treating as unhealthy", service_name)
            return False
        try:
            result = fn()
            if not result:
                _logger.debug("Health check failed for '%s'", service_name)
            return result
        except Exception:
            _logger.exception("Health check raised for '%s'", service_name)
            return False