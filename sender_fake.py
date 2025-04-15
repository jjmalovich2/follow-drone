import random
import time
from socket import socket, AF_INET, SOCK_STREAM
from datetime import datetime

RECEIVER_IP = "192.168.241.1"
RECEIVER_PORT = 40739


def generate_fake_coords():
    """Generate [lat, lon, alt, timestamp]"""
    return [
        round(random.uniform(-90, 90), 6),  # lat
        round(random.uniform(-180, 180), 6),  # lon
        10,                                 # constant altitude
        datetime.now().timestamp()          # current timestamp
    ]


def send_data():
    try:
        with socket(AF_INET, SOCK_STREAM) as s:
            s.connect((RECEIVER_IP, RECEIVER_PORT))
            while True:
                payload = str(generate_fake_coords())
                s.sendall(payload.encode())
                print(f"Sent: {payload}")
                time.sleep(1)
    except Exception as e:
        print(f"Network Error: {e}")


if __name__ == "__main__":
    send_data()
