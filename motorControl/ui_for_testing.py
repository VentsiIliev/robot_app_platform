import sys
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTextEdit, QComboBox, QSpinBox
)
from PyQt6.QtCore import Qt

from applications.glue_dispensing_application.services.glueSprayService.motorControl.MotorControl import MotorControl


class MotorControlUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Motor Control GUI")
        self.setGeometry(100, 100, 600, 400)

        self.motor_control = MotorControl()

        # Layouts
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Motor selection
        motor_layout = QHBoxLayout()
        layout.addLayout(motor_layout)
        motor_layout.addWidget(QLabel("Motor Address:"))
        self.motor_combo = QComboBox()
        self.motor_combo.addItems(["0", "2", "4", "6"])
        motor_layout.addWidget(self.motor_combo)

        # Speed input
        speed_layout = QHBoxLayout()
        layout.addLayout(speed_layout)
        speed_layout.addWidget(QLabel("Speed:"))
        self.speed_input = QSpinBox()
        self.speed_input.setMaximum(50000)
        self.speed_input.setValue(10000)
        speed_layout.addWidget(self.speed_input)

        # Reverse speed input
        reverse_layout = QHBoxLayout()
        layout.addLayout(reverse_layout)
        reverse_layout.addWidget(QLabel("Reverse Speed:"))
        self.reverse_input = QSpinBox()
        self.reverse_input.setMaximum(50000)
        self.reverse_input.setValue(250)
        reverse_layout.addWidget(self.reverse_input)

        # Command buttons
        button_layout = QHBoxLayout()
        layout.addLayout(button_layout)

        self.on_button = QPushButton("Motor ON")
        self.on_button.clicked.connect(self.motor_on)
        button_layout.addWidget(self.on_button)

        self.off_button = QPushButton("Motor OFF")
        self.off_button.clicked.connect(self.motor_off)
        button_layout.addWidget(self.off_button)

        self.state_button = QPushButton("Motor State")
        self.state_button.clicked.connect(self.motor_state)
        button_layout.addWidget(self.state_button)

        self.all_states_button = QPushButton("All Motor States")
        self.all_states_button.clicked.connect(self.all_motor_states)
        button_layout.addWidget(self.all_states_button)

        # Log/output area
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)

    def log(self, message):
        self.log_output.append(message)
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())

    def motor_on(self):
        motor_addr = int(self.motor_combo.currentText())
        speed = self.speed_input.value()
        self.log(f"Turning motor {motor_addr} ON at speed {speed}")
        result = self.motor_control.motorOn(motor_addr, speed, ramp_steps=3, initial_ramp_speed=22000, initial_ramp_speed_duration=1)
        self.log(f"Motor ON result: {result}")

    def motor_off(self):
        motor_addr = int(self.motor_combo.currentText())
        speed_reverse = self.reverse_input.value()
        self.log(f"Turning motor {motor_addr} OFF with reverse speed {speed_reverse}")
        result = self.motor_control.motorOff(motor_addr, speed_reverse, reverse_time=0.5, ramp_steps=1)
        self.log(f"Motor OFF result: {result}")

    def motor_state(self):
        motor_addr = int(self.motor_combo.currentText())
        self.log(f"Fetching state for motor {motor_addr}")
        state = self.motor_control.motorState(motor_addr)
        self.log(f"Motor {motor_addr} state: {state}")
        self.log(f"Modbus Errors: {state.modbus_errors}")

    def all_motor_states(self):
        self.log("Fetching all motor states")
        all_states = self.motor_control.getAllMotorStates()
        self.log(f"Success: {all_states.success}")
        for addr, state in all_states.motors.items():
            self.log(f"Motor {addr}: {state}")
        sorted_errors = all_states.get_all_errors_sorted()
        self.log(f"Sorted Errors: {sorted_errors}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MotorControlUI()
    window.show()
    sys.exit(app.exec())
