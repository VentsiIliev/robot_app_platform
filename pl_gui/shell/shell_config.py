"""
Shell configuration module.

Provides centralized folder structure definition and dynamic management API.
"""
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class FolderDefinition:
    """Definition of a folder in the shell launcher."""
    id: int
    name: str
    translation_key: str
    display_name: str  # Default English name

    def get_translate_fn(self) -> Callable[[str], str]:
        """Return a translate function for this folder."""
        # For now, returns the display name
        # In future, this can integrate with real translation system
        return lambda key: self.display_name


class ShellConfig:
    """
    Configuration for the App Shell launcher.

    Provides both static configuration and dynamic management API.
    """

    # Internal storage - use public API to modify
    _folders: list[FolderDefinition] = []
    _initialized: bool = False

    @classmethod
    def initialize_defaults(cls):
        """Initialize with default folder structure."""
        if not cls._initialized:
            cls._folders = [
                FolderDefinition(
                    id=1,
                    name="WORK",
                    translation_key="folder.work",
                    display_name="WORK"
                ),
                FolderDefinition(
                    id=2,
                    name="SERVICE",
                    translation_key="folder.service",
                    display_name="SERVICE"
                ),
                FolderDefinition(
                    id=3,
                    name="ADMINISTRATION",
                    translation_key="folder.administration",
                    display_name="ADMINISTRATION"
                ),
            ]
            cls._initialized = True

    # ============================================================
    # PUBLIC API - Folder Management
    # ============================================================

    @classmethod
    def add_folder(cls, folder: FolderDefinition, override_defaults: bool = False) -> None:
        """
        Add a new folder definition.

        Args:
            folder: FolderDefinition to add
            override_defaults: If True, don't initialize defaults (for custom-only config).
                             If False (default), initialize defaults first (add to defaults).

        Raises:
            ValueError: If folder ID already exists

        Example:
            >>> # Add to defaults
            >>> new_folder = FolderDefinition(id=4, name="MAINTENANCE", ...)
            >>> ShellConfig.add_folder(new_folder)

            >>> # Override defaults (custom-only)
            >>> ShellConfig.add_folder(custom_folder, override_defaults=True)
        """
        if not override_defaults:
            cls.initialize_defaults()

        # If override_defaults=True and not initialized, mark as initialized to prevent auto-init
        if override_defaults and not cls._initialized:
            cls._initialized = True

        if cls.folder_exists(folder.id):
            raise ValueError(f"Folder with ID {folder.id} already exists")

        cls._folders.append(folder)
        print(f"[ShellConfig] Added folder: {folder.name} (ID: {folder.id})")

    @classmethod
    def remove_folder(cls, folder_id: int) -> bool:
        """
        Remove a folder definition by ID.

        Args:
            folder_id: ID of folder to remove

        Returns:
            True if folder was removed, False if not found

        Example:
            >>> ShellConfig.remove_folder(4)
            True
        """
        cls.initialize_defaults()

        for i, folder in enumerate(cls._folders):
            if folder.id == folder_id:
                removed = cls._folders.pop(i)
                print(f"[ShellConfig] Removed folder: {removed.name} (ID: {folder_id})")
                return True
        return False

    @classmethod
    def update_folder(cls, folder_id: int, **updates) -> bool:
        """
        Update an existing folder definition.

        Args:
            folder_id: ID of folder to update
            **updates: Fields to update (name, translation_key, display_name)

        Returns:
            True if folder was updated, False if not found

        Example:
            >>> ShellConfig.update_folder(1, display_name="WORK AREA")
            True
        """
        cls.initialize_defaults()

        for folder in cls._folders:
            if folder.id == folder_id:
                for key, value in updates.items():
                    if hasattr(folder, key):
                        setattr(folder, key, value)
                print(f"[ShellConfig] Updated folder ID {folder_id}: {updates}")
                return True
        return False

    @classmethod
    def clear_folders(cls) -> None:
        """
        Clear all folder definitions.

        After calling this, use add_folder(folder, override_defaults=True)
        to build a custom-only configuration.

        Warning: Use with caution. Usually followed by add_folder() calls.

        Example:
            >>> ShellConfig.clear_folders()
            >>> # Add custom folders without defaults
            >>> ShellConfig.add_folder(custom_folder, override_defaults=True)
        """
        cls._folders.clear()
        cls._initialized = True  # Prevent auto-initialization of defaults
        print("[ShellConfig] Cleared all folder definitions")

    @classmethod
    def reset_to_defaults(cls) -> None:
        """
        Reset to default folder configuration.

        Example:
            >>> ShellConfig.reset_to_defaults()
        """
        cls._folders.clear()
        cls._initialized = False
        cls.initialize_defaults()
        print("[ShellConfig] Reset to default folder configuration")

    # ============================================================
    # PUBLIC API - Folder Queries
    # ============================================================

    @classmethod
    def get_folders(cls) -> list[FolderDefinition]:
        """
        Get all folder definitions.

        Returns:
            List of all FolderDefinition objects

        Example:
            >>> folders = ShellConfig.get_folders()
            >>> for folder in folders:
            ...     print(f"{folder.id}: {folder.name}")
        """
        cls.initialize_defaults()
        return cls._folders.copy()

    @classmethod
    def get_folder_by_id(cls, folder_id: int) -> Optional[FolderDefinition]:
        """
        Get folder definition by ID.

        Args:
            folder_id: Folder ID to find

        Returns:
            FolderDefinition if found, None otherwise

        Example:
            >>> folder = ShellConfig.get_folder_by_id(1)
            >>> if folder:
            ...     print(folder.name)
        """
        cls.initialize_defaults()

        for folder in cls._folders:
            if folder.id == folder_id:
                return folder
        return None

    @classmethod
    def get_all_folder_ids(cls) -> list[int]:
        """
        Get all defined folder IDs.

        Returns:
            List of folder IDs

        Example:
            >>> ids = ShellConfig.get_all_folder_ids()
            >>> print(ids)  # [1, 2, 3]
        """
        cls.initialize_defaults()
        return [f.id for f in cls._folders]

    @classmethod
    def folder_exists(cls, folder_id: int) -> bool:
        """
        Check if folder ID exists in configuration.

        Args:
            folder_id: Folder ID to check

        Returns:
            True if folder exists, False otherwise

        Example:
            >>> if ShellConfig.folder_exists(4):
            ...     print("Folder 4 exists")
        """
        cls.initialize_defaults()
        return folder_id in cls.get_all_folder_ids()

    @classmethod
    def get_folders_with_apps(cls, filtered_apps: dict[int, list]) -> list[FolderDefinition]:
        """
        Get only folders that have apps assigned.

        Args:
            filtered_apps: Dictionary mapping folder_id to list of apps

        Returns:
            List of FolderDefinition objects that have apps

        Example:
            >>> app_map = {1: [app1, app2], 2: [app3]}
            >>> folders = ShellConfig.get_folders_with_apps(app_map)
        """
        cls.initialize_defaults()
        return [f for f in cls._folders if f.id in filtered_apps and filtered_apps[f.id]]


# Convenience constants for folder IDs
FOLDER_WORK = 1
FOLDER_SERVICE = 2
FOLDER_ADMINISTRATION = 3


# ============================================================
# Helper Functions for Common Operations
# ============================================================

def create_custom_folder(
    folder_id: int,
    name: str,
    display_name: Optional[str] = None,
    translation_key: Optional[str] = None
) -> FolderDefinition:
    """
    Helper to create a custom folder definition.

    Args:
        folder_id: Unique folder ID
        name: Internal folder name (uppercase recommended)
        display_name: Display name (defaults to name)
        translation_key: Translation key (defaults to folder.{name.lower()})

    Returns:
        FolderDefinition ready to add via ShellConfig.add_folder()

    Example:
        >>> folder = create_custom_folder(4, "MAINTENANCE", "Maintenance")
        >>> ShellConfig.add_folder(folder)
    """
    return FolderDefinition(
        id=folder_id,
        name=name,
        translation_key=translation_key or f"folder.{name.lower()}",
        display_name=display_name or name
    )
