from __future__ import annotations

from src.robot_systems.twin_robot.applications.choreography_setup.view.choreography_setup_view import (
    ChoreographySetupView,
)
from src.robot_systems.twin_robot.domain import ChoreographyStep


class ChoreographySetupFactory:
    def build(self, service, messaging=None):
        view = ChoreographySetupView()
        current = {"definition": None}

        def render(message: str = "") -> None:
            choreography = current["definition"]
            if choreography is not None:
                view.set_definition(choreography)
            view.set_message(message)

        def new(choreography_id: str, name: str) -> None:
            if not choreography_id or not name:
                view.set_message("ID and name are required")
                return
            current["definition"] = service.new(choreography_id, name)
            render("New choreography created")

        def add_step() -> None:
            choreography = current["definition"]
            if choreography is None:
                view.set_message("Create or load a choreography first")
                return
            choreography.steps.append(ChoreographyStep(name=f"Step {len(choreography.steps) + 1}"))
            render()
            view.table.selectRow(len(choreography.steps) - 1)

        def delete_step(row: int) -> None:
            choreography = current["definition"]
            if choreography is None or not (0 <= row < len(choreography.steps)):
                return
            del choreography.steps[row]
            render()

        def capture_robot(robot_name: str, row: int) -> None:
            choreography = current["definition"]
            if choreography is None or not (0 <= row < len(choreography.steps)):
                view.set_message("Select a choreography step first")
                return
            try:
                captured = service.capture_robot(robot_name)
                setattr(choreography.steps[row], robot_name, captured)
                render(f"Captured {robot_name} into step {row + 1}")
                view.table.selectRow(row)
            except Exception as exc:
                view.set_message(str(exc))

        def capture_both(row: int) -> None:
            choreography = current["definition"]
            if choreography is None or not (0 <= row < len(choreography.steps)):
                view.set_message("Select a choreography step first")
                return
            try:
                choreography.steps[row].robot1 = service.capture_robot("robot1")
                choreography.steps[row].robot2 = service.capture_robot("robot2")
                render(f"Captured both robots into step {row + 1}")
                view.table.selectRow(row)
            except Exception as exc:
                view.set_message(str(exc))

        def sync_table_to_model() -> None:
            choreography = current["definition"]
            if choreography is None:
                return
            choreography.name = view.name_edit.text().strip()
            choreography.loop_count = int(view.loop_spin.value())
            for row, step in enumerate(choreography.steps):
                name_item = view.table.item(row, 0)
                if name_item:
                    step.name = name_item.text().strip() or step.name
                values = []
                for col in range(3, 7):
                    item = view.table.item(row, col)
                    values.append(float(item.text()) if item and item.text().strip() else 30.0)
                step.robot1_motion.velocity = values[0]
                step.robot1_motion.acceleration = values[1]
                step.robot2_motion.velocity = values[2]
                step.robot2_motion.acceleration = values[3]

        def save() -> None:
            choreography = current["definition"]
            if choreography is None:
                view.set_message("Nothing to save")
                return
            try:
                sync_table_to_model()
                service.save(choreography)
                errors = choreography.validate()
                render("Saved" if not errors else "Saved with validation warnings: " + "; ".join(errors))
            except Exception as exc:
                view.set_message(str(exc))

        def bind_jog(widget, robot_name: str) -> None:
            widget.jog_requested.connect(
                lambda command, axis, direction, step, name=robot_name: _safe_jog(
                    lambda: service.jog(name, command, axis, direction, step)
                )
            )
            widget.joint_jog_requested.connect(
                lambda command, joint, direction, step, name=robot_name: _safe_jog(
                    lambda: service.joint_jog(name, command, joint, direction, step)
                )
            )

        def _safe_jog(call) -> None:
            try:
                result = call()
                if int(result) != 0:
                    view.set_message(f"Jog returned {result}")
            except Exception as exc:
                view.set_message(str(exc))

        view.new_requested.connect(new)
        view.save_requested.connect(save)
        view.add_step_requested.connect(add_step)
        view.delete_step_requested.connect(delete_step)
        view.capture_robot_requested.connect(capture_robot)
        view.capture_both_requested.connect(capture_both)
        bind_jog(view.robot1_jog, "robot1")
        bind_jog(view.robot2_jog, "robot2")

        existing = service.list()
        if existing:
            current["definition"] = existing[0]
            render(f"Loaded {existing[0].name}")
        else:
            current["definition"] = service.new("new_choreography", "New Choreography")
            render("Create the start pose by jogging both robots and pressing Capture Both")
        return view
