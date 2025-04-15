# Follow-Drone

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Last Commit](https://img.shields.io/github/last-commit/jjmalovich2/follow-drone)](https://github.com/jjmalovich2/follow-drone/commits/main)
[![Repo Size](https://img.shields.io/github/repo-size/jjmalovich2/follow-drone)](https://github.com/jjmalovich2/follow-drone)
[![Issues](https://img.shields.io/github/issues/jjmalovich2/follow-drone)](https://github.com/jjmalovich2/follow-drone/issues)

## Overview

This project implements a Python-based "Follow Me" drone system. It facilitates GPS-based tracking by transmitting location data from a sender (e.g., a smartphone) to a receiver (the drone), enabling the drone to autonomously follow the sender. The system is designed to be lightweight and adaptable for integration with various drone platforms.

## Features

- Real-time GPS data transmission from sender to receiver  
- Modular code structure for easy integration and testing  
- Simulated sender module (`sender_fake.py`) for development without GPS hardware  
- Efficient data decoding and handling on the receiver side  

## File Structure

- `sender.py`: Captures and sends GPS coordinates to the receiver  
- `sender_fake.py`: Simulates GPS data transmission for testing purposes  
- `receiver.py`: Receives GPS data and processes it for drone navigation  
- `decoder.py`: Decodes incoming GPS data into usable coordinates  

## Getting Started

### Prerequisites

- Python 3.8 or higher  
- Required Python packages (install via `requirements.txt` if available)  

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/jjmalovich2/follow-drone.git
   cd follow-drone
   ```

2. Install requirements:
  ```bash
  pip install -r requirements.txt
  ```

## Usage
1. Start the receiver module on the drone's onboard RaspberryPi:
   ```bash
   python receiver.py
   ```

2. On the sender RaspberryPi run:
   ```bash
   python sender.py
   ```
   For testing without GPS hardware, use the simulated sender:
   ```bash
   python sender_fake.py
   ```
