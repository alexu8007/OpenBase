
#!/usr/bin/env python3
import paho.mqtt.client as mqtt
import json
import math
import time
import signal
import sys
from flask import Flask, jsonify
import threading
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))  # noqa: E501
import config

INPUT_MQTT_BROKER = config.MQTT_BROKER
INPUT_MQTT_PORT = config.MQTT_PORT
MQTT_INPUT_TOPIC = "pi2/gyro"

OUTPUT_MQTT_BROKER = config.MQTT_BROKER
OUTPUT_MQTT_PORT = config.MQTT_PORT
MQTT_OUTPUT_TOPIC = "pi2/pitch_yaw_roll"

last_timestamp = 0
first_message = True
gyro_integrated = {"roll": 0, "pitch": 0, "yaw": 0}

gyro_calibration = {"x": 0, "y": 0, "z": 0}
calibration_samples = 0
is_calibrating = True
CALIBRATION_SAMPLES_NEEDED = 100

YAW_DRIFT_COMPENSATION = 0.98

ALPHA = 0.96

NOISE_THRESHOLD = 0.03

app = Flask(__name__)
HTTP_PORT = 5002

def on_connect(client: mqtt.Client, userdata: object, flags: dict, rc: int) -> None:
    """Callback function when the MQTT client connects."""
    print(f"Connected to MQTT broker with result code {rc}")
    client.subscribe(MQTT_INPUT_TOPIC)
    print(f"Subscribed to {MQTT_INPUT_TOPIC}")

def on_message(client: mqtt.Client, userdata: object, msg: mqtt.MQTTMessage) -> None:
    """Callback function for incoming MQTT messages."""
    global last_timestamp, gyro_integrated, first_message
    global gyro_calibration, calibration_samples, is_calibrating
    
    try:
        data = json.loads(msg.payload.decode())
        
        gyro_x = data.get("gyro", {}).get("x", 0)
        gyro_y = data.get("gyro", {}).get("y", 0)
        gyro_z = data.get("gyro", {}).get("z", 0)
        
        # temp_y = gyro_y
        gyro_y = -gyro_y
        # gyro_z = -gyro_z
                
        current_timestamp = data.get("timestamp", 0)
        
        if is_calibrating and calibration_samples < CALIBRATION_SAMPLES_NEEDED:
            gyro_calibration["x"] += gyro_x
            gyro_calibration["y"] += gyro_y
            gyro_calibration["z"] += gyro_z
            calibration_samples += 1
            
            if calibration_samples == CALIBRATION_SAMPLES_NEEDED:
                gyro_calibration["x"] /= CALIBRATION_SAMPLES_NEEDED
                gyro_calibration["y"] /= CALIBRATION_SAMPLES_NEEDED
                gyro_calibration["z"] /= CALIBRATION_SAMPLES_NEEDED
                is_calibrating = False
                print(f"Calibration complete: {gyro_calibration}")
            return
        
        gyro_x -= gyro_calibration["x"]
        gyro_y -= gyro_calibration["y"]
        gyro_z -= gyro_calibration["z"]
        
        if abs(gyro_x) < NOISE_THRESHOLD: gyro_x = 0
        if abs(gyro_y) < NOISE_THRESHOLD: gyro_y = 0
        if abs(gyro_z) < NOISE_THRESHOLD: gyro_z = 0
        
        accel_x = data.get("accel", {}).get("x", 0)
        accel_y = data.get("accel", {}).get("y", 0)
        accel_z = data.get("accel", {}).get("z", 0)
        
        accel_roll = math.degrees(math.atan2(accel_y, accel_z))
        accel_pitch = math.degrees(math.atan2(-accel_x, math.sqrt(accel_y**2 + accel_z**2)))
        
        if first_message:
            gyro_integrated = {"roll": accel_roll, "pitch": accel_pitch, "yaw": 0}
            first_message = False
            last_timestamp = current_timestamp
        elif last_timestamp > 0:
            dt = current_timestamp - last_timestamp
            
            gyro_integrated["roll"] += gyro_x * dt
            gyro_integrated["pitch"] += gyro_y * dt
            gyro_integrated["yaw"] += gyro_z * dt * YAW_DRIFT_COMPENSATION
            
            gyro_integrated["roll"] = ALPHA * gyro_integrated["roll"] + (1 - ALPHA) * accel_roll
            gyro_integrated["pitch"] = ALPHA * gyro_integrated["pitch"] + (1 - ALPHA) * accel_pitch
            
            if gyro_integrated["yaw"] > 180:
                gyro_integrated["yaw"] -= 360
            elif gyro_integrated["yaw"] < -180:
                gyro_integrated["yaw"] += 360
        
        last_timestamp = current_timestamp
        
        roll = max(min(gyro_integrated["roll"], 180), -180) + 270
        pitch = max(min(gyro_integrated["pitch"], 180), -180)
        yaw = max(min(gyro_integrated["yaw"], 180), -180)
        
        output_data = {
            "pitch": round(pitch, 2),
            "yaw": round(yaw, 2),
            "roll": round(roll, 2)
        }
        
        output_client.publish(MQTT_OUTPUT_TOPIC, json.dumps(output_data))
        
        if current_timestamp % 5 < 0.1:
            print(''.join(["Published: ", str(output_data)]))
            
    except Exception as e:
        print(f"Error processing message: {e}")

@app.route('/calibrate', methods=['POST'])
def reset_calibration() -> str:
    """Reset calibration data and perform calibration."""
    global gyro_calibration, calibration_samples, is_calibrating, first_message, last_timestamp, gyro_integrated
    
    print("Resetting calibration...")
    gyro_calibration = {"x": 0, "y": 0, "z": 0}
    calibration_samples = 0
    is_calibrating = True
    first_message = True
    last_timestamp = 0
    gyro_integrated = {"roll": 0, "pitch": 0, "yaw": 0}
    
    while is_calibrating:
        time.sleep(0.1)
    
    return jsonify({
        "status": "success",
        "message": "Calibration complete."
    })

@app.route('/zero', methods=['POST'])
def zero_orientation() -> str:
    """Zero the orientation values."""
    global gyro_integrated, first_message, last_timestamp
    
    print("Zeroing pitch, yaw, and roll...")
    gyro_integrated = {"roll": 0, "pitch": 0, "yaw": 0}
    first_message = True
    last_timestamp = 0
    
    return jsonify({
        "status": "success",
        "message": "Orientation zeroed successfully."
    })

def run_flask() -> None:
    """Run the Flask application."""
    app.run(host='127.0.0.1', port=HTTP_PORT)

def signal_handler(sig: int, frame: object) -> None:
    """Handle signals for shutdown."""
    print("Shutting down service")
    input_client.loop_stop()
    output_client.disconnect()
    sys.exit(0)

if __name__ == '__main__':
    print("Starting gyro service")
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    input_client = mqtt.Client()
    input_client.on_connect = on_connect
    input_client.on_message = on_message
    
    output_client = mqtt.Client()
    
    try:
        print(f"Connecting to input MQTT broker at {INPUT_MQTT_BROKER}:{INPUT_MQTT_PORT}")
        input_client.connect(INPUT_MQTT_BROKER, INPUT_MQTT_PORT, 60)
        input_client.loop_start()
        
        print(f"Connecting to output MQTT broker at {OUTPUT_MQTT_BROKER}:{OUTPUT_MQTT_PORT}")
        output_client.connect(OUTPUT_MQTT_BROKER, OUTPUT_MQTT_PORT, 60)
        
        print(f"Starting HTTP server on port {HTTP_PORT}")
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        
        while True:
            time.sleep(1)
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
