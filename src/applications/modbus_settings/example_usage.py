def run_standalone() -> None:
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow
    from src.applications.modbus_settings.modbus_settings_factory import ModbusSettingsFactory
    from src.applications.modbus_settings.service.stub_modbus_settings_service import StubModbusSettingsService
    from src.applications.modbus_settings.service.stub_modbus_action_service import StubModbusActionService

    app    = QApplication(sys.argv)
    widget = ModbusSettingsFactory().build(StubModbusSettingsService(), StubModbusActionService())

    window = QMainWindow()
    window.setWindowTitle("Modbus Settings — standalone")
    window.setCentralWidget(widget)
    window.resize(900, 600)
    window.show()
    sys.exit(app.exec())
