# ── Wire into a robot app ─────────────────────────────────────────────────
#
# def _build_my_application(robot_app):
#     from src.applications.APPLICATION_BLUEPRINT.my_application import MyApplication
#     return MyApplication(
#         settings_service=robot_app._settings_service,
#         # robot_service=robot_app.get_service("robot"),
#     )
#
# class YourRobotApp(BaseRobotApp):
#     shell = ShellSetup(
#         folders=[
#             FolderSpec(folder_id=1, name="PRODUCTION", display_name="Production"),
#             FolderSpec(folder_id=2, name="SERVICE",    display_name="Service"),
#         ],
#         applications=[
#             ApplicationSpec(
#                 name="MyApplication",
#                 folder_id=2,
#                 icon="fa5s.cog",
#                 factory=_build_my_application,
#             ),
#         ],
#     )


# ── Standalone dev runner ─────────────────────────────────────────────────

def run_standalone() -> None:
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow
    from src.applications.APPLICATION_BLUEPRINT.my_application_factory import MyApplicationFactory
    from src.applications.APPLICATION_BLUEPRINT.service.stub_my_service import StubMyService

    app    = QApplication(sys.argv)
    widget = MyApplicationFactory().build(StubMyService())

    window = QMainWindow()
    window.setCentralWidget(widget)
    window.resize(1280, 900)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_standalone()
