import socket
import struct
from datetime import datetime
import random  # Only needed for fake GPS

# Configuration
DELAY = 1
RECEIVER_IP = "172.16.18.74"
RECEIVER_PORT = 40739
MSG_FORMAT = "!fffd"  # lat(float), lon(float), alt(float), timestamp(double)
MSG_SIZE = struct.calcsize(MSG_FORMAT)  # 24 bytes

def pack_data(lat, lon, alt=10.0):
    """Pack coordinates into fixed-size binary"""
    timestamp = datetime.now().timestamp()
    return struct.pack(MSG_FORMAT, lat, lon, alt, timestamp)

def send_gps_data():
    """Real GPS version (using your GPS module)"""
    # Replace with your actual GPS reading code
    lat, lon = read_gps_module()  # Implement this
    return pack_data(lat, lon)

def send_fake_data():
    """Simulated GPS version"""
    lat = round(random.uniform(-90, 90), 6)
    lon = round(random.uniform(-180, 180), 6)
    return pack_data(lat, lon)

def start_sender(use_real_gps=True):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((RECEIVER_IP, RECEIVER_PORT))
        print(f"Connected to {RECEIVER_IP}:{RECEIVER_PORT}")
        
        while True:
            try:
                # Choose data source
                binary_data = send_gps_data() if use_real_gps else send_fake_data()
                
                # Send exactly MSG_SIZE bytes
                s.sendall(binary_data)
                print(f"Sent {len(binary_data)} bytes | Lat: {struct.unpack(MSG_FORMAT, binary_data)[0]:.6f}")
                
                time.sleep(DELAY)  # Adjust frequency as needed
                
            except (socket.error, struct.error) as e:
                print(f"Error: {e}")
                break

if __name__ == "__main__":
    start_sender(use_real_gps=False)  # Change to True for real GPS
