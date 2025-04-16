import socket
import struct
from datetime import datetime
import serial  # For GPS module
import os

# Configuration
RECEIVER_IP = "172.16.18.74"  # Replace with receiver IP
RECEIVER_PORT = 8080
GPS_PORT = "/dev/ttyACM0"     # Typical GPS device
GPS_BAUD = 9600               # Common baud rate for GPS modules
MSG_FORMAT = "!fffd"          # lat(float), lon(float), alt(float), timestamp(double)
MSG_SIZE = struct.calcsize(MSG_FORMAT)

def get_gps_coordinates():
    """Read real GPS data from serial connection"""
    with serial.Serial(GPS_PORT, GPS_BAUD, timeout=1) as ser:
        while True:
            line = ser.readline().decode('ascii', errors='ignore').strip()
            if line.startswith('$GPGGA'):  # Standard NMEA sentence
                try:
                    parts = line.split(',')
                    lat = float(parts[2][:2]) + float(parts[2][2:])/60
                    if parts[3] == 'S': lat *= -1
                    lon = float(parts[4][:3]) + float(parts[4][3:])/60
                    if parts[5] == 'W': lon *= -1
                    return lat, lon, float(parts[9])  # Altitude in meters
                except (IndexError, ValueError):
                    continue

def display_sender(lat, lon, alt, timestamp, byte_count):
    """ASCII display with real-time stats"""
    os.system('clear')
    print(f"""
        REAL GPS SENDER
        -------------------------------------
        | Last Update: {datetime.fromtimestamp(timestamp).strftime('%H:%M:%S.%f')[:-3]}
        | Latitude: {lat:.6f}
        | Longitude: {lon:.6f}
        | Altitude: {alt:.1f}m
        | Bytes Sent: {byte_count:,}
        -------------------------------------
        | GPS Fix: Active
        | Satellites: {get_satellite_count()}  # Implement this based on your GPS module
        -------------------------------------
    """)

def send_data():
    byte_count = 0
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((RECEIVER_IP, RECEIVER_PORT))
        print(f"Connected to {RECEIVER_IP}:{RECEIVER_PORT}")
        
        while True:
            try:
                # Get real GPS coordinates
                lat, lon, alt = get_gps_coordinates()
                timestamp = datetime.now().timestamp()
                
                # Pack and send binary data
                data = struct.pack(MSG_FORMAT, lat, lon, alt, timestamp)
                s.sendall(data)
                byte_count += MSG_SIZE
                
                # Update display
                display_sender(lat, lon, alt, timestamp, byte_count)
                
                # Throttle to GPS update rate (typically 1Hz)
                time.sleep(1)  
                
            except (serial.SerialException, socket.error) as e:
                print(f"Error: {e}")
                time.sleep(5)  # Wait before retrying
                continue

if __name__ == "__main__":
    send_data()
