# ── Wire into GlueRobotApp ────────────────────────────────────────────────
#
# def _build_glue_settings_application(robot_app):
#     from src.applications.base.widget_application import WidgetApplication
#     from src.robot_systems.glue.glue_settings import GlueSettingsFactory, GlueSettingsApplicationService
#
#     service = GlueSettingsApplicationService(robot_app._settings_service)
#     factory = GlueSettingsFactory()
#     return WidgetApplication(widget_factory=lambda _ms: factory.build(service))


def run_standalone() -> None:
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow
    from src.robot_systems.glue.applications.glue_settings import GlueSettingsFactory
    from src.robot_systems.glue.applications.glue_settings.service.stub_glue_settings_service import StubGlueSettingsService

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