from __future__ import annotations

from src.robot_systems.twin_robot.applications.dashboard.view.twin_dashboard_view import (
    TwinDashboardView,
)


class TwinDashboardFactory:
    def build(self, service, messaging=None):
        view = TwinDashboardView()

        def refresh() -> None:
            view.set_choreographies(service.list_choreographies())

        def select(choreography_id: str) -> None:
            try:
                choreography = service.select(choreography_id)
                view.loop_count.setValue(max(1, int(choreography.loop_count)))
                view.set_plan_status(False, False, "Selected. Press PLAN BOTH.")
            except Exception as exc:
                view.set_plan_status(False, False, str(exc))

        def plan() -> None:
            try:
                result = service.plan_selected()
            except Exception as exc:
                view.set_plan_status(False, False, str(exc))
                return
            view.set_plan_status(
                bool(result.get("robot1_ready", False)),
                bool(result.get("robot2_ready", False)),
                str(result.get("error", "") or ("Both trajectories prepared" if result.get("success") else "Planning failed")),
            )

        def start(loop_count: int) -> None:
            try:
                result = service.start(loop_count=loop_count)
                view.set_message(str(result.get("error", "") or ("Choreography started" if result.get("success") else "Start failed")))
            except Exception as exc:
                view.set_message(str(exc))

        def stop() -> None:
            try:
                result = service.stop()
                view.set_message(str(result.get("error", "") or "Stop requested"))
            except Exception as exc:
                view.set_message(str(exc))

        view.choreography_selected.connect(select)
        view.plan_requested.connect(plan)
        view.start_requested.connect(start)
        view.stop_requested.connect(stop)
        refresh()
        return view
