from .workpiece_field import WorkpieceField
class WorkpieceFieldProvider:
    """
    Singleton provider for workpiece field configuration.
    Provides access to field enum and defines required fields.
    """
    _instance = None
    @classmethod
    def get_instance(cls):
        """Get singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    def get_field_enum(self):
        """Get the WorkpieceField enum class"""
        return WorkpieceField
    def get_required_fields(self):
        """Get list of required field names (as enum attribute names)"""
        return [
            "WORKPIECE_ID",
            "HEIGHT",
            "GLUE_TYPE"
        ]
    def is_field_required(self, field_name: str) -> bool:
        """Check if a field is required"""
        return field_name.upper() in self.get_required_fields()
