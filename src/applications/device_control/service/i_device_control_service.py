from abc import ABC, abstractmethod


class IDeviceControlService(ABC):

    @abstractmethod
    def laser_on(self) -> None: ...

    @abstractmethod
    def laser_off(self) -> None: ...

    @abstractmethod
    def vacuum_pump_on(self) -> bool: ...

    @abstractmethod
    def vacuum_pump_off(self) -> bool: ...

    @abstractmethod
    def motor_on(self) -> bool: ...

    @abstractmethod
    def motor_off(self) -> bool: ...

    @abstractmethod
    def generator_on(self) -> bool: ...

    @abstractmethod
    def generator_off(self) -> bool: ...

    @abstractmethod
    def is_laser_available(self) -> bool: ...

    @abstractmethod
    def is_vacuum_pump_available(self) -> bool: ...

    @abstractmethod
    def is_motor_available(self) -> bool: ...

    @abstractmethod
    def is_generator_available(self) -> bool: ...

