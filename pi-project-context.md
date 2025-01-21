# Raspberry Pi Radio Project Context

## Project Overview
A distributed network of Raspberry Pi-based communication devices that enable asynchronous voice message sharing between friends' homes. Each node consists of a headless Raspberry Pi connected to USB speakers and a USB microphone.

## Core Features
- Command-line interface for basic operations
- Automatic message distribution to all devices
- Store-and-forward message delivery
- Support for 3-9 network nodes
- Audio recording and playback
- MQTT-based message distribution

## Technical Implementation

### Hardware Components (Per Node)
- Raspberry Pi (headless mode)
- USB speakers
- USB microphone

### Software Architecture
1. Message Broker (Primary Pi)
   - Mosquitto MQTT broker
   - Handles message distribution
   - Manages device authentication
   - Port 1883 exposed for network access

2. Client Nodes
   - Python-based audio handling
   - MQTT client for message distribution
   - Local message storage
   - Automatic message playback

### Audio Configuration
- Chunk size: 8192 (for smooth playback)
- Format: 16-bit PCM
- Channels: Mono
- Sample rate: Auto-detected based on device capability
- Prioritized sample rates: [48000, 44100, 32000, 22050, 16000, 8000]

### Network Architecture
- Central broker with port forwarding
- Authenticated MQTT connections
- Store-and-forward message delivery
- All-to-all message distribution

### Security Implementation
- MQTT username/password authentication
- No anonymous connections allowed
- Network-level security through port forwarding
- Message validation and sanitization

## Current Implementation Details

### Working Features
1. Audio System
   - Successfully recording from USB microphones
   - Automatic playback on message receipt
   - Dynamic sample rate detection and configuration
   - Error handling for buffer overflows
   - Messages stored as WAV files

2. MQTT Implementation
   - Working broker setup with authentication
   - Successful message passing between 3+ devices
   - Messages broadcasted to all connected devices
   - Working across different networks via port forwarding
   - Store-and-forward functionality operational

3. Message Format
   - Messages packaged as JSON with:
     ```javascript
     {
         "device_id": string,  // Unique identifier for sender
         "timestamp": string,  // ISO format timestamp
         "audio_data": string  // Hex-encoded WAV data
     }
     ```
   - Local storage in received_messages directory
   - Automatic file naming with timestamp and sender ID

### Technical Specifications

1. Audio Configuration Details
   - PyAudio configuration:
     ```python
     FORMAT = pyaudio.paInt16
     CHANNELS = 1
     CHUNK = 8192  # Buffer size for smooth playback
     RATE = auto-detected  # Typically 44100 or 48000 Hz
     ```
   - Recording buffer: Uses exception_on_overflow=False for stability
   - Playback includes 0.5s end-padding to prevent cutoff

2. MQTT Details
   - Topic structure: "voice_messages" for audio data
   - QoS Level: 0 (fire and forget)
   - Clean Session: True
   - Keep Alive: 60 seconds
   - Port: 1883 (standard MQTT)
   - TLS: Not currently implemented

3. File Management
   - Temporary files used during recording (temp_{device_id}.wav)
   - Received messages stored as: msg_{sender_id}_{timestamp}.wav
   - No automatic cleanup of stored messages
   - WAV format with PCM encoding

4. Resource Usage
   - Memory: ~50MB per Python process
   - Storage: ~10MB per minute of audio
   - Network: ~80KB/s during message transmission
   - CPU: <10% during idle, ~30% during record/playback

### Known Limitations
1. Audio
   - Fixed 5-second recording duration
   - No volume control
   - No visual audio level indication
   - Some devices may have sample rate compatibility issues

2. Networking
   - No automatic broker discovery
   - No TLS encryption
   - No automatic reconnection
   - No handling of network transitions

3. User Interface
   - Command-line only
   - No message management commands
   - No status indicators
   - No way to cancel recording

### Implementation Notes
1. Device Discovery
   ```python
   def configure_audio_device(self):
       # Attempts to find and configure input device
       # Tests multiple sample rates
       # Returns first working configuration
   ```

2. Message Processing Pipeline
   ```python
   Recording -> WAV File -> Hex Encoding -> JSON -> MQTT -> 
   JSON -> Hex Decoding -> WAV File -> Playback
   ```

3. Critical Code Sections
   - Audio device initialization
   - MQTT connection handling
   - Message encoding/decoding
   - File I/O operations

### Required Libraries and Versions
- pyaudio==0.2.14
- paho-mqtt==1.6.1
- Python 3.11+
- portaudio19-dev system package
- mosquitto 2.0+

## Future Considerations
1. Physical Interface
   - Buttons for recording
   - LED indicators
   - Status display

2. Enhanced Features
   - Message length configuration
   - Stored message management
   - Online/offline status tracking
   - Network disconnection recovery

3. Quality Improvements
   - Audio quality optimization
   - Network efficiency
   - Error handling
   - User feedback

## Testing Information
- Audio quality: Currently working with some room for improvement
- Network reliability: Tested on same network (need to test different networks)
- Message delivery: Working with store-and-forward
- Security: Basic authentication implemented
