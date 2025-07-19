
# Standard library imports
import json
import os
import threading
import time

# Third-party imports
from flask import Flask, render_template, request, jsonify
import paho.mqtt.client as mqtt
import requests
from flask_socketio import SocketIO

# Local imports
from dashboard_utils import on_rpi2_message, on_rpi4_message, setup_mqtt, stop_mqtt_clients, rpi2_client_loop, rpi4_client_loop

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
FLASK_HOST = '127.0.0.1'
FLASK_PORT = 8080
FLASK_DEBUG = False
RPI2_BROKER = "192.168.2.219"
RPI4_BROKER = "192.168.2.220"
MQTT_PORT = 1883
MQTT_KEEPALIVE = 60

RPI2_TOPICS = {
    "button_state": "pi2/button_state",
    "gyro": "pi2/gyro",
    "vibration_motor_response": "pi2/vibration_motor_response",
    "pitch_yaw_roll": "pi2/pitch_yaw_roll"
}

RPI4_TOPICS = {
    "gyro": "pi4/gyro",
    "vibration_motor_controller": "pi4/vibration_motor_controller",
    "pitch_yaw_roll": "pi4/pitch_yaw_roll",
    "detections": "pi4/detections",
    "detection_image": "pi4/detection_image",
    "depth_map": "pi4/depth_map",
    "menu": "pi4/menu",
    "menu_logs": "pi4/menu_logs"
}

MESSAGE_CATEGORIES = {
    "CANE_BUTTON_STATE": "Cane Button State",
    "GYRO": "Gyro",
    "VIBRATION_MOTOR_RESPONSE": "Vibration Motor Response",
    "CAMERA_DETECTIONS": "Camera Detections",
    "HEADSET_GYRO": "Headset Gyro",
    "HEADSET_VIBRATION_MOTOR_CONTROLLER": "Headset Vibration Motor Controller",
    "PITCH_YAW_ROLL": "Pitch Yaw Roll",
    "MENU": "Menu",
    "MENU_LOGS": "Menu Logs"
}

CAMERA_CONTROL_API_URL = "http://localhost:8010"
VIBRATION_API_URL = "http://localhost:5000/vibrate"
DETECTION_API_URL = "http://localhost:8005/detections"
AUDIO_API_BASE_URL = "http://localhost:5001"
PLAY_AUDIO_ENDPOINT = f"{AUDIO_API_BASE_URL}/play_file"
SET_VOLUME_ENDPOINT = f"{AUDIO_API_BASE_URL}/set_volume"
GET_VOLUME_ENDPOINT = f"{AUDIO_API_BASE_URL}/get_volume"
TTS_ENDPOINT = f"{AUDIO_API_BASE_URL}/tts"
HEADSET_CALIBRATION_ENDPOINT = f"http://{RPI4_BROKER}:5002/calibrate"
HEADSET_ZERO_ENDPOINT = f"http://{RPI4_BROKER}:5002/zero"
CANE_CALIBRATION_ENDPOINT = f"http://{RPI2_BROKER}:5002/calibrate"
CANE_ZERO_ENDPOINT = f"http://{RPI2_BROKER}:5002/zero"
MQTT_API_URL = "http://localhost:8080/mqtt_service"
CAMERA_CONTROL_START_API_ENDPOINT = f"{CAMERA_CONTROL_API_URL}/start"
CAMERA_CONTROL_STOP_API_ENDPOINT = f"{CAMERA_CONTROL_API_URL}/stop"
CAMERA_CONTROL_STATUS_API_ENDPOINT = f"{CAMERA_CONTROL_API_URL}/status"

DEFAULT_TTS_SPEED = 125
DEFAULT_TTS_VOICE = "en-us"

SOCKETIO_MQTT_UPDATE = 'mqtt_update'
SOCKETIO_MQTT_CONNECTION_STATUS = 'mqtt_connection_status'
SOCKETIO_MQTT_MESSAGE = 'mqtt_message'

app = Flask(__name__, template_folder=TEMPLATE_DIR)
socketio = SocketIO(app, cors_allowed_origins="*")

last_messages = {
    MESSAGE_CATEGORIES["CANE_BUTTON_STATE"]: None,
    MESSAGE_CATEGORIES["GYRO"]: None,
    MESSAGE_CATEGORIES["VIBRATION_MOTOR_RESPONSE"]: None,
    MESSAGE_CATEGORIES["CAMERA_DETECTIONS"]: None,
    MESSAGE_CATEGORIES["HEADSET_GYRO"]: None,
    MESSAGE_CATEGORIES["HEADSET_VIBRATION_MOTOR_CONTROLLER"]: None,
    MESSAGE_CATEGORIES["PITCH_YAW_ROLL"]: None
}

rpi2_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
rpi4_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_threads = []

def index() -> str:
    """Render the index HTML template."""
    return render_template('index.html')

def vibrate() -> tuple:
    """Handle POST request to vibrate device."""
    try:
        data = request.get_json()
        response = requests.post(
            VIBRATION_API_URL,
            headers={"Content-Type": "application/json"},
            json=data,
            timeout=10
        )
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def run_detection() -> tuple:
    """Handle GET request to run detection and update last messages."""
    try:
        response = requests.get(DETECTION_API_URL, timeout=10)
        detection_data = response.json()
        
        if 'status' in detection_data and detection_data['status'] == 'ok':
            last_messages[MESSAGE_CATEGORIES["CAMERA_DETECTIONS"]] = detection_data
            socketio.emit(SOCKETIO_MQTT_UPDATE, {'topic': MESSAGE_CATEGORIES["CAMERA_DETECTIONS"], 'payload': detection_data})
        
        return jsonify(detection_data), 200
    except Exception as e:
        return jsonify({
            "error": str(e),
            "status": "error"
        }), 500

def get_all_data() -> tuple:
    """Handle GET request to retrieve all last messages."""
    return jsonify(last_messages)

def refresh_mqtt() -> tuple:
    """Handle POST request to refresh MQTT connections."""
    try:
        connection_status = setup_mqtt()
        return jsonify({"status": "success", "connection": connection_status}), 200
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

def play_audio() -> tuple:
    """Handle POST request to play an audio file."""
    try:
        data = request.get_json()
        file_name = data.get('file')
        
        response = requests.get(
            f"{PLAY_AUDIO_ENDPOINT}?file={file_name}",
            timeout=10
        )
        return jsonify({"status": "success", "message": f"Playing {file_name}"}), 200
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

def set_volume() -> tuple:
    """Handle POST request to set audio volume."""
    try:
        data = request.get_json()
        volume = data.get('volume')
        
        response = requests.get(
            f"{SET_VOLUME_ENDPOINT}?volume={volume}",
            timeout=10
        )
        return jsonify({"status": "success", "message": f"Volume set to {volume}%"}), 200
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

def get_volume() -> tuple:
    """Handle GET request to retrieve current audio volume."""
    try:
        response = requests.get(GET_VOLUME_ENDPOINT, timeout=10)
        volume_data = response.json()
        return jsonify(volume_data), 200
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

def text_to_speech() -> tuple:
    """Handle POST request for text-to-speech conversion."""
    try:
        data = request.get_json()
        text = data.get('text')
        speed = data.get('speed', DEFAULT_TTS_SPEED)
        voice_name = data.get('voice_name', DEFAULT_TTS_VOICE)
        
        response = requests.get(
            f"{TTS_ENDPOINT}?text={text}&speed={speed}&voice_name={voice_name}",
            timeout=10
        )
        return jsonify({"status": "success", "message": "Speech played successfully"}), 200
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

def calibrate_headset_gyro() -> tuple:
    """Handle POST request to calibrate headset gyro."""
    try:
        response = requests.post(HEADSET_CALIBRATION_ENDPOINT, timeout=10)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
def zero_headset_gyro() -> tuple:
    """Handle POST request to zero headset gyro."""
    try:
        response = requests.post(HEADSET_ZERO_ENDPOINT, timeout=10)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
def calibrate_cane_gyro() -> tuple:
    """Handle POST request to calibrate cane gyro."""
    try:
        response = requests.post(CANE_CALIBRATION_ENDPOINT, timeout=10)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
def zero_cane_gyro() -> tuple:
    """Handle POST request to zero cane gyro."""
    try:
        response = requests.post(CANE_ZERO_ENDPOINT, timeout=10)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
def start_camera() -> tuple:
    """Handle POST request to start camera."""
    try:
        response = requests.post(CAMERA_CONTROL_START_API_ENDPOINT, timeout=10)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
def stop_camera() -> tuple:
    """Handle POST request to stop camera."""
    try:
        response = requests.post(CAMERA_CONTROL_STOP_API_ENDPOINT, timeout=10)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
def camera_status() -> tuple:
    """Handle GET request to get camera status."""
    try:
        response = requests.get(CAMERA_CONTROL_STATUS_API_ENDPOINT, timeout=10)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def restart_camera() -> tuple:
    """Handle POST request to restart camera."""
    try:
        response = requests.post(f"{CAMERA_CONTROL_API_URL}/restart", timeout=10)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

app.add_url_rule('/', 'index', index, methods=['GET'])
app.add_url_rule('/vibrate', 'vibrate', vibrate, methods=['POST'])
app.add_url_rule('/run_detection', 'run_detection', run_detection, methods=['GET'])
app.add_url_rule('/get_all_data', 'get_all_data', get_all_data, methods=['GET'])
app.add_url_rule('/refresh_mqtt', 'refresh_mqtt', refresh_mqtt, methods=['POST'])
app.add_url_rule('/play_audio', 'play_audio', play_audio, methods=['POST'])
app.add_url_rule('/set_volume', 'set_volume', set_volume, methods=['POST'])
app.add_url_rule('/get_volume', 'get_volume', get_volume, methods=['GET'])
app.add_url_rule('/text_to_speech', 'text_to_speech', text_to_speech, methods=['POST'])
app.add_url_rule('/calibrate_headset_gyro', 'calibrate_headset_gyro', calibrate_headset_gyro, methods=['POST'])
app.add_url_rule('/zero_headset_gyro', 'zero_headset_gyro', zero_headset_gyro, methods=['POST'])
app.add_url_rule('/calibrate_cane_gyro', 'calibrate_cane_gyro', calibrate_cane_gyro, methods=['POST'])
app.add_url_rule('/zero_cane_gyro', 'zero_cane_gyro', zero_cane_gyro, methods=['POST'])
app.add_url_rule('/start_camera', 'start_camera', start_camera, methods=['POST'])
app.add_url_rule('/stop_camera', 'stop_camera', stop_camera, methods=['POST'])
app.add_url_rule('/camera_status', 'camera_status', camera_status, methods=['GET'])
app.add_url_rule('/restart_camera', 'restart_camera', restart_camera, methods=['POST'])

if __name__ == '__main__':
    setup_mqtt()
    socketio.run(app, host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG, allow_unsafe_werkzeug=True)
