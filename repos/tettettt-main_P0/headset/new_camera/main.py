import cv2
import depthai as dai
import numpy as np
import time
import json
import base64
from flask import Flask, Response, jsonify, request
import threading
import uuid
import paho.mqtt.client as mqtt
from new_camera_utils import frame_norm, create_placeholder_frame, calculate_distance, visualize_depth, draw_detections, frame_to_base64

MQTT_HOST = '127.0.0.1'
MQTT_PORT = 1883
MQTT_TOPIC_DETECTIONS = 'pi4/detections'
MQTT_TOPIC_DEPTH_MAP = 'pi4/depth_map'
MQTT_TOPIC_DETECTION_IMAGE = 'pi4/detection_image'

with open('yolov8ntrained.json', 'r') as f:
    model_config = json.load(f)

labels = model_config['mappings']['labels']
confidence_threshold = 0.6

app = Flask(__name__)

mqtt_client = mqtt.Client()
mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)

def start_mqtt_loop():
    mqtt_client.loop_forever()

def publish_message(topic: str, message: str) -> None:
    mqtt_client.publish(topic, message)

def create_pipeline() -> dai.Pipeline:
    """Create and configure the DepthAI pipeline."""
    pipeline = dai.Pipeline()
    
    cam_rgb = pipeline.create(dai.node.ColorCamera)
    mono_left = pipeline.create(dai.node.MonoCamera)
    mono_right = pipeline.create(dai.node.MonoCamera)
    stereo = pipeline.create(dai.node.StereoDepth)
    detection_network = pipeline.create(dai.node.YoloDetectionNetwork)
    
    xout_rgb = pipeline.create(dai.node.XLinkOut)
    xin_frame = pipeline.create(dai.node.XLinkIn)
    nn_out = pipeline.create(dai.node.XLinkOut)
    xout_depth = pipeline.create(dai.node.XLinkOut)
    
    xout_rgb.setStreamName("rgb")
    xin_frame.setStreamName("frame_in")
    nn_out.setStreamName("nn")
    xout_depth.setStreamName("depth")
    
    cam_rgb.setPreviewSize(320, 320)
    cam_rgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
    cam_rgb.setInterleaved(False)
    cam_rgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
    cam_rgb.setFps(24)
    
    mono_left.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
    mono_left.setBoardSocket(dai.CameraBoardSocket.LEFT)
    mono_right.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
    mono_right.setBoardSocket(dai.CameraBoardSocket.RIGHT)
    
    stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.HIGH_DENSITY)
    stereo.setLeftRightCheck(True)
    stereo.setExtendedDisparity(False)
    stereo.setSubpixel(True)
    
    detection_network.setBlobPath("yolov8ntrained_openvino_2022.1_6shave.blob")
    detection_network.setConfidenceThreshold(confidence_threshold)
    detection_network.setNumClasses(model_config['nn_config']['NN_specific_metadata']['classes'])
    detection_network.setCoordinateSize(model_config['nn_config']['NN_specific_metadata']['coordinates'])
    detection_network.setAnchors([])
    detection_network.setAnchorMasks({})
    detection_network.setIouThreshold(model_config['nn_config']['NN_specific_metadata']['iou_threshold'])
    detection_network.setNumInferenceThreads(2)
    detection_network.input.setBlocking(False)
    
    mono_left.out.link(stereo.left)
    mono_right.out.link(stereo.right)
    
    cam_rgb.preview.link(xout_rgb.input)
    stereo.depth.link(xout_depth.input)
    
    xin_frame.out.link(detection_network.input)
    detection_network.out.link(nn_out.input)
    
    return pipeline

latest_frame = None
latest_depth = None
device = None
frame_lock = threading.Lock()
depth_lock = threading.Lock()
running_inference = False

def run_pipeline() -> None:
    """Run the DepthAI pipeline loop, handling frame and depth capture."""
    global latest_frame, latest_depth, device
    consecutive_errors = 0
    max_consecutive_errors = 5
    device_in_use = False
    
    while True:
        try:
            if device_in_use:
                with frame_lock:
                    latest_frame = create_placeholder_frame("Camera in use by another application")
                time.sleep(2)
                device_in_use = False
                consecutive_errors = 0
                
            pipeline = create_pipeline()
            device = dai.Device(pipeline)
            
            q_rgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
            q_depth = device.getOutputQueue(name="depth", maxSize=4, blocking=False)
            
            print("Starting video stream...")
            consecutive_errors = 0
            
            while True:
                try:
                    in_rgb = q_rgb.get()
                    frame = in_rgb.getCvFrame()
                    
                    frame = cv2.flip(frame, 1)
                    frame = cv2.flip(frame, 0)
                    
                    in_depth = q_depth.tryGet()
                    if in_depth is not None:
                        depth_frame = in_depth.getFrame()
                        depth_frame = cv2.resize(depth_frame, (frame.shape[1], frame.shape[0]))
                        
                        with depth_lock:
                            latest_depth = depth_frame.copy()
                    
                    with frame_lock:
                        latest_frame = frame.copy()
                    
                    time.sleep(0.1)
                except dai.XLinkError as e:
                    print(f"XLink error during frame processing: {e}")
                    if "X_LINK_ERROR" in str(e):
                        device_in_use = True
                    break
                except Exception as e:
                    consecutive_errors += 1
                    print(f"Error during frame processing: {e}")
                    if consecutive_errors >= max_consecutive_errors:
                        break
                    time.sleep(1)
        
        except dai.XLinkError as e:
            print(f"XLink error during device initialization: {e}")
            if "X_LINK_DEVICE_ALREADY_IN_USE" in str(e) or "X_LINK_ERROR" in str(e):
                device_in_use = True
                print("Device appears to be in use by another application")
                with frame_lock:
                    latest_frame = create_placeholder_frame("Camera in use by another application")
            time.sleep(2)
        except Exception as e:
            print(f"Error during device initialization: {e}")
            consecutive_errors += 1
            time.sleep(2)
        
        print("Attempting to reconnect to device...")
        
        try:
            if device is not None:
                device.close()
        except Exception as e:
            print(f"Error closing device: {e}")

def generate_frames() -> str:
    global latest_frame
    while True:
        try:
            current_frame = None
            with frame_lock:
                if latest_frame is not None:
                    current_frame = latest_frame.copy()
                else:
                    current_frame = create_placeholder_frame()
            
            ret, buffer = cv2.imencode('.jpg', current_frame)
            frame_bytes = buffer.tobytes()
            
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        except Exception as e:
            print(f"Error in generate_frames: {e}")
            placeholder = create_placeholder_frame()
            ret, buffer = cv2.imencode('.jpg', placeholder)
            frame_bytes = buffer.tobytes()
            
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        time.sleep(0.1)

@app.route('/video_stream')
def video_stream() -> Response:
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/detections')
def get_detections() -> jsonify:
    global latest_frame, latest_depth, device, running_inference
    
    if latest_frame is None:
        return jsonify({"error": "No frame available"})
    
    if device is None:
        return jsonify({"error": "Camera device not initialized", "status": "disconnected"})
    
    if running_inference:
        return jsonify({"error": "Detection already in progress", "status": "busy"})
    
    running_inference = True
    
    placeholder_check = np.sum(latest_frame[:, :, 0]) + np.sum(latest_frame[:, :, 1]) + np.sum(latest_frame[:, :, 2])
    if placeholder_check < 10000:
        running_inference = False
        return jsonify({
            "error": "Camera not available or in use by another application", 
            "status": "unavailable",
            "detections": []
        })
    
    try:
        frame_copy = None
        depth_copy = None
        
        with frame_lock:
            if latest_frame is not None:
                frame_copy = latest_frame.copy()
            else:
                running_inference = False
                return jsonify({"error": "No frame available for detection"})
        
        with depth_lock:
            if latest_depth is not None:
                depth_copy = latest_depth.copy()
        
        nn_in = device.getInputQueue("frame_in")
        nn_out = device.getOutputQueue("nn", maxSize=4, blocking=True)
        
        img = dai.ImgFrame()
        img.setType(dai.ImgFrame.Type.BGR888p)
        c = 640
        img.setWidth(c)
        img.setHeight(c)
        img.setData(cv2.resize(frame_copy, (c, c)).transpose(2, 0, 1).flatten())
        
        nn_in.send(img)
        
        start_time = time.time()
        timeout = 2.0
        
        in_nn = None
        while time.time() - start_time < timeout:
            in_nn = nn_out.tryGet()
            if in_nn is not None:
                break
            time.sleep(0.1)
        
        if in_nn is None:
            running_inference = False
            return jsonify({"error": "Detection timeout, no results received from neural network"})
        
        detections = []
        for detection in in_nn.detections:
            label_id = detection.label
            if label_id < len(labels):
                label_name = labels[label_id]
            else:
                label_name = f"Class {label_id}"
            
            confidence = detection.confidence
            
            if confidence >= confidence_threshold:
                bbox = frame_norm(frame_copy, (detection.xmin, detection.ymin, detection.xmax, detection.ymax))
                
                distance = None
                if depth_copy is not None:
                    distance = calculate_distance(depth_copy, (bbox[0], bbox[1], bbox[2], bbox[3]))
                
                detection_data = {
                    "label": label_name,
                    "confidence": float(confidence),
                    "bbox": {
                        "x1": int(bbox[0]),
                        "y1": int(bbox[1]),
                        "x2": int(bbox[2]),
                        "y2": int(bbox[3])
                    }
                }
                
                if distance is not None:
                    detection_data["distance"] = round(float(distance), 2)
                
                detections.append(detection_data)
        
        detection_image = None
        depth_map = None
        
        if frame_copy is not None:
            detection_image = draw_detections(frame_copy, detections)
            detection_image_b64 = frame_to_base64(detection_image)
        else:
            detection_image_b64 = None
            
        if depth_copy is not None:
            depth_map = visualize_depth(depth_copy)
            depth_map_b64 = frame_to_base64(depth_map)
        else:
            depth_map_b64 = None
        
        class_counts = {}
        for detection in detections:
            label = detection["label"]
            if label in class_counts:
                class_counts[label] += 1
            else:
                class_counts[label] = 1
        
        running_inference = False
        
        unique_id = uuid.uuid4()
        publish_message(MQTT_TOPIC_DETECTIONS, json.dumps({
            "timestamp": time.time(),
            "id": str(unique_id),
            "num_detections": len(detections),
            "detections": detections
        }))
        
        if detection_image_b64 is not None:
            publish_message(MQTT_TOPIC_DETECTION_IMAGE, json.dumps({
                "timestamp": time.time(),
                "id": str(unique_id),
                "detection_image": detection_image_b64
            }))
            
        if depth_map_b64 is not None:
            publish_message(MQTT_TOPIC_DEPTH_MAP, json.dumps({
                "timestamp": time.time(),
                "id": str(unique_id),
                "depth_map": depth_map_b64
            }))
        
        return jsonify({
            'status': 'ok',
            "timestamp": time.time(),
            "num_detections": len(detections),
            "detections": detections,
            "detection_image": detection_image_b64,
            "depth_map": depth_map_b64
        })
    except Exception as e:
        running_inference = False
        return jsonify({
            "error": f"Error processing detections: {str(e)}",
            "status": "error"
        })
    
@app.route('/')
def visualization() -> str:
    return html_text

if __name__ == "__main__":
    mqtt_thread = threading.Thread(target=start_mqtt_loop, daemon=True)
    mqtt_thread.start()
    
    with frame_lock:
        latest_frame = create_placeholder_frame()

    pipeline_thread = threading.Thread(target=run_pipeline, daemon=True)
    pipeline_thread.start()
    
    app.run(host='127.0.0.1', port=8005, debug=False, threaded=True)
    
# Note: The HTML string is assumed to be in this file as per the original code.
html_text = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Detection Visualization</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 20px;
                background-color: #f0f0f0;
            }
            .container {
                display: flex;
                flex-wrap: wrap;
                gap: 20px;
            }
            .image-container {
                background-color: white;
                padding: 10px;
                border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }
            h2 {
                margin-top: 0;
            }
            button {
                background-color: #4CAF50;
                border: none;
                color: white;
                padding: 10px 20px;
                text-align: center;
                text-decoration: none;
                display: inline-block;
                font-size: 16px;
                margin: 20px 0;
                cursor: pointer;
                border-radius: 4px;
            }
            button:hover {
                background-color: #45a049;
            }
            img {
                max-width: 100%;
                height: auto;
                border: 1px solid #ddd;
            }
            #status {
                margin: 10px 0;
                font-weight: bold;
            }
            .detection-info {
                margin-top: 10px;
                padding: 10px;
                background-color: #f9f9f9;
                border-radius: 4px;
                max-height: 200px;
                overflow-y: auto;
            }
        </style>
    </head>
    <body>
        <h1>Object Detection Visualization</h1>
        <button id="detect-btn">Run Detection</button>
        <div id="status">Ready</div>
        <div class="container">
            <div class="image-container">
                <h2>Live Video Stream</h2>
                <img id="live-stream" src="/video_stream" alt="Live video stream">
            </div>
            <div class="image-container">
                <h2>Detection Image</h2>
                <img id="detection-image" src="" alt="No detection image available">
            </div>
            <div class="image-container">
                <h2>Depth Map</h2>
                <img id="depth-image" src="" alt="No depth map available">
            </div>
        </div>
        <div class="image-container">
            <h2>Detection Results</h2>
            <div id="detection-info" class="detection-info">No detections yet</div>
        </div>

        <script>
            document.getElementById('detect-btn').addEventListener('click', async function() {
                const statusEl = document.getElementById('status');
                const detectionImageEl = document.getElementById('detection-image');
                const depthMapEl = document.getElementById('depth-image');
                const detectionInfoEl = document.getElementById('detection-info');
                
                statusEl.textContent = 'Running detection...';
                
                try {
                    const response = await fetch('/detections');
                    const data = await response.json();
                    
                    if (data.status === 'ok') {
                        statusEl.textContent = 'Detection completed successfully';
                        
                        if (data.detection_image) {
                            detectionImageEl.src = 'data:image/jpeg;base64,' + data.detection_image;
                        } else {
                            detectionImageEl.alt = 'No detection image available';
                            detectionImageEl.src = '';
                        }
                        
                        if (data.depth_map) {
                            depthMapEl.src = 'data:image/jpeg;base64,' + data.depth_map;
                        } else {
                            depthMapEl.alt = 'No depth map available';
                            depthMapEl.src = '';
                        }
                        
                        if (data.detections && data.detections.length > 0) {
                            let infoHTML = ['<h3>Found ', String(data.detections.length), ' objects:</h3>', '<ul>'];
                            data.detections.forEach((det) => {
                                let li = `<li>${det.label} (confidence: ${det.confidence.toFixed(2)}`;
                                if (det.distance !== undefined) {
                                    li += ` - Distance: ${det.distance.toFixed(2)}m`;
                                }
                                li += '</li>';
                                infoHTML.push(li);
                            });
                            infoHTML.push('</ul>');
                            detectionInfoEl.innerHTML = infoHTML.join('');
                        } else {
                            detectionInfoEl.textContent = 'No objects detected';
                        }
                    } else {
                        statusEl.textContent = 'Error: ' + (data.error || 'Unknown error');
                        detectionInfoEl.textContent = 'Detection failed: ' + (data.error || 'Unknown error');
                    }
                } catch (error) {
                    statusEl.textContent = 'Request failed: ' + error.message;
                    detectionInfoEl.textContent = 'Request failed: ' + error.message;
                }
            });
        </script>
    </body>
    </html>
    '''