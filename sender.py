import serial
import time
from socket import socket, AF_INET, SOCK_STREAM
from decoder import nmea_to_coords  # Import your decoder function

# Configuration
GPS_PORT = "/dev/ttyS0"
GPS_BAUDRATE = 9600
RECEIVER_IP = "172.16.18.74"
RECEIVER_PORT = 8080

def get_gps_data():
    """Read raw NMEA data from GPS module"""
    try:
        ser = serial.Serial(GPS_PORT, GPS_BAUDRATE, timeout=1)
        while True:
            line = ser.readline().decode('ascii', errors='ignore').strip()
            if line.startswith(('$GPGGA', '$GPRMC')):
                return line
    except Exception as e:
        print(f"GPS Error: {e}")
        return None

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
        raw_data = get_gps_data()
        if raw_data:
            # Decode and send coordinates
            coords = nmea_to_coords(raw_data)
            if coords:
                send_data(str(coords))  # Send as string "[lat,lon,alt]"
        time.sleep(1)
