from __future__ import annotations
from typing import List

from pl_gui.dashboard.config import CardConfig
from src.robot_apps.glue.dashboard.model.glue_dashboard_model import GlueDashboardModel


class GlueCardFactory:

    def __init__(self, model: GlueDashboardModel):
        self._model = model

    def build_cards(self, cell_configs: List[CardConfig]) -> list:
        from src.robot_apps.glue.dashboard.ui.widgets.GlueMeterCard import GlueMeterCard
        return [
            (
                GlueMeterCard(
                    cfg.label,
                    cfg.card_id,
                    capacity_grams=self._model.get_cell_capacity(cfg.card_id - 1),  # 0-based
                ),
                cfg.card_id,
                getattr(cfg, "row", 0),
                getattr(cfg, "col", 0),
            )
            for cfg in cell_configs
        ]
