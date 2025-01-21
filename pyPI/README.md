# Raspberry Pi Radio - Voice Message Network

A distributed network of Raspberry Pi-based communication devices that enable asynchronous voice message sharing between friends' homes. Each node consists of a headless Raspberry Pi connected to USB speakers and a USB microphone.

## Prerequisites
```bash
# Update package list
sudo apt update

# Install required system packages
sudo apt install python3-full python3-venv python3.11-dev portaudio19-dev git

# Clone the project repository
git clone https://github.com/Goldartfrog/Raspberry-Pi-Radio.git
cd Raspberry-Pi-Radio/pyPI

# Create and set up Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python packages
pip install pyaudio paho-mqtt
```

## Installation

### Broker Pi Setup (Primary Pi)
```bash
# Install Mosquitto and clients
sudo apt install mosquitto mosquitto-clients

# Enable autostart
sudo systemctl enable mosquitto

# Configure network access
sudo nano /etc/mosquitto/conf.d/default.conf
# Add:
# listener 1883
# allow_anonymous true

# Restart service
sudo systemctl restart mosquitto
```

### Client Pi Setup (All Other Pis)
```bash
# Install Mosquitto clients only
sudo apt install mosquitto-clients
```

## Security Setup
Create a password file on the broker Pi:
```bash
sudo mosquitto_passwd -c /etc/mosquitto/passwd_file your_username
```

Update Mosquitto config (`/etc/mosquitto/conf.d/default.conf`):
```
listener 1883
allow_anonymous false
password_file /etc/mosquitto/passwd_file
```

Restart Mosquitto:
```bash
sudo systemctl restart mosquitto
```

## Usage
1. Activate the virtual environment:
```bash
cd Raspberry-Pi-Radio/pyPI
source venv/bin/activate
```

2. Run the script:
```bash
python mqtt_audio.py --broker YOUR_BROKER_IP --username YOUR_USERNAME --password YOUR_PASSWORD --device-id pi1
```

Replace:
- YOUR_BROKER_IP with the IP address of your broker Pi
- YOUR_USERNAME with your Mosquitto username
- YOUR_PASSWORD with your Mosquitto password
- pi1 with a unique identifier for each Pi (e.g., pi1, pi2, pi3)

3. Available commands:
- Type 'record' to record a 5-second message
- Type 'quit' to exit the program

## Network Setup
- The broker Pi needs port 1883 forwarded on its network
- Other Pis don't require port forwarding
- All Pis must have internet access

## Hardware Requirements
- Raspberry Pi (any model)
- USB microphone
- USB speakers or audio output device