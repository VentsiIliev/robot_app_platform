from dataclasses import dataclass


@dataclass
class GeneratorConfig:
    relay_register:  int   = 9
    state_register:  int   = 10
    timeout_minutes: float = 5.0