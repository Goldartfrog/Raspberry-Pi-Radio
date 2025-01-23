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
from pydub import AudioSegment


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


class MusicCommandHandler:
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
        """Search for a song on YouTube using yt-dlp"""
        try:
            # Configure yt-dlp for search
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,  # Don't download, just get info
                'default_search': 'ytsearch1'  # Search and return first result
            }
            
            with YoutubeDL(ydl_opts) as ydl:
                result = ydl.extract_info(f"{query} music", download=False)
                print(result)
                if not result or 'entries' not in result or not result['entries']:
                    return None
                    
                video = result['entries'][0]
                return {
                    'title': video['title'],
                    'url': f"https://youtube.com/watch?v={video['id']}",
                    'duration': str(video.get('duration', 'unknown'))
                }
        except Exception as e:
            print(f"Error searching for song: {e}")
            return None

    def download_song(self, url, title):
        """Download and return the path to the downloaded MP3"""
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

def integrate_with_mqtt_client(audio_mqtt_client):
    """Add music playing capabilities to existing AudioMQTTClient"""
    
    # Add music handler instance
    audio_mqtt_client.music_handler = MusicCommandHandler()
    
    # Extend message handling for music commands
    original_on_message = audio_mqtt_client.on_message
    
    def new_on_message(client, userdata, msg):
        try:
            message = json.loads(msg.payload)
            
            # Handle music command messages
            if message.get("type") == "music_command":
                # Skip processing our own messages
                if message["device_id"] == audio_mqtt_client.device_id:
                    return
                    
                print(f"\nReceived music request: {message['song_title']}")
                
                # Download and play the song
                file_path = audio_mqtt_client.music_handler.download_song(
                    message['song_url'],
                    message['song_title']
                )
                
                if file_path:
                    audio_mqtt_client.audio_player.play_file(file_path)
                else:
                    print("Failed to download song")
                
            else:
                # Handle normal voice messages
                original_on_message(client, userdata, msg)
                
        except Exception as e:
            print(f"Error processing message: {e}")
    
    # Replace original message handler
    audio_mqtt_client.on_message = new_on_message
    
    def process_music_command(self):
        """Record voice command and process it"""
        print("Recording music command (5 seconds)...")
        
        # Use existing recording logic
        temp_filename = f"temp_{self.device_id}.wav"
        
        # Start recording using existing recording method
        stream = self.audio.open(format=self.FORMAT,
                               channels=self.CHANNELS,
                               rate=self.RATE,
                               input=True,
                               frames_per_buffer=self.CHUNK)
        
        frames = []
        for _ in range(0, int(self.RATE / self.CHUNK * self.RECORD_SECONDS)):
            try:
                data = stream.read(self.CHUNK, exception_on_overflow=False)
                frames.append(data)
            except IOError as e:
                print(f"Warning: {e}")
                continue
        
        print("Finished recording")
        
        stream.stop_stream()
        stream.close()
        
        # Save temporary WAV file
        with wave.open(temp_filename, 'wb') as wf:
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(self.audio.get_sample_size(self.FORMAT))
            wf.setframerate(self.RATE)
            wf.writeframes(b''.join(frames))
        
        # Process the command
        text = self.music_handler.transcribe_audio(temp_filename)
        os.remove(temp_filename)
        
        print(text)
        
        if not text:
            print("Could not understand command")
            return
            
        # Extract song request from command
        for phrase in ["play", "listen to", "put on"]:
            text = text.replace(phrase, "").strip()
        
        # Search for the song
        result = self.music_handler.search_song(text)
        if not result:
            print(f"Could not find song matching: {text}")
            return
            
        # Send music command message
        message = {
            "device_id": self.device_id,
            "timestamp": datetime.now().isoformat(),
            "type": "music_command",
            "song_title": result['title'],
            "song_url": result['url'],
            "duration": result['duration']
        }
        
        self.mqtt_client.publish("voice_messages", json.dumps(message))
        print(f"Requested song: {result['title']}")
        
        # Download and play on this device too
        file_path = self.music_handler.download_song(result['url'], result['title'])
        if file_path:
            self.audio_player.play_file(file_path)
    
    # Add new method to client
    audio_mqtt_client.process_music_command = process_music_command.__get__(audio_mqtt_client)
    
    
    
class AudioPlayer:
    def __init__(self, audio_instance):
        self.audio = audio_instance
        self.CHUNK = 8192
        
    def play_file(self, filepath):
        """Play either MP3 or WAV files"""
        file_extension = os.path.splitext(filepath)[1].lower()
        
        if file_extension == '.wav':
            self._play_wav(filepath)
        elif file_extension == '.mp3':
            self._play_mp3(filepath)
        else:
            raise ValueError(f"Unsupported file format: {file_extension}")
    
    def _play_wav(self, filepath):
        """Play a WAV file"""
        try:
            wf = wave.open(filepath, 'rb')
            stream = self.audio.open(
                format=self.audio.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True,
                frames_per_buffer=self.CHUNK
            )
            
            data = wf.readframes(self.CHUNK)
            while data:
                stream.write(data)
                data = wf.readframes(self.CHUNK)
                
            stream.stop_stream()
            stream.close()
            wf.close()
            
        except Exception as e:
            print(f"Error playing WAV file: {e}")
    
    def _play_mp3(self, filepath):
        """Convert MP3 to WAV in memory and play"""
        try:
            # Load MP3 using pydub
            audio = AudioSegment.from_mp3(filepath)
            
            # Set up audio stream
            stream = self.audio.open(
                format=self.audio.get_format_from_width(audio.sample_width),
                channels=audio.channels,
                rate=audio.frame_rate,
                output=True,
                frames_per_buffer=self.CHUNK
            )
            
            # Convert to raw audio data
            # Extract raw audio data as an array of samples
            samples = audio.raw_data
            
            # Play in chunks
            for i in range(0, len(samples), self.CHUNK * audio.sample_width):
                chunk = samples[i:i + self.CHUNK * audio.sample_width]
                stream.write(chunk)
            
            stream.stop_stream()
            stream.close()
            
        except Exception as e:
            print(f"Error playing MP3 file: {e}")

def integrate_audio_player(audio_mqtt_client):
    """Add MP3 playback capability to the MQTT client"""
    
    # Create audio player instance
    audio_mqtt_client.audio_player = AudioPlayer(audio_mqtt_client.audio)
    
    # Replace original play_message with new version
    def new_play_message(self, filepath):
        """Play either MP3 or WAV files"""
        self.audio_player.play_file(filepath)
    
    # Update the client's play_message method
    audio_mqtt_client.play_message = new_play_message.__get__(audio_mqtt_client)
    

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
            command = input("Enter command (record/music/quit): ").strip().lower()
            if command == 'record':
                client.record_message()
            if command == 'music':
                client.process_music_command()
            elif command == 'quit':
                break
    finally:
        client.cleanup()