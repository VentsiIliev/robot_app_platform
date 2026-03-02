from ..ui.CreateWorkpieceForm import CreateWorkpieceForm
from .workpiece_form_config import create_workpiece_form_config
from .workpiece_form_schema import WorkpieceFormSchema


class WorkpieceFormFactory:

    def __init__(self, schema: WorkpieceFormSchema):
        self._schema = schema

    def create_form(self, parent=None):
        form_config = create_workpiece_form_config(self._schema)
        form = CreateWorkpieceForm(
            parent=parent,
            form_config=form_config,
            showButtons=False,
        )
        form.setFixedWidth(400)
        return form
