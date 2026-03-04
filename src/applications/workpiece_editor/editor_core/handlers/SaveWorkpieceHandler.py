from typing import Dict, Any, List


class SaveWorkpieceHandler:

    @classmethod
    def validate_form_data(cls, data: Dict[str, Any], required_keys: List[str]) -> tuple[bool, List[str]]:
        errors = [f"'{k}' is required" for k in required_keys if not data.get(k)]
        return len(errors) == 0, errors
