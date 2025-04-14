import random
import time
from socket import socket, AF_INET, SOCK_STREAM

# Receiver IP and Port
RECEIVER_IP = "172.16.18.74"  # Replace with receiver's IP
RECEIVER_PORT = 8080

def generate_fake_gps():
    """Generate fake NMEA GPGGA sentence."""
    lat = round(random.uniform(-90, 90), 6)
    lon = round(random.uniform(-180, 180), 6)
    return f"$GPGGA,{int(time.time()) % 86400},{abs(lat):09.6f},{'N' if lat >=0 else 'S'},{abs(lon):010.6f},{'E' if lon >=0 else 'W'},1,08,1.2,100.0,M,50.0,M,,*77"

def send_data(data):
    """Send data to receiver."""
    try:
        with socket(AF_INET, SOCK_STREAM) as s:
            s.connect((RECEIVER_IP, RECEIVER_PORT))
            s.sendall(data.encode())
            print(f"Sent: {data}")
    except Exception as e:
        print(f"Network Error: {e}")

if __name__ == "__main__":
    while True:
        fake_data = generate_fake_gps()
        send_data(fake_data)
        time.sleep(1)  # Send every 1 second
