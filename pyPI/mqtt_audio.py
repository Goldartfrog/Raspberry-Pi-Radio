import pyaudio
import wave
import paho.mqtt.client as mqtt
import time
import os
from datetime import datetime
import json
import speech_recognition as sr
from yt_dlp import YoutubeDL
import requests
from youtubesearchpython import VideosSearch


class AudioMQTTClient:
    def __init__(self, broker_host, username, password, device_id):
        # Audio configuration - will be set after device selection
        self.CHUNK = 8192  # Increased buffer size for smoother playback
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
        
        # Common sample rates to try, prioritizing higher quality
        COMMON_RATES = [48000, 44100, 32000, 22050, 16000, 8000]  # Prioritize higher rates
        
        for i in range(self.audio.get_device_count()):
            dev_info = self.audio.get_device_info_by_index(i)
            if dev_info['maxInputChannels'] > 0:  # if it's an input device
                print(f"Device {i}: {dev_info['name']}")
                print(f"Default sample rate: {int(dev_info['defaultSampleRate'])} Hz")
                
                # Try device's default sample rate first
                default_rate = int(dev_info['defaultSampleRate'])
                if default_rate not in COMMON_RATES:
                    COMMON_RATES.insert(0, default_rate)
                
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
        os.remove(temp_filename)

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
            
            # Open a stream for playback with larger buffer
            stream = self.audio.open(format=self.audio.get_format_from_width(wf.getsampwidth()),
                                   channels=wf.getnchannels(),
                                   rate=wf.getframerate(),
                                   output=True,
                                   frames_per_buffer=self.CHUNK,
                                   output_device_index=None)  # Use default output
            
            # Read and play the audio data in chunks
            data = wf.readframes(self.CHUNK)
            while data:
                stream.write(data)
                data = wf.readframes(self.CHUNK)
            
            # Small delay to prevent cutting off end of audio
            time.sleep(0.5)
            
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


class MusicPlayer:
    def __init__(self, cache_dir="music_cache"):
        self.recognizer = sr.Recognizer()
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        
        # Configure yt-dlp options
        self.ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': f'{cache_dir}/%(title)s.%(ext)s',
            'quiet': True
        }

    def transcribe_audio(self, wav_file):
        """Convert speech to text using the specified WAV file"""
        with sr.AudioFile(wav_file) as source:
            audio = self.recognizer.record(source)
            try:
                text = self.recognizer.recognize_google(audio)
                return text.lower()
            except sr.UnknownValueError:
                print("Could not understand audio")
                return None
            except sr.RequestError as e:
                print(f"Could not request results; {e}")
                return None

    def search_song(self, query):
        """Search for a song on YouTube"""
        try:
            # Add "music" to the query to prioritize music results
            search = VideosSearch(f"{query} music", limit=1)
            results = search.result()
            
            if not results['result']:
                return None
                
            return {
                'title': results['result'][0]['title'],
                'url': results['result'][0]['link'],
                'duration': results['result'][0]['duration']
            }
        except Exception as e:
            print(f"Error searching for song: {e}")
            return None

    def download_song(self, url, title):
        """Download a song from YouTube and return the file path"""
        cache_path = f"{self.cache_dir}/{title}.mp3"
        
        # Check if song is already in cache
        if os.path.exists(cache_path):
            print(f"Found {title} in cache")
            return cache_path
            
        try:
            with YoutubeDL(self.ydl_opts) as ydl:
                ydl.download([url])
            return cache_path
        except Exception as e:
            print(f"Error downloading song: {e}")
            return None

    def process_music_command(self, wav_file):
        """Process a voice command to play music"""
        # First, transcribe the audio
        text = self.transcribe_audio(wav_file)
        if not text:
            return None, "Could not understand audio command"
            
        # Check if the command is asking to play music
        if not any(phrase in text for phrase in ["play", "listen to", "put on"]):
            return None, "Not a valid music command"
            
        # Extract the song query by removing command words
        for phrase in ["play", "listen to", "put on"]:
            text = text.replace(phrase, "").strip()
            
        # Search for the song
        result = self.search_song(text)
        if not result:
            return None, f"Could not find song matching: {text}"
            
        # Download the song
        file_path = self.download_song(result['url'], result['title'])
        if not file_path:
            return None, f"Failed to download: {result['title']}"
            
        return {
            'file_path': file_path,
            'title': result['title'],
            'duration': result['duration']
        }, None

def integrate_with_mqtt_client(audio_mqtt_client):
    """Add music playing capabilities to existing AudioMQTTClient"""
    
    # Add music player instance
    audio_mqtt_client.music_player = MusicPlayer()
    
    # Extend message format to include music commands
    original_on_message = audio_mqtt_client.on_message
    
    def new_on_message(client, userdata, msg):
        try:
            message = json.loads(msg.payload)
            
            # Check if this is a music command
            if message.get("type") == "music_command":
                # Process as music command
                temp_wav = f"temp_command_{message['device_id']}.wav"
                
                # Save audio command to temporary WAV
                audio_data = bytes.fromhex(message["audio_data"])
                with wave.open(temp_wav, 'wb') as wf:
                    wf.setnchannels(audio_mqtt_client.CHANNELS)
                    wf.setsampwidth(audio_mqtt_client.audio.get_sample_size(audio_mqtt_client.FORMAT))
                    wf.setframerate(audio_mqtt_client.RATE)
                    wf.writeframes(audio_data)
                
                # Process music command
                result, error = audio_mqtt_client.music_player.process_music_command(temp_wav)
                
                # Clean up temp file
                os.remove(temp_wav)
                
                if error:
                    print(f"Music command error: {error}")
                    return
                    
                # Play the music file
                audio_mqtt_client.play_message(result['file_path'])
                
            else:
                # Handle normal voice message
                original_on_message(client, userdata, msg)
                
        except Exception as e:
            print(f"Error processing message: {e}")
    
    # Replace original message handler
    audio_mqtt_client.on_message = new_on_message
    
    # Add method to send music commands
    def send_music_command(self):
        """Record and send a music command"""
        print("Recording music command...")
        
        # Use existing recording logic but mark as music command
        temp_filename = f"temp_{self.device_id}.wav"
        
        # Record audio using existing method
        self.record_message()
        
        # Read the temporary file and send as music command
        with open(temp_filename, 'rb') as f:
            audio_data = f.read()
            message = {
                "device_id": self.device_id,
                "timestamp": datetime.now().isoformat(),
                "type": "music_command",
                "audio_data": audio_data.hex()
            }
            self.mqtt_client.publish("voice_messages", json.dumps(message))
        
        print("Music command sent")
    
    # Add new method to client
    audio_mqtt_client.send_music_command = send_music_command.__get__(audio_mqtt_client)




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
    integrate_with_mqtt_client(client)
    client.connect()
    
    try:
        while True:
            command = input("Enter command (record/quit): ").strip().lower()
            if command == 'record':
                client.record_message()
            if command == 'music':
                client.send_music_command()
            elif command == 'quit':
                break
    finally:
        client.cleanup()