# ── Wire into a robot app ─────────────────────────────────────────────────
#
# def _build_my_plugin(robot_app):
#     from src.plugins.PLUGIN_BLUEPRINT.my_plugin import MyPlugin
#     return MyPlugin(
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
#         plugins=[
#             PluginSpec(
#                 name="MyPlugin",
#                 folder_id=2,
#                 icon="fa5s.cog",
#                 factory=_build_my_plugin,
#             ),
#         ],
#     )


# ── Standalone dev runner ─────────────────────────────────────────────────

def run_standalone() -> None:
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow
    from src.plugins.PLUGIN_BLUEPRINT.my_plugin_factory import MyPluginFactory
    from src.plugins.PLUGIN_BLUEPRINT.service.stub_my_service import StubMyService

    app    = QApplication(sys.argv)
    widget = MyPluginFactory().build(StubMyService())

    window = QMainWindow()
    window.setCentralWidget(widget)
    window.resize(1280, 900)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_standalone()
