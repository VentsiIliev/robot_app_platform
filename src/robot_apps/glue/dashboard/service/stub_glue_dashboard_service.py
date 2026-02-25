from typing import Dict, List, Optional
from src.robot_apps.glue.dashboard.service.i_glue_dashboard_service import IGlueDashboardService
#for testing / early dev:

class StubGlueDashboardService(IGlueDashboardService):

    def start(self)              -> None:          print("[GlueDashboard] ▶ start")
    def stop(self)               -> None:          print("[GlueDashboard] ■ stop")
    def pause(self)              -> None:          print("[GlueDashboard] ⏸ pause")
    def clean(self)              -> None:          print("[GlueDashboard] 🧹 clean")
    def reset_errors(self)       -> None:          print("[GlueDashboard] ↺ reset_errors")
    def set_mode(self, mode: str) -> None:         print(f"[GlueDashboard] ⚙ set_mode → {mode}")
    def get_cell_capacity(self, cell_id: int) -> float:         return 5000.0
    def get_cell_glue_type(self, cell_id: int) -> Optional[str]: return "Type A"
    def get_all_glue_types(self) -> List[str]:                   return ["Type A", "Type B"]
    def get_initial_cell_state(self, cell_id: int) -> Optional[Dict]: return None