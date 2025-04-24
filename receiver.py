from socket import socket, AF_INET, SOCK_STREAM
from datetime import datetime
import struct
import os
from statistics import mean
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import webbrowser
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
        self.delay_avg = []
        self.oldlat = '~'
        self.oldlon = '~'
        self.client_addr = None
        self.last_update = time.time()

    def calculate_latency(self, sent_ts):
        """Compute latency in milliseconds"""
        return round((datetime.now().timestamp() - sent_ts) * 1000, 2)

    def unpack_data(self, binary_data):
        """Unpack binary data with validation"""
        try:
            if len(binary_data) != MSG_SIZE:
                raise ValueError(f"Invalid size: expected {MSG_SIZE}, got {len(binary_data)}")
            return struct.unpack(MSG_FORMAT, binary_data)
        except struct.error as e:
            print(f"Unpack error: {e}")
            return None

    def display(self, data, current_delay, avg_delay):
        os.system('clear')
        print(f"""
            GPS TRACKING SYSTEM
            -------------------------------------
            | Connected To: {self.client_addr}                
            | Bytes Received: {self.total_bytes:,}    
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
        """Generate base64 encoded plot of GPS path"""
        with self.lock:
            if len(self.gps_path) < 2:
                return None

            plt.figure(figsize=(10, 6))
            
            # Extract coordinates
            lats = [p.lat for p in self.gps_path]
            lons = [p.lon for p in self.gps_path]
            
            # Create plot
            plt.plot(lons, lats, 'b-', linewidth=2, label='Path')
            plt.plot(lons[0], lats[0], 'go', markersize=8, label='Start')
            plt.plot(lons[-1], lats[-1], 'ro', markersize=8, label='End')
            
            # Add labels and title
            plt.xlabel('Longitude')
            plt.ylabel('Latitude')
            plt.title(f'GPS Path Tracking ({len(self.gps_path)} points)')
            plt.legend()
            plt.grid(True)
            
            # Save to bytes buffer
            buf = BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
            plt.close()
            buf.seek(0)
            return base64.b64encode(buf.read()).decode('utf-8')

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.handle_main_page()
        elif self.path == '/kml':
            self.handle_kml_download()
        else:
            self.send_response(404)
            self.end_headers()

    def handle_main_page(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
        # Generate plot image
        plot_img = receiver.generate_plot_image()
        
        # Get current stats
        with receiver.lock:
            path_count = len(receiver.gps_path)
            last_update = datetime.fromtimestamp(receiver.last_update).strftime('%H:%M:%S')
            last_point = receiver.gps_path[-1] if receiver.gps_path else None
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>GPS Path Viewer</title>
            <meta http-equiv="refresh" content="5">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .container {{ max-width: 1000px; margin: 0 auto; }}
                .panel {{ background: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
                .map-container {{ margin: 20px 0; text-align: center; }}
                img {{ max-width: 100%; height: auto; border: 1px solid #ddd; }}
                .data-table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                .data-table th, .data-table td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>GPS Path Tracking</h1>
                
                <div class="panel">
                    <div style="display: flex; justify-content: space-between;">
                        <div>Total points: <strong>{path_count}</strong></div>
                        <div>Last update: <strong>{last_update}</strong></div>
                    </div>
                </div>
                
                <div class="map-container">
                    {f'<img src="data:image/png;base64,{plot_img}" alt="GPS Path">' if plot_img else '<p>Not enough data points to generate path</p>'}
                </div>
                
                {self.generate_point_table() if receiver.gps_path else ''}
            </div>
        </body>
        </html>
        """
        self.wfile.write(html.encode())

    def generate_point_table(self):
        with receiver.lock:
            points = receiver.gps_path[-10:][::-1]  # Last 10 points, newest first
            
        rows = "\n".join(
            f"<tr><td>{datetime.fromtimestamp(p.timestamp).strftime('%H:%M:%S')}</td>"
            f"<td>{p.lat:.6f}</td>"
            f"<td>{p.lon:.6f}</td>"
            f"<td>{p.alt:.1f}m</td></tr>"
            for p in points
        )
        
        return f"""
        <table class="data-table">
            <tr>
                <th>Time</th>
                <th>Latitude</th>
                <th>Longitude</th>
                <th>Altitude</th>
            </tr>
            {rows}
        </table>
        """

    def handle_kml_download(self):
        receiver.save_kml()
        with open(KML_FILE, 'rb') as f:
            self.send_response(200)
            self.send_header('Content-type', 'application/vnd.google-earth.kml+xml')
            self.send_header('Content-Disposition', f'attachment; filename={KML_FILE}')
            self.end_headers()
            self.wfile.write(f.read())

def start_http_server():
    server = HTTPServer(('0.0.0.0', HTTP_PORT), RequestHandler)
    print(f"HTTP server started on port {HTTP_PORT}")
    webbrowser.open(f"http://localhost:{HTTP_PORT}")
    server.serve_forever()

def start_receiver():
    global receiver
    receiver = GPSReceiver()
    
    # Start HTTP server in a separate thread
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()
    
    with socket(AF_INET, SOCK_STREAM) as s:
        s.bind(('0.0.0.0', 40739))
        s.listen(1)
        print("GPS receiver started. Waiting for connections...")
        conn, addr = s.accept()
        receiver.client_addr = addr[0]
        
        with conn:
            print(f"Connected to {addr}")
            buffer = bytearray()
            
            while True:
                try:
                    chunk = conn.recv(MSG_SIZE - len(buffer))
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
                            
                            # Update delay average
                            receiver.delay_avg.append(current_delay)
                            if len(receiver.delay_avg) > DELAY_WINDOW:
                                receiver.delay_avg.pop(0)
                            avg_delay = mean(receiver.delay_avg) if receiver.delay_avg else 0
                            
                            # Store the data point
                            with receiver.lock:
                                data = GPSData(lat, lon, alt, ts)
                                receiver.gps_path.append(data)
                                receiver.last_update = time.time()
                                if len(receiver.gps_path) % 10 == 0:
                                    receiver.generate_plot_image()  # Pre-generate plot
                            
                            # Update display
                            receiver.display(data, current_delay, avg_delay)
                            
                except (ConnectionResetError, ValueError) as e:
                    print(f"Connection error: {e}")
                    break

if __name__ == "__main__":
    start_receiver()
