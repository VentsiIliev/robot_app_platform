from ..ui.CreateWorkpieceForm import CreateWorkpieceForm
from .workpiece_form_config import create_workpiece_form_config


class WorkpieceFormFactory:

    def __init__(self, glue_types=None):
        self.glue_types = glue_types or ["Type A", "Type B", "Type C"]

    def create_form(self, parent=None):
        print("🏭 Creating workpiece form...")
        print(f"   ✅ Using configured glue types: {self.glue_types}")

        form_config = create_workpiece_form_config(self.glue_types)

        form = CreateWorkpieceForm(
            parent=parent,
            form_config=form_config,
            showButtons=False
        )
        form.setFixedWidth(400)
        print("✅ Workpiece form created")
        return form
