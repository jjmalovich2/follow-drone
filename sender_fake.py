import random
import time
from socket import socket, AF_INET, SOCK_STREAM
from decoder import nmea_to_coords  # Reuse decoder for consistency

# Configuration
RECEIVER_IP = "172.16.18.74"
RECEIVER_PORT = 8080

def generate_fake_nmea():
    """Generate fake NMEA sentence in GPGGA format"""
    lat = round(random.uniform(-90, 90), 6)
    lon = round(random.uniform(-180, 180), 6)
    return f"$GPGGA,000000,{abs(lat):09.6f},{'N' if lat >=0 else 'S'},{abs(lon):010.6f},{'E' if lon >=0 else 'W'},1,08,1.0,10.0,M,0.0,M,,*00"

def send_data(data):
    """Send coordinates to receiver"""
    try:
        with socket(AF_INET, SOCK_STREAM) as s:
            s.connect((RECEIVER_IP, RECEIVER_PORT))
            s.sendall(data.encode())
            print(f"Sent: {data}")
    except Exception as e:
        print(f"Network Error: {e}")

if __name__ == "__main__":
    while True:
        # Generate fake NMEA → decode → send
        fake_nmea = generate_fake_nmea()
        coords = nmea_to_coords(fake_nmea)
        if coords:
            send_data(str(coords))  # Same format as real GPS
        time.sleep(1)
