from pathlib import Path
from modules.shared.tools.GlueCell import GlueCell, GlueMeter
from modules.shared.tools.glue_monitor_system.config.loader import log_if_enabled, load_config
from modules.utils import PathResolver
from modules.utils.custom_logging import LoggingLevel


class GlueCellsManagerSingleton:
    _manager_instance = None

    # Use application-specific storage for glue cell config
    @classmethod
    def _get_config_path(cls):
        """Get the path to glue cell config using application-specific storage."""
        try:
            from core.application.ApplicationStorageResolver import get_app_settings_path
            return Path(get_app_settings_path("glue_dispensing_application", "glue_cell_config"))
        except ImportError:
            # Fallback to old path for backward compatibility
            return Path(PathResolver.get_settings_file_path('glue_cell_config.json'))

    CONFIG_PATH = None  # Will be set in get_instance()

    @staticmethod
    def get_instance():
        if GlueCellsManagerSingleton._manager_instance is None:
            # Set CONFIG_PATH if not already set
            if GlueCellsManagerSingleton.CONFIG_PATH is None:
                GlueCellsManagerSingleton.CONFIG_PATH = GlueCellsManagerSingleton._get_config_path()

            # Load and validate config
            config = load_config(GlueCellsManagerSingleton.CONFIG_PATH)
            
            print(f"[GlueCellsManager] Running in {config.environment.upper()} mode - using server: {config.server.base_url}")

            cells = []
            for cell_cfg in config.cells:
                glue_type = cell_cfg.type  # Use the enum directly
                
                # Override URL based on mode
                if config.is_test_mode:
                    url = f"{config.server.base_url}/weight{cell_cfg.id}"
                else:
                    url = cell_cfg.url

                print(f"[GlueCellsManager] Cell {cell_cfg.id}: {url}")

                # Create GlueMeter with all required parameters
                glue_meter = GlueMeter(
                    id=cell_cfg.id,
                    url=url,
                    name=f"GlueMeter_{cell_cfg.id}",
                    state="initializing"
                )

                # Get motor address from config (default to 0 if not present)
                motor_address = getattr(cell_cfg, 'motor_address', 0)

                glue_cell = GlueCell(
                    id=cell_cfg.id,
                    glueType=glue_type,
                    glueMeter=glue_meter,
                    capacity=cell_cfg.capacity,
                    motor_address=motor_address
                )
                cells.append(glue_cell)

            # Pass config and CONFIG_PATH into manager
            GlueCellsManagerSingleton._manager_instance = GlueCellsManager(
                cells, config, GlueCellsManagerSingleton.CONFIG_PATH
            )

        return GlueCellsManagerSingleton._manager_instance


class GlueCellsManager:
    """
    Manages multiple glue cells in the dispensing application.

    Attributes:
        cells (list): A list of GlueCell instances.

    Methods:
        setCells(cells): Sets the list of glue cells.
        getCellById(id): Retrieves a glue cell by its unique identifier.
    """

    def __init__(self, cells, config, config_path):
        """
        Initializes a GlueCellsManager instance.

        Args:
            cells (list): A list of GlueCell instances.
            config: Validated GlueMonitorConfig instance.
            config_path: Path to configuration file.

        Raises:
            TypeError: If any item in the cells list is not an instance of GlueCell.
        """
        self.logTag = "GlueCellsManager"
        self.setCells(cells)
        self.config_path = config_path
        self.config = config


    def updateGlueTypeById(self, id, glueType: str):
        """
        Updates the glue type of a specific glue cell by its unique identifier
        and persists the change to the config file.

        Args:
            id: Cell ID
            glueType: New glue type (e.g., "Type A", "Custom Glue X")
        """
        glueType_str = glueType

        log_if_enabled(LoggingLevel.INFO, f"🔄 UPDATING GLUE TYPE: Cell {id} → {glueType_str}")

        cell = self.getCellById(id)
        if cell is None:
            log_if_enabled(LoggingLevel.ERROR, f"❌ CELL NOT FOUND: Cell {id} does not exist")
            return False

        log_if_enabled(LoggingLevel.DEBUG, f"Setting cell {id} glue type from {cell.glueType} to {glueType_str}")
        cell.setGlueType(glueType_str)

        import json
        with self.config_path.open("r") as f:
            config_data = json.load(f)
        
        for c in config_data["cells"]:
            if c["id"] == id:
                c["type"] = glueType_str
                break

        with self.config_path.open("w") as f:
            json.dump(config_data, f, indent=2)

        return True


    def setCells(self, cells):
        """
        Sets the list of glue cells.

        Args:
            cells (list): A list of GlueCell instances.

        Raises:
            TypeError: If any item in the cells list is not an instance of GlueCell.
        """
        if not all(isinstance(cell, GlueCell) for cell in cells):
            raise TypeError(f"[DEBUG] {self.logTag} All items in the cells list must be instances of GlueCell")
        self.cells = cells

    def getCellById(self, id):
        """
        Retrieves a glue cell by its unique identifier.

        Args:
            id (int): The unique identifier of the glue cell.

        Returns:
            GlueCell: The glue cell with the specified identifier, or None if not found.
        """
        for cell in self.cells:
            if cell.id == id:
                return cell
        return None

    def pollGlueDataById(self,id):
        weight, percent = self.getCellById(id).getGlueInfo()
        return weight, percent

    def __str__(self):
        """
        Returns a string representation of the GlueCellsManager instance.

        Returns:
            str: A string representation of the GlueCellsManager instance.
        """
        return f"CellsManager(cells={self.cells})"
