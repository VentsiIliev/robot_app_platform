import sys
import os

from src.robot_systems.paint.domain.vacuum_pump.ModbusController import ModbusController

# Ensure we can import from the project root
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify, request
import json

app = Flask(__name__)

# Default Modbus settings (will be overridden by robot_config.json if possible)
MODBUS_SETTINGS = {
    "enabled": True,
    "port": "/dev/ttyUSB0",
    "baudrate": 57600,
    "slave_id": 1,
    "byte_size": 8,
    "parity": "EVEN",
    "stop_bits": 1,
    "timeout": 0.001
}

def load_settings():
    # Try multiple possible locations for robot_config.json
    possible_paths = [
        "applications/edge_painting_application/storage/settings/robot_config.json",
        "applications/glue_dispensing_application/storage/settings/robot_config.json",
        "core/database/settings/robot_config.json"
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    config_data = json.load(f)
                    MODBUS_SETTINGS["enabled"] = config_data.get("MODBUS_ENABLED", MODBUS_SETTINGS["enabled"])
                    MODBUS_SETTINGS["port"] = config_data.get("MODBUS_PORT", MODBUS_SETTINGS["port"])
                    MODBUS_SETTINGS["baudrate"] = config_data.get("MODBUS_BAUDRATE", MODBUS_SETTINGS["baudrate"])
                    MODBUS_SETTINGS["slave_id"] = config_data.get("MODBUS_SLAVE_ID", MODBUS_SETTINGS["slave_id"])
                    MODBUS_SETTINGS["byte_size"] = config_data.get("MODBUS_BYTE_SIZE", MODBUS_SETTINGS["byte_size"])
                    MODBUS_SETTINGS["parity"] = config_data.get("MODBUS_PARITY", MODBUS_SETTINGS["parity"])
                    MODBUS_SETTINGS["stop_bits"] = config_data.get("MODBUS_STOP_BITS", MODBUS_SETTINGS["stop_bits"])
                    MODBUS_SETTINGS["timeout"] = config_data.get("MODBUS_TIMEOUT", MODBUS_SETTINGS["timeout"])
                    print(f"Loaded Modbus settings from {path}")
                    return True
            except Exception as e:
                print(f"Error loading settings from {path}: {e}")
    return False

# Initialize
load_settings()
ModbusController.initialize(MODBUS_SETTINGS)

@app.route('/relay/y0/on', methods=['GET', 'POST'])
def turn_on_y0():
    relay = ModbusController.get_relay_controller()
    if not relay:
        return jsonify({"success": False, "error": "Relay controller not initialized"}), 500
    
    success = relay.write_output(0, True)
    if success:
        return jsonify({"success": True, "message": "Y0 turned ON"})
    else:
        return jsonify({"success": False, "error": "Failed to turn ON Y0"}), 500

@app.route('/relay/y0/off', methods=['GET', 'POST'])
def turn_off_y0():
    relay = ModbusController.get_relay_controller()
    if not relay:
        return jsonify({"success": False, "error": "Relay controller not initialized"}), 500
    
    success = relay.write_output(0, False)
    if success:
        return jsonify({"success": True, "message": "Y0 turned OFF"})
    else:
        return jsonify({"success": False, "error": "Failed to turn OFF Y0"}), 500

@app.route('/relay/y0/status', methods=['GET'])
def get_y0_status():
    relay = ModbusController.get_relay_controller()
    if not relay:
        return jsonify({"success": False, "error": "Relay controller not initialized"}), 500
    
    try:
        status = relay.read_output(0)
        return jsonify({"success": True, "status": "ON" if status else "OFF", "value": status})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/relay/status', methods=['GET'])
def get_all_status():
    relay = ModbusController.get_relay_controller()
    if not relay:
        return jsonify({"success": False, "error": "Relay controller not initialized"}), 500
    
    try:
        outputs = relay.read_all_outputs()
        inputs = relay.read_all_inputs()
        return jsonify({
            "success": True, 
            "outputs": outputs,
            "inputs": inputs
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/relay/<int:output_num>/<string:state>', methods=['GET', 'POST'])
def set_relay_state(output_num, state):
    relay = ModbusController.get_relay_controller()
    if not relay:
        return jsonify({"success": False, "error": "Relay controller not initialized"}), 500
    
    if output_num < 0 or output_num > 7:
        return jsonify({"success": False, "error": "Invalid output number (0-7)"}), 400
    
    value = state.lower() in ['on', 'true', '1']
    success = relay.write_output(output_num, value)
    
    if success:
        return jsonify({"success": True, "message": f"Y{output_num} turned {'ON' if value else 'OFF'}"})
    else:
        return jsonify({"success": False, "error": f"Failed to set Y{output_num} state"}), 500

@app.route('/')
def index():
    return """
    <h1>Relay Control Server</h1>
    <ul>
        <li><a href="/relay/y0/on">Turn Y0 ON</a></li>
        <li><a href="/relay/y0/off">Turn Y0 OFF</a></li>
        <li><a href="/relay/y0/status">Get Y0 Status</a></li>
        <li><a href="/relay/status">Get All Status</a></li>
    </ul>
    """

if __name__ == '__main__':
    # Using port 5003
    print(f"Starting Relay Control Server on port 5000...")
    app.run(host='0.0.0.0', port=5003, threaded=True)
