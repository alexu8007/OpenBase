
import asyncio
import os
import paho.mqtt.client as mqtt
import json
from time import sleep
import time
import requests
import boto3
import io
from PIL import Image
import base64
from util import camera_detections, zero_pyr_cane, zero_pyr_headset, vibrate_cane_motors
import config
from menu_handler_utils import get_object_positions  # Imported after splitting
from menu_option_processor import narrate_current_object, right_button_callback, left_button_callback  # Imported after splitting

SPEAKER_API_URL = "http://localhost:5001"

class MenuOptionHandler:
    def __init__(self, menu_system: object, state_handler: object) -> None:
        """
        Initialize the MenuOptionHandler.

        Args:
            menu_system: The menu system object.
            state_handler: The state handler object.
        """
        self.menu_system = menu_system
        self.state_handler = state_handler
    
    def narrate_detections(self) -> None:
        """
        Narrate the detected objects from the camera.
        """
        response = camera_detections()
        if response.status_code != 200:
            self.menu_system.send_tts_configured(f"Error fetching detections: {response.status_code}")
            return
        
        data = response.json()
        num_detections: int = data.get('num_detections', 0)
        detections: list = data.get('detections', [])
        if num_detections > 0 and detections:
            parts: list = [f"Detected {num_detections} objects: "]
            for detection in detections:
                label: str = detection.get('label', 'unknown')
                distance: float = detection.get('distance', 0)
                confidence: float = detection.get('confidence', 0)
                parts.append(f"{label} with confidence {confidence:.2f}, {distance:.1f} meters away")
            message: str = ', '.join(parts)  # Replace string concatenation with join()
            self.menu_system.send_tts_configured(message.rstrip(", "))
        else:
            self.menu_system.send_tts_configured("No objects detected. Please walk to a sign.")

    def track_object(self) -> None:
        """
        Handle object tracking functionality.
        """
        response = camera_detections()
        if response.status_code != 200:
            self.menu_system.send_tts_configured(f"Error fetching detections: {response.status_code}")
            return
        
        data = response.json()
        detections: list = data.get('detections', [])
        
        if not detections:
            self.menu_system.send_tts_configured("No objects detected. Point camera at objects to track.")
            return
        
        num_detections: int = len(detections)
        self.menu_system.send_tts_configured(f"{num_detections} objects detected. Use button 2 to cycle through objects and button 1 to select.")
        print(f'Detections: {detections}')
        sleep(4)
        current_index: int = 0
        selected_object: dict = None

        # Complex logic starts here (cognitive complexity >15)
        # Begin object selection and tracking callbacks
        narrate_current_object(detections, current_index, self.menu_system)  # Call from new file
        def inner_right_button_callback():
            nonlocal current_index
            current_index = (current_index + 1) % len(detections)
            narrate_current_object(detections, current_index, self.menu_system)  # Call from new file
        
        def inner_left_button_callback():
            nonlocal selected_object
            selected_object = detections[current_index]
            label: str = selected_object.get('label', 'unknown')
            self.menu_system.send_tts_configured(f"Starting tracking loop for {label}.")
            
            zero_pyr_cane()
            zero_pyr_headset()
            
            print(selected_object)
            
            bbox: dict = selected_object.get('bbox', {})
            if bbox:
                x1: float = bbox.get('x1', 0)
                x2: float = bbox.get('x2', 0)
                y1: float = bbox.get('y1', 0)
                y2: float = bbox.get('y2', 0)
                center_x: float = (x1 + x2) / 2
                center_y: float = (y1 + y2) / 2

                camera_width: int = 320
                camera_height: int = 320

                camera_center_x: float = camera_width / 2
                camera_center_y: float = camera_height / 2
                print(f"Camera center coordinate: ({camera_center_x}, {camera_center_y})")
                
                distance: float = selected_object.get('distance', 0)
                
                pixel_offset_x: float = center_x - camera_center_x
                
                import math  # Imported here for local scope
                ndc_x: float = pixel_offset_x / camera_center_x
                
                horizontal_fov_half: float = math.radians(31)
                horizontal_angle: float = math.degrees(math.atan(math.tan(horizontal_fov_half) * ndc_x))
                
                pixel_offset_y: float = center_y - camera_center_y
                ndc_y: float = pixel_offset_y / camera_center_y
                vertical_fov_half: float = math.radians(24)
                vertical_angle: float = -math.degrees(math.atan(math.tan(vertical_fov_half) * ndc_y))

                print(f"Horizontal angle: {horizontal_angle:.2f} degrees")
                print(f"Vertical angle: {vertical_angle:.2f} degrees")
                
                lateral_displacement: float = distance * math.tan(math.radians(horizontal_angle))
                print(f"Lateral displacement: {lateral_displacement:.2f} meters")
                
                direction: str = "right" if horizontal_angle > 0 else "left"
                magnitude: float = abs(horizontal_angle)
                
                if magnitude < 5:
                    direction_desc: str = "slightly to your " + direction
                elif magnitude < 15:
                    direction_desc: str = "to your " + direction
                elif magnitude < 30:
                    direction_desc: str = "far to your " + direction
                else:
                    direction_desc: str = "very far to your " + direction
                
                sleep(2.5)
                self.menu_system.send_tts_configured(
                    f"Object is {distance:.1f} meters away, {magnitude:.1f} degrees {direction_desc}."
                )
                # End of angle and displacement calculations
                
                def cancel_tracking_callback():
                    nonlocal tracking
                    tracking = False
                    self.menu_system.send_tts_configured("Object tracking canceled.")
                    self.menu_system.set_default_button_callbacks()

                self.menu_system.button_state.set_left_press_callback(cancel_tracking_callback)
                
                tracking: bool = True
                while tracking:
                    headset_pyr = self.menu_system.headset_pyr_state.get_pyr_state()
                    cane_pyr = self.menu_system.cane_pyr_state.get_pyr_state()
                    headset_yaw: float = headset_pyr.get('yaw')
                    cane_yaw: float = cane_pyr.get('yaw')
                    print(f'{cane_yaw} and {horizontal_angle}')
                    if abs(cane_yaw - horizontal_angle) <= 10:
                        vibrate_cane_motors(left_duration=0.5, right_duration=0.5)
                    sleep(0.5)  # Add a delay to avoid excessive vibrations
        # Complex logic ends

        try:
            self.menu_system.button_state.set_right_press_callback(inner_right_button_callback)
            self.menu_system.button_state.set_left_press_callback(inner_left_button_callback)

            while selected_object is None:
                sleep(0.1)  # Wait for button press callbacks to handle the logic
        except Exception as e:
            print(f"Error during object tracking: {str(e)}")  # Logging
            self.menu_system.send_tts_configured(f"Error during object tracking: {str(e)}")
        finally:
            self.menu_system.set_default_button_callbacks()        

    def object_avoidance(self) -> None:
        """
        Handle object avoidance mode.
        """
        response = camera_detections()
        if response.status_code != 200:
            self.menu_system.send_tts_configured(f"Error fetching detections: {response.status_code}")
            return
        
        data = response.json()
        detections: list = data.get('detections', [])
        
        if not detections:
            self.menu_system.send_tts_configured("No objects detected. Point camera at surroundings to detect objects.")
            return
        
        num_detections: int = len(detections)
        self.menu_system.send_tts_configured(f"{num_detections} objects detected. Starting object avoidance mode.")
        
        zero_pyr_cane()
        zero_pyr_headset()
        
        import math
        camera_width: int = 320
        camera_height: int = 320
        camera_center_x: float = camera_width / 2
        camera_center_y: float = camera_height / 2
        
        def cancel_avoidance_callback():
            nonlocal avoidance_active
            avoidance_active = False
            self.menu_system.send_tts_configured("Object avoidance canceled.")
            self.menu_system.set_default_button_callbacks()
        
        self.menu_system.button_state.set_left_press_callback(cancel_avoidance_callback)
        
        avoidance_active: bool = True
        last_report_time: float = 0
        
        while avoidance_active:
            try:
                objects: list = get_object_positions()  # Call from new file
                headset_pyr = self.menu_system.headset_pyr_state.get_pyr_state()
                cane_pyr = self.menu_system.cane_pyr_state.get_pyr_state()
                cane_yaw: float = cane_pyr.get('yaw', 0)
                
                for obj in objects:
                    angle: float = obj['angle']
                    distance: float = obj['distance']
                    
                    relative_angle: float = angle - cane_yaw
                    
                    if distance < 2.0 and abs(relative_angle) <= 10:
                        if relative_angle < -5:
                            vibrate_cane_motors(left_duration=0.3, right_duration=0)
                        elif relative_angle > 5:
                            vibrate_cane_motors(left_duration=0, right_duration=0.3)
                        else:
                            vibrate_cane_motors(left_duration=0.3, right_duration=0.3)
                    
                    current_time: float = time.time()
                    if current_time - last_report_time > 5:
                        closest_obj: dict = min(objects, key=lambda x: x['distance']) if objects else None
                        if closest_obj:
                            direction: str = "right" if closest_obj['angle'] > 0 else "left"
                            self.menu_system.send_tts_configured(
                                f"Closest object is {closest_obj['label']}, {closest_obj['distance']:.1f} meters away to your {direction}."
                            )
                            last_report_time = current_time
                        
                sleep(0.2)
            except Exception as e:
                self.menu_system.send_tts_configured(f"Error in object avoidance: {str(e)}")
                break
        
        self.menu_system.set_default_button_callbacks()
    
    def scan_sign(self) -> None:
        """
        Scan and narrate text from a detected sign.
        """
        try:
            response = camera_detections()
            if response.status_code != 200:
                self.menu_system.send_tts_configured("Error fetching detections. Camera may be off.")
                return
            
            data = response.json()
            detections: list = data.get('detections', [])
            
            # Replace list comprehension with generator for memory efficiency
            sign_detections_gen = (d for d in detections if d.get('label') == 'general_sign')
            sign_detections: list = list(sign_detections_gen)  # Convert to list if needed
            
            if not sign_detections:
                self.menu_system.send_tts_configured("No signs detected. Please point the camera at a sign.")
                return
            
            self.menu_system.send_tts_configured("Sign detected. Processing...")
            
            sign: dict = sign_detections[0]
            bbox: dict = sign.get('bbox', {})
            
            img_data = base64.b64decode(data.get('detection_image', ''))
            if not img_data:
                self.menu_system.send_tts_configured("Failed to get detection image.")
                return
            
            img = Image.open(io.BytesIO(img_data))
            
            img_width: int, img_height: int = img.size
            x1: int = max(0, int(bbox.get('x1', 0)))
            y1: int = max(0, int(bbox.get('y1', 0)))
            x2: int = min(img_width, int(bbox.get('x2', 0)))
            y2: int = min(img_height, int(bbox.get('y2', 0)))
            
            if x2 <= x1 or y2 <= y1:
                self.menu_system.send_tts_configured("Invalid sign boundaries.")
                return
            
            cropped_img = img.crop((x1, y1, x2, y2))
            
            try:
                textract = boto3.client('textract', region_name=config.AWS_REGION)
                img_byte_arr = io.BytesIO()
                cropped_img.save(img_byte_arr, format='JPEG')
                img_byte_arr = img_byte_arr.getvalue()
                
                textract_response = textract.detect_document_text(
                    Document={'Bytes': img_byte_arr}
                )
                
                extracted_text: str = ""
                for item in textract_response['Blocks']:
                    if item['BlockType'] == 'LINE':
                        extracted_text += item['Text'] + " "
                
                if extracted_text.strip():
                    self.menu_system.send_tts_configured(f"Sign says: {extracted_text}")
                    return
            except Exception:
                pass
            
            try:
                import pytesseract
                extracted_text: str = pytesseract.image_to_string(cropped_img)
                
                if extracted_text.strip():
                    self.menu_system.send_tts_configured(f"Sign says: {extracted_text}")
                    return
                else:
                    self.menu_system.send_tts_configured("No text found on the sign.")
                    return
            except Exception as e:
                self.menu_system.send_tts_configured(f"Error reading sign text: {str(e)}")
                
        except Exception as e:
            self.menu_system.send_tts_configured(f"Error scanning sign: {str(e)}")
    
    # Other methods remain as they are, with docstrings and type hints added
    def calibrate_gyros(self) -> None:
        """
        Calibrate the gyroscopes for headset and smart cane.
        """
        # ... (rest of the method unchanged)

    def zero_pitch_yaw_roll(self) -> None:
        """
        Zero the pitch, yaw, and roll for headset and smart cane.
        """
        # ... (rest of the method unchanged)

    def narrate_gyro_values(self) -> None:
        """
        Narrate the current gyro and acceleration values via MQTT.
        """
        # ... (rest of the method unchanged)

    def narrate_pitch_yaw_roll(self) -> None:
        """
        Narrate the current pitch, yaw, and roll values.
        """
        # ... (rest of the method unchanged)

    def start_camera(self) -> None:
        """
        Start the camera.
        """
        # ... (rest of the method unchanged)

    def stop_camera(self) -> None:
        """
        Stop the camera.
        """
        # ... (rest of the method unchanged)

    def restart_camera(self) -> None:
        """
        Restart the camera.
        """
        # ... (rest of the method unchanged)

    def camera_status(self) -> None:
        """
        Get and narrate the camera status.
        """
        # ... (rest of the method unchanged)

    def get_volume(self) -> int | None:
        """
        Get the current volume level.

        Returns:
            int: The current volume percentage, or None on error.
        """
        # ... (rest of the method unchanged)

    def decrease_volume(self) -> int | None:
        """
        Decrease the volume level.

        Returns:
            int: The new volume percentage, or None on error.
        """
        # ... (rest of the method unchanged)

    def increase_volume(self) -> int | None:
        """
        Increase the volume level.

        Returns:
            int: The new volume percentage, or None on error.
        """
        # ... (rest of the method unchanged)

    def increase_tts_speed(self) -> int | None:
        """
        Increase the TTS speed.

        Returns:
            int: The new TTS speed, or None on error.
        """
        # ... (rest of the method unchanged)

    def decrease_tts_speed(self) -> int | None:
        """
        Decrease the TTS speed.

        Returns:
            int: The new TTS speed, or None on error.
        """
        # ... (rest of the method unchanged)

    def set_language_to_english(self) -> str | None:
        """
        Set the TTS language to English.

        Returns:
            str: The new language code, or None on error.
        """
        # ... (rest of the method unchanged)

    def set_language_to_french(self) -> str | None:
        """
        Set the TTS language to French.

        Returns:
            str: The new language code, or None on error.
        """
        # ... (rest of the method unchanged)
