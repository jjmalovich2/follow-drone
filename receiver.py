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
        self.plot_img = None

    # [Previous methods remain the same until generate_plot_image]

    def generate_plot_image(self):
        """Generate and cache the latest plot image"""
        with self.lock:
            if len(self.gps_path) < 2:
                self.plot_img = None
                return
            
            plt.figure(figsize=(10, 6))
            plt.plot([p.lon for p in self.gps_path], [p.lat for p in self.gps_path], 'b-')
            plt.xlabel('Longitude')
            plt.ylabel('Latitude')
            plt.title('GPS Path')
            plt.grid(True)
            
            buf = BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight')
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
