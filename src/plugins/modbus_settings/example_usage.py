# ── Wire into a robot app ─────────────────────────────────────────────────
#
# def _build_modbus_settings_plugin(robot_app):
#     from src.plugins.base.widget_plugin import WidgetPlugin
#     from src.plugins.modbus_settings import ModbusSettingsFactory, ModbusSettingsPluginService
#
#     service = ModbusSettingsPluginService(robot_app._settings_service)
#     factory = ModbusSettingsFactory()
#     return WidgetPlugin(widget_factory=lambda _ms: factory.build(service))


def run_standalone() -> None:
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow
    from src.plugins.modbus_settings.modbus_settings_factory import ModbusSettingsFactory
    from src.plugins.modbus_settings.service.stub_modbus_settings_service import StubModbusSettingsService

    app    = QApplication(sys.argv)
    widget = ModbusSettingsFactory().build(StubModbusSettingsService())

    window = QMainWindow()
    window.setWindowTitle("Modbus Settings — standalone")
    window.setCentralWidget(widget)
    window.resize(900, 600)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_standalone()