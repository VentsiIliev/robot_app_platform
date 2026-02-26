# ── Wire into GlueRobotApp ────────────────────────────────────────────────
#
# def _build_glue_settings_plugin(robot_app):
#     from src.plugins.base.widget_plugin import WidgetPlugin
#     from src.robot_apps.glue.glue_settings import GlueSettingsFactory, GlueSettingsPluginService
#
#     service = GlueSettingsPluginService(robot_app._settings_service)
#     factory = GlueSettingsFactory()
#     return WidgetPlugin(widget_factory=lambda _ms: factory.build(service))


def run_standalone() -> None:
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow
    from src.robot_apps.glue.glue_settings.glue_settings_factory import GlueSettingsFactory
    from src.robot_apps.glue.glue_settings.service.stub_glue_settings_service import StubGlueSettingsService

    app    = QApplication(sys.argv)
    widget = GlueSettingsFactory().build(StubGlueSettingsService())

    window = QMainWindow()
    window.setWindowTitle("Glue Settings — standalone")
    window.setCentralWidget(widget)
    window.resize(1280, 900)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_standalone()