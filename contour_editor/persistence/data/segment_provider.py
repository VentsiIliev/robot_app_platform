"""
Segment Manager Provider

Singleton provider for segment manager implementation.
Allows applications to inject their own segment manager implementations.
"""

from typing import Type, Optional
from ...models.interfaces import ISegmentManager


class SegmentManagerProvider:
    """
    Singleton provider for segment manager implementation.

    This allows applications to inject custom segment manager implementations
    while providing a sensible default (BezierSegmentManagerAdapter).

    Usage:
        # In application initialization:
        provider = SegmentManagerProvider.get_instance()
        provider.set_manager_class(MyCustomSegmentManager)

        # In ContourEditor:
        manager = SegmentManagerProvider.get_instance().create_manager()
    """

    _instance = None
    _manager_class: Optional[Type[ISegmentManager]] = None

    @classmethod
    def get_instance(cls):
        """Get singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def set_manager_class(self, manager_class: Type[ISegmentManager]):
        """
        Set the segment manager class to use.

        Args:
            manager_class: Class implementing ISegmentManager interface
        """
        self._manager_class = manager_class
        print(f"[SegmentManagerProvider] Using custom manager: {manager_class.__name__}")

    def create_manager(self) -> ISegmentManager:
        """
        Create a new segment manager instance.

        Returns:
            Instance of configured segment manager class.

        Raises:
            RuntimeError: If no manager class has been registered.
        """
        if self._manager_class:
            return self._manager_class()

        # No default - plugin MUST register a manager
        raise RuntimeError(
            "No segment manager registered! "
            "Plugin must call SegmentManagerProvider.get_instance().set_manager_class(ManagerClass) "
            "before creating ContourEditor."
        )

    def reset(self):
        """Reset to default (useful for testing)"""
        self._manager_class = None

