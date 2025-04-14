import serial
import time
from socket import socket, AF_INET, SOCK_STREAM

# GPS Setup (adjust port/baudrate)
GPS_PORT = "/dev/ttyS0"  # Common ports: /dev/ttyAMA0, /dev/ttyUSB0
GPS_BAUDRATE = 9600

# Receiver Pi's IP and port
RECEIVER_IP = "192.168.1.100"  # Replace with receiver's IP
RECEIVER_PORT = 1234

def get_gps_data():
    """Read NMEA data from GPS module"""
    try:
        ser = serial.Serial(GPS_PORT, GPS_BAUDRATE, timeout=1)
        while True:
            line = ser.readline().decode('ascii', errors='replace').strip()
            if line.startswith('$GPGGA'):  # Example: GPGGA sentence has lat/lon
                return line
    except serial.SerialException as e:
        print(f"GPS Error: {e}")
        return None

def send_to_receiver(data):
    """Send data over TCP"""
    try:
        with socket(AF_INET, SOCK_STREAM) as s:
            s.connect((RECEIVER_IP, RECEIVER_PORT))
            s.sendall(data.encode())
            print(f"Sent: {data}")
    except Exception as e:
        print(f"Network Error: {e}")

if __name__ == "__main__":
    while True:
        gps_data = get_gps_data()
        if gps_data:
            send_to_receiver(gps_data)
        time.sleep(1)  # Adjust based on GPS update rate
