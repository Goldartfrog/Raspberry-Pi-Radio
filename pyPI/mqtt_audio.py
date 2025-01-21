import pyaudio
import wave
import paho.mqtt.client as mqtt
import time
import os
from datetime import datetime
import json

class AudioMQTTClient:
    def __init__(self, broker_host, username, password, device_id):
        # Audio configuration - will be set after device selection
        self.CHUNK = 4096
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = None  # Will be set based on device capabilities
        self.RECORD_SECONDS = 5  # Default recording time
        
        # Initialize PyAudio
        self.audio = pyaudio.PyAudio()
        
        # Find and configure input device
        self.input_device_index = self.configure_audio_device()
        if self.input_device_index is None:
            raise Exception("No suitable input device found")
        
        # MQTT configuration
        self.broker_host = broker_host
        self.device_id = device_id
        self.mqtt_client = mqtt.Client(client_id=f"audio_client_{device_id}")
        self.mqtt_client.username_pw_set(username, password)
        
        # Set up MQTT callbacks
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        
        # Create messages directory if it doesn't exist
        self.messages_dir = "received_messages"
        os.makedirs(self.messages_dir, exist_ok=True)

    def configure_audio_device(self):
        """Find and configure a suitable input device"""
        print("\nAvailable Input Devices:")
        input_device_index = None
        
        # Common sample rates to try
        COMMON_RATES = [44100, 48000, 32000, 22050, 16000, 8000]
        
        for i in range(self.audio.get_device_count()):
            dev_info = self.audio.get_device_info_by_index(i)
            if dev_info['maxInputChannels'] > 0:  # if it's an input device
                print(f"Device {i}: {dev_info['name']}")
                
                # Try to find a working sample rate
                for rate in COMMON_RATES:
                    try:
                        supported = self.audio.is_format_supported(
                            rate,
                            input_device=i,
                            input_channels=self.CHANNELS,
                            input_format=self.FORMAT
                        )
                        print(f"  Sample rate {rate} Hz is supported")
                        if input_device_index is None:  # Take the first working device
                            input_device_index = i
                            self.RATE = rate
                            print(f"Selected device {i} with sample rate {rate} Hz")
                            break
                    except Exception as e:
                        print(f"  Sample rate {rate} Hz is not supported")
                        continue
                
        return input_device_index

    def connect(self):
        """Connect to MQTT broker"""
        self.mqtt_client.connect(self.broker_host, 1883, 60)
        self.mqtt_client.loop_start()

    def on_connect(self, client, userdata, flags, rc):
        """Callback for when the client connects to the broker"""
        print(f"Connected with result code {rc}")
        # Subscribe to the voice messages topic
        self.mqtt_client.subscribe("voice_messages")

    def record_message(self, duration=None):
        """Record audio message"""
        if duration:
            self.RECORD_SECONDS = duration
            
        print(f"Recording for {self.RECORD_SECONDS} seconds...")
        
        # Open recording stream
        # List available input devices
        print("\nAvailable Input Devices:")
        for i in range(self.audio.get_device_count()):
            dev_info = self.audio.get_device_info_by_index(i)
            if dev_info['maxInputChannels'] > 0:  # if it's an input device
                print(f"Device {i}: {dev_info['name']}")
        
        # Open recording stream with error handling
        try:
            stream = self.audio.open(format=self.FORMAT,
                                   channels=self.CHANNELS,
                                   rate=self.RATE,
                                   input=True,
                                   frames_per_buffer=self.CHUNK,
                                   input_device_index=None)  # Use default input device
        except Exception as e:
            print(f"Error opening audio stream: {e}")
            return
        
        frames = []
        for i in range(0, int(self.RATE / self.CHUNK * self.RECORD_SECONDS)):
            try:
                data = stream.read(self.CHUNK, exception_on_overflow=False)
                frames.append(data)
            except IOError as e:
                print(f"Warning: {e}")
                continue  # Skip this chunk and continue
        
        print("Finished recording")
        
        # Stop and close the stream
        stream.stop_stream()
        stream.close()
        
        # Create temporary WAV file
        temp_filename = f"temp_{self.device_id}.wav"
        wf = wave.open(temp_filename, 'wb')
        wf.setnchannels(self.CHANNELS)
        wf.setsampwidth(self.audio.get_sample_size(self.FORMAT))
        wf.setframerate(self.RATE)
        wf.writeframes(b''.join(frames))
        wf.close()
        
        # Read the file and send it
        with open(temp_filename, 'rb') as f:
            audio_data = f.read()
            self.send_message(audio_data)
        
        # Clean up temporary file
        # os.remove(temp_filename)

    def send_message(self, audio_data):
        """Send audio message via MQTT"""
        # Create message packet with metadata
        message = {
            "device_id": self.device_id,
            "timestamp": datetime.now().isoformat(),
            "audio_data": audio_data.hex()  # Convert bytes to hex string
        }
        
        # Publish message
        self.mqtt_client.publish("voice_messages", json.dumps(message))
        print("Message sent")

    def on_message(self, client, userdata, msg):
        """Handle received messages"""
        try:
            # Parse message
            message = json.loads(msg.payload)
            
            # Skip messages from self
            if message["device_id"] == self.device_id:
                return
                
            # Convert hex string back to bytes
            audio_data = bytes.fromhex(message["audio_data"])
            
            # Save message to file
            timestamp = datetime.fromisoformat(message["timestamp"]).strftime("%Y%m%d_%H%M%S")
            filename = f"{self.messages_dir}/msg_{message['device_id']}_{timestamp}.wav"
            
            with wave.open(filename, 'wb') as wf:
                wf.setnchannels(self.CHANNELS)
                wf.setsampwidth(self.audio.get_sample_size(self.FORMAT))
                wf.setframerate(self.RATE)
                wf.writeframes(audio_data)
            
            print(f"Received message from {message['device_id']}, saved as {filename}")
            self.play_message(filename)
            
        except Exception as e:
            print(f"Error processing message: {e}")

    def play_message(self, filename):
        """Play an audio message"""
        try:
            # Open the audio file
            wf = wave.open(filename, 'rb')
            
            # Open a stream for playback
            stream = self.audio.open(format=self.audio.get_format_from_width(wf.getsampwidth()),
                                   channels=wf.getnchannels(),
                                   rate=wf.getframerate(),
                                   output=True)
            
            # Read and play the audio data
            data = wf.readframes(self.CHUNK)
            while data:
                stream.write(data)
                data = wf.readframes(self.CHUNK)
            
            # Clean up
            stream.stop_stream()
            stream.close()
            wf.close()
            
        except Exception as e:
            print(f"Error playing message: {e}")

    def cleanup(self):
        """Clean up resources"""
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
        self.audio.terminate()

# Example usage
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Audio MQTT Client')
    parser.add_argument('--broker', required=True, help='MQTT broker hostname/IP')
    parser.add_argument('--username', required=True, help='MQTT username')
    parser.add_argument('--password', required=True, help='MQTT password')
    parser.add_argument('--device-id', required=True, help='Unique device identifier')
    
    args = parser.parse_args()
    
    client = AudioMQTTClient(args.broker, args.username, args.password, args.device_id)
    client.connect()
    
    try:
        while True:
            command = input("Enter command (record/quit): ").strip().lower()
            if command == 'record':
                client.record_message()
            elif command == 'quit':
                break
    finally:
        client.cleanup()
