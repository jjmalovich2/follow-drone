from socket import socket, AF_INET, SOCK_STREAM
from datetime import datetime
import struct
import os
from statistics import mean
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import time
import matplotlib.pyplot as plt
from io import BytesIO
import base64

# Constants
MSG_FORMAT = "!fffd"  # lat(float), lon(float), alt(float), timestamp(double)
MSG_SIZE = struct.calcsize(MSG_FORMAT)  # 24 bytes
DELAY_WINDOW = 5
HTTP_PORT = 8080
KML_FILE = "gps_path.kml"

# Valid coordinate ranges (adjust as needed)
MIN_LAT = -90
MAX_LAT = 90
MIN_LON = -180
MAX_LON = 180
MIN_ALT = -1000  # Dead Sea is about -430m
MAX_ALT = 10000  # Mount Everest is 8848m

class GPSData:
    def __init__(self, lat, lon, alt, timestamp):
        self.lat = lat
        self.lon = lon
        self.alt = alt
        self.timestamp = timestamp

class GPSReceiver:
    def __init__(self):
        self.gps_path = []
        self.lock = threading.Lock()
        self.total_bytes = 0
        self.valid_packets = 0
        self.invalid_packets = 0
        self.delay_avg = []
        self.client_addr = None
        self.last_update = time.time()
        self.plot_img = None
        self.buffer = bytearray()

    def validate_coordinates(self, lat, lon, alt):
        """Validate GPS coordinates are within reasonable ranges"""
        return (MIN_LAT <= lat <= MAX_LAT and
                MIN_LON <= lon <= MAX_LON and
                MIN_ALT <= alt <= MAX_ALT)

    def validate_timestamp(self, timestamp):
        """Validate timestamp is within reasonable range"""
        current_time = time.time()
        # Allow timestamps from 2020 to 1 hour in future
        return 1577836800 <= timestamp <= current_time + 3600

    def unpack_and_validate(self, binary_data):
        """Unpack and validate GPS data with comprehensive checks"""
        try:
            if len(binary_data) != MSG_SIZE:
                raise ValueError(f"Invalid size: expected {MSG_SIZE}, got {len(binary_data)}")
            
            # Unpack with strict byte order checking
            lat, lon, alt, timestamp = struct.unpack(MSG_FORMAT, binary_data)
            
            # Validate numerical ranges
            if not self.validate_coordinates(lat, lon, alt):
                raise ValueError(f"Invalid coordinates: lat={lat}, lon={lon}, alt={alt}")
            
            if not self.validate_timestamp(timestamp):
                raise ValueError(f"Invalid timestamp: {timestamp}")
            
            return GPSData(lat, lon, alt, timestamp)
            
        except struct.error as e:
            raise ValueError(f"Unpack error: {e}")
        except Exception as e:
            raise ValueError(f"Validation error: {e}")

    def process_buffer(self):
        """Process all complete messages in the buffer"""
        while len(self.buffer) >= MSG_SIZE:
            message = self.buffer[:MSG_SIZE]
            self.buffer = self.buffer[MSG_SIZE:]
            
            try:
                data = self.unpack_and_validate(message)
                self.valid_packets += 1
                self.handle_valid_data(data)
            except ValueError as e:
                self.invalid_packets += 1
                print(f"Bad data: {e}")
                # Try to resync by looking for next valid message
                self.resync_buffer()

    def resync_buffer(self):
        """Attempt to resync by finding the next valid message start"""
        for i in range(1, len(self.buffer)):
            try:
                # Check if this could be a valid message
                potential_msg = self.buffer[i:i+MSG_SIZE]
                if len(potential_msg) < MSG_SIZE:
                    break
                    
                data = self.unpack_and_validate(potential_msg)
                # If we get here, we found a valid message
                print(f"Resynced at offset {i}")
                self.buffer = self.buffer[i:]
                return
            except ValueError:
                continue
        
        # If we get here, no valid message found - clear buffer
        self.buffer.clear()

    def handle_valid_data(self, data):
        """Process validated GPS data"""
        current_delay = self.calculate_latency(data.timestamp)
        
        # Update delay metrics
        self.delay_avg.append(current_delay)
        if len(self.delay_avg) > DELAY_WINDOW:
            self.delay_avg.pop(0)
        avg_delay = mean(self.delay_avg) if self.delay_avg else 0
        
        # Store data
        with self.lock:
            self.gps_path.append(data)
            self.last_update = time.time()
            
            # Update plot periodically
            if len(self.gps_path) % 5 == 0:
                self.generate_plot_image()
        
        # Update console display
        self.display_status(data, current_delay, avg_delay)

    def calculate_latency(self, sent_ts):
        """Compute latency in milliseconds"""
        return round((time.time() - sent_ts) * 1000, 2)

    def display_status(self, data, current_delay, avg_delay):
        """Display current status in console"""
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"""
        GPS RECEIVER STATUS
        -------------------------------------
        | Connected To: {self.client_addr or 'None'}
        | Valid Packets: {self.valid_packets}
        | Invalid Packets: {self.invalid_packets}
        | Buffer Size: {len(self.buffer)} bytes
        -------------------------------------
        | Current Position:
        | Latitude: {data.lat:.6f}
        | Longitude: {data.lon:.6f}
        | Altitude: {data.alt:.1f}m
        -------------------------------------
        | Performance:
        | Current Delay: {current_delay:.2f}ms
        | Avg Delay (Last 5): {avg_delay:.2f}ms
        -------------------------------------
        | Web Interface: http://localhost:{HTTP_PORT}
        | Path Points: {len(self.gps_path)}
        | Last Update: {datetime.fromtimestamp(self.last_update).strftime('%H:%M:%S')}
        -------------------------------------
        """)

    def generate_plot_image(self):
        """Generate and cache the latest plot image"""
        with self.lock:
            if len(self.gps_path) < 2:
                self.plot_img = None
                return
            
            plt.figure(figsize=(10, 6))
            plt.plot([p.lon for p in self.gps_path], [p.lat for p in self.gps_path], 'b-', linewidth=2)
            
            # Mark start and end points
            if len(self.gps_path) > 1:
                plt.plot(self.gps_path[0].lon, self.gps_path[0].lat, 'go', markersize=8, label='Start')
                plt.plot(self.gps_path[-1].lon, self.gps_path[-1].lat, 'ro', markersize=8, label='End')
            
            plt.xlabel('Longitude')
            plt.ylabel('Latitude')
            plt.title(f'GPS Path ({len(self.gps_path)} points)')
            plt.legend()
            plt.grid(True)
            
            buf = BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
            plt.close()
            buf.seek(0)
            self.plot_img = base64.b64encode(buf.read()).decode('utf-8')

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            if self.path == '/':
                self.handle_main_page()
            elif self.path == '/kml':
                self.handle_kml_download()
            elif self.path == '/plot':
                self.handle_plot_image()
            else:
                self.send_error(404)
        except Exception as e:
            print(f"Error handling request: {e}")
            self.send_error(500)

    def handle_main_page(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
        with receiver.lock:
            path_count = len(receiver.gps_path)
            last_update = datetime.fromtimestamp(receiver.last_update).strftime('%H:%M:%S')
            has_plot = receiver.plot_img is not None
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>GPS Tracker</title>
    <meta http-equiv="refresh" content="2">
    <style>
        body {{ font-family: Arial, sans-serif; padding: 20px; }}
        .container {{ max-width: 1000px; margin: 0 auto; }}
        .plot-container {{ margin: 20px 0; text-align: center; }}
        img {{ max-width: 100%; border: 1px solid #ddd; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>GPS Path Tracking</h1>
        <p>Total points: {path_count} | Last update: {last_update}</p>
        
        <div class="plot-container">
            {f'<img src="data:image/png;base64,{receiver.plot_img}" alt="GPS Path">' if has_plot else '<p>Collecting data... (need at least 2 points)</p>'}
        </div>
        
        {self.generate_points_table()}
    </div>
</body>
</html>"""
        self.wfile.write(html.encode('utf-8'))

    def generate_points_table(self):
        with receiver.lock:
            if not receiver.gps_path:
                return ""
            
            points = receiver.gps_path[-10:][::-1]  # Last 10 points, newest first
            rows = "".join(
                f"<tr><td>{datetime.fromtimestamp(p.timestamp).strftime('%H:%M:%S')}</td>"
                f"<td>{p.lat:.6f}</td>"
                f"<td>{p.lon:.6f}</td>"
                f"<td>{p.alt:.1f}m</td></tr>"
                for p in points
            )
            
            return f"""
            <table>
                <tr><th>Time</th><th>Latitude</th><th>Longitude</th><th>Altitude</th></tr>
                {rows}
            </table>"""

    def handle_kml_download(self):
        receiver.save_kml()
        with open(KML_FILE, 'rb') as f:
            self.send_response(200)
            self.send_header('Content-type', 'application/vnd.google-earth.kml+xml')
            self.send_header('Content-Disposition', f'attachment; filename={KML_FILE}')
            self.end_headers()
            self.wfile.write(f.read())

    def handle_plot_image(self):
        with receiver.lock:
            if receiver.plot_img is None:
                self.send_error(404)
                return
            
            self.send_response(200)
            self.send_header('Content-type', 'image/png')
            self.end_headers()
            self.wfile.write(base64.b64decode(receiver.plot_img))

def start_http_server():
    server = HTTPServer(('0.0.0.0', HTTP_PORT), RequestHandler)
    print(f"HTTP server running on port {HTTP_PORT}")
    server.serve_forever()

def start_receiver():
    global receiver
    receiver = GPSReceiver()
    
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()
    
    with socket(AF_INET, SOCK_STREAM) as s:
        s.bind(('0.0.0.0', 40739))
        s.listen(1)
        print("GPS receiver waiting for connection...")
        conn, addr = s.accept()
        receiver.client_addr = addr[0]
        
        with conn:
            print(f"Connected to {addr}")
            buffer = bytearray()
            
            while True:
                try:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                        
                    receiver.total_bytes += len(chunk)
                    buffer.extend(chunk)
                    
                    while len(buffer) >= MSG_SIZE:
                        message = buffer[:MSG_SIZE]
                        buffer = buffer[MSG_SIZE:]
                        
                        coords = receiver.unpack_data(message)
                        if coords:
                            lat, lon, alt, ts = coords
                            current_delay = receiver.calculate_latency(ts)
                            
                            # Update metrics
                            receiver.delay_avg.append(current_delay)
                            if len(receiver.delay_avg) > DELAY_WINDOW:
                                receiver.delay_avg.pop(0)
                            avg_delay = mean(receiver.delay_avg) if receiver.delay_avg else 0
                            
                            # Store data
                            with receiver.lock:
                                data = GPSData(lat, lon, alt, ts)
                                receiver.gps_path.append(data)
                                receiver.last_update = time.time()
                                
                                # Update plot every 5 points
                                if len(receiver.gps_path) % 5 == 0:
                                    receiver.generate_plot_image()
                            
                            # Update console display
                            receiver.display(data, current_delay, avg_delay)
                            
                except (ConnectionResetError, ValueError) as e:
                    print(f"Connection error: {e}")
                    break

if __name__ == "__main__":
    start_receiver()
