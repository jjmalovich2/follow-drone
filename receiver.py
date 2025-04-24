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
import traceback

# Constants
MSG_FORMAT = "!fffd"  # lat(float), lon(float), alt(float), timestamp(double)
MSG_SIZE = struct.calcsize(MSG_FORMAT)  # 24 bytes
DELAY_WINDOW = 5
HTTP_PORT = 8080
KML_FILE = "gps_path.kml"

# Valid coordinate ranges
MIN_LAT = -90
MAX_LAT = 90
MIN_LON = -180
MAX_LON = 180
MIN_ALT = -1000
MAX_ALT = 10000

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
        return 1577836800 <= timestamp <= current_time + 3600  # 2020-2023 + 1hr

    def unpack_and_validate(self, binary_data):
        """Unpack and validate GPS data with comprehensive checks"""
        try:
            if len(binary_data) != MSG_SIZE:
                raise ValueError(f"Invalid size: expected {MSG_SIZE}, got {len(binary_data)}")
            
            lat, lon, alt, timestamp = struct.unpack(MSG_FORMAT, binary_data)
            
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
            
            try:
                data = self.unpack_and_validate(message)
                self.valid_packets += 1
                self.buffer = self.buffer[MSG_SIZE:]
                self.handle_valid_data(data)
            except ValueError as e:
                self.invalid_packets += 1
                print(f"Bad data: {e}")
                self.resync_buffer()

    def resync_buffer(self):
        """Attempt to resync by finding the next valid message start"""
        sync_found = False
        for i in range(1, len(self.buffer)):
            try:
                potential_msg = self.buffer[i:i+MSG_SIZE]
                if len(potential_msg) < MSG_SIZE:
                    break
                    
                data = self.unpack_and_validate(potential_msg)
                print(f"Resynced at offset {i}")
                self.buffer = self.buffer[i:]
                sync_found = True
                break
            except ValueError:
                continue
        
        if not sync_found:
            self.buffer.clear()

    def handle_valid_data(self, data):
        """Process validated GPS data"""
        current_delay = self.calculate_latency(data.timestamp)
        
        self.delay_avg.append(current_delay)
        if len(self.delay_avg) > DELAY_WINDOW:
            self.delay_avg.pop(0)
        avg_delay = mean(self.delay_avg) if self.delay_avg else 0
        
        with self.lock:
            self.gps_path.append(data)
            self.last_update = time.time()
            
            if len(self.gps_path) % 5 == 0 or len(self.gps_path) == 1:
                self.generate_plot_image()
        
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
            if len(self.gps_path) < 1:
                self.plot_img = None
                return
            
            plt.figure(figsize=(10, 6))
            
            if len(self.gps_path) > 1:
                plt.plot([p.lon for p in self.gps_path], [p.lat for p in self.gps_path], 
                        'b-', linewidth=2, label='Path')
                plt.plot(self.gps_path[0].lon, self.gps_path[0].lat, 
                        'go', markersize=8, label='Start')
                plt.plot(self.gps_path[-1].lon, self.gps_path[-1].lat, 
                        'ro', markersize=8, label='End')
            else:
                plt.plot(self.gps_path[0].lon, self.gps_path[0].lat, 
                        'bo', markersize=8, label='Single Point')
            
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

    def save_kml(self):
        """Save current path as KML file"""
        with self.lock:
            if not self.gps_path:
                return
            
            with open(KML_FILE, 'w') as f:
                f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
                f.write('<kml xmlns="http://www.opengis.net/kml/2.2">\n')
                f.write('<Document>\n')
                f.write('<Placemark>\n')
                f.write('<name>GPS Path</name>\n')
                f.write('<LineString>\n')
                f.write('<coordinates>\n')
                
                for point in self.gps_path:
                    f.write(f"{point.lon},{point.lat},{point.alt}\n")
                
                f.write('</coordinates>\n')
                f.write('</LineString>\n')
                f.write('</Placemark>\n')
                f.write('</Document>\n')
                f.write('</kml>\n')

class HTTPRequestHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    
    def do_GET(self):
        try:
            if self.path == '/':
                self.handle_main_page()
            elif self.path == '/kml':
                self.handle_kml_download()
            elif self.path == '/plot':
                self.handle_plot_image()
            elif self.path == '/favicon.ico':
                self.handle_favicon()
            else:
                self.send_error(404, "Not Found")
        except Exception as e:
            print(f"HTTP Error: {e}\n{traceback.format_exc()}")
            self.send_error(500, "Internal Server Error")

    def handle_main_page(self):
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
        .status {{ background: #f5f5f5; padding: 10px; border-radius: 5px; }}
        .plot-container {{ margin: 20px 0; text-align: center; }}
        img {{ max-width: 100%; border: 1px solid #ddd; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>GPS Path Tracking</h1>
        
        <div class="status">
            <strong>Total points:</strong> {path_count} | 
            <strong>Last update:</strong> {last_update}
        </div>
        
        <div class="plot-container">
            {f'<img src="/plot" alt="GPS Path">' if has_plot else '<p>Collecting data... (need at least 1 point)</p>'}
        </div>
        
        {self.generate_points_table()}
    </div>
</body>
</html>"""

        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(html)))
        self.end_headers()
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

    def handle_plot_image(self):
        with receiver.lock:
            if not receiver.plot_img:
                self.send_error(404, "No plot available")
                return
            
            img_data = base64.b64decode(receiver.plot_img)
            self.send_response(200)
            self.send_header('Content-type', 'image/png')
            self.send_header('Content-Length', str(len(img_data)))
            self.end_headers()
            self.wfile.write(img_data)

    def handle_kml_download(self):
        receiver.save_kml()
        try:
            with open(KML_FILE, 'rb') as f:
                kml_data = f.read()
                self.send_response(200)
                self.send_header('Content-type', 'application/vnd.google-earth.kml+xml')
                self.send_header('Content-Disposition', f'attachment; filename="{KML_FILE}"')
                self.send_header('Content-Length', str(len(kml_data)))
                self.end_headers()
                self.wfile.write(kml_data)
        except FileNotFoundError:
            self.send_error(404, "KML file not found")

    def handle_favicon(self):
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        """Override to prevent logging to stderr"""
        pass

def start_http_server():
    """Start the HTTP server with proper error handling"""
    server_address = ('', HTTP_PORT)
    httpd = HTTPServer(server_address, HTTPRequestHandler)
    print(f"HTTP server running on port {HTTP_PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()

def start_receiver():
    global receiver
    receiver = GPSReceiver()
    
    # Start HTTP server in a separate thread
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()
    
    with socket(AF_INET, SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('0.0.0.0', 40739))
        s.listen(1)
        print("GPS receiver waiting for connection...")
        
        try:
            while True:
                conn, addr = None, None
                try:
                    conn, addr = s.accept()
                    receiver.client_addr = addr[0]
                    print(f"Connected to {addr}")
                    
                    with conn:
                        while True:
                            try:
                                chunk = conn.recv(4096)
                                if not chunk:
                                    break
                                    
                                receiver.total_bytes += len(chunk)
                                receiver.buffer.extend(chunk)
                                receiver.process_buffer()
                                
                            except ConnectionResetError:
                                print("Connection reset by peer")
                                break
                            except Exception as e:
                                print(f"Data processing error: {e}")
                                break
                            
                except OSError as e:
                    print(f"Socket error: {e}")
                finally:
                    if conn:
                        conn.close()
                    print("Connection closed")
                    receiver.client_addr = None
                    
        except KeyboardInterrupt:
            print("Shutting down...")
        finally:
            s.close()

if __name__ == "__main__":
    start_receiver()
