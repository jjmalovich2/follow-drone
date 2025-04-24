from socket import socket, AF_INET, SOCK_STREAM
from datetime import datetime
import struct
import os
from statistics import mean
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import webbrowser
from urllib.parse import urlencode
import time

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
            $$$$$$$$\        $$\ $$\                               $$$$$$$\                                          
            $$  _____|       $$ |$$ |                              $$  __$$\                                         
            $$ |    $$$$$$\  $$ |$$ | $$$$$$\  $$\  $$\  $$\       $$ |  $$ | $$$$$$\   $$$$$$\  $$$$$$$\   $$$$$$\  
            $$$$$\ $$  __$$\ $$ |$$ |$$  __$$\ $$ | $$ | $$ |      $$ |  $$ |$$  __$$\ $$  __$$\ $$  __$$\ $$  __$$\ 
            $$  __|$$ /  $$ |$$ |$$ |$$ /  $$ |$$ | $$ | $$ |      $$ |  $$ |$$ |  \__|$$ /  $$ |$$ |  $$ |$$$$$$$$ |
            $$ |   $$ |  $$ |$$ |$$ |$$ |  $$ |$$ | $$ | $$ |      $$ |  $$ |$$ |      $$ |  $$ |$$ |  $$ |$$   ____|
            $$ |   \$$$$$$  |$$ |$$ |\$$$$$$  |\$$$$$\$$$$  |      $$$$$$$  |$$ |      \$$$$$$  |$$ |  $$ |\$$$$$$$\ 
            \__|    \______/ \__|\__| \______/  \_____\____/       \_______/ \__|       \______/ \__|  \__| \_______|                                                                                                     

            -------------------------------------
            | Connected To: {self.client_addr}                
            | Bytes Received: {self.total_bytes:,}    
            -------------------------------------

            -------------------------------------                                              
            | Data: {data}                      
            | Drone Latitude: {self.oldlat}          
            | Drone Longitude: {self.oldlon}         
            | Drone Altitude: 3m                
            -------------------------------------

            -------------------------------------
            | Person Latitude: {data.lat:.6f}        
            | Person Longitude: {data.lon:.6f}       
            | Current Delay: {current_delay:.2f}ms
            | Avg Delay (Last 5): {avg_delay:.2f}ms
            -------------------------------------
            | Web Interface: http://localhost:{HTTP_PORT}
            | Path Points: {len(self.gps_path)}
            | Last Update: {datetime.fromtimestamp(self.last_update).strftime('%H:%M:%S')}
            -------------------------------------
        """)

    def save_kml(self):
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

    def generate_google_maps_url(self):
        if not self.gps_path:
            return ""
        
        with self.lock:
            # Create a path for Google Maps
            path_coords = "|".join([f"{p.lat},{p.lon}" for p in self.gps_path])
            
            # Google Maps URL with path
            params = {
                'q': path_coords,
                'output': 'embed',
                'z': '15'  # Zoom level
            }
            return f"https://www.google.com/maps?{urlencode(params)}"

    def generate_static_map_url(self):
        if not self.gps_path:
            return ""
        
        with self.lock:
            # Create path for static map
            path_coords = "|".join([f"{p.lat},{p.lon}" for p in self.gps_path])
            
            # Create markers for start and end
            markers = []
            if len(self.gps_path) > 1:
                start = self.gps_path[0]
                end = self.gps_path[-1]
                markers.append(f"color:green|label:S|{start.lat},{start.lon}")
                markers.append(f"color:red|label:E|{end.lat},{end.lon}")
            
            # Static Maps URL parameters
            params = {
                'size': '800x400',
                'maptype': 'roadmap',
                'path': f'color:0x0000ff|weight:5|{path_coords}',
                'markers': '&markers='.join(markers)
            }
            return f"https://maps.googleapis.com/maps/api/staticmap?{urlencode(params)}"

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            # Generate URLs with current data
            maps_url = receiver.generate_google_maps_url()
            static_url = receiver.generate_static_map_url()
            
            # Get current path length
            with receiver.lock:
                path_count = len(receiver.gps_path)
                last_update = datetime.fromtimestamp(receiver.last_update).strftime('%H:%M:%S')
            
            # Auto-refresh every 5 seconds
            html = f"""
            <html>
                <head>
                    <title>GPS Path Viewer</title>
                    <meta http-equiv="refresh" content="5">
                    <style>
                        body {{ font-family: Arial, sans-serif; margin: 20px; }}
                        .map-container {{ margin: 20px 0; }}
                        a {{ color: #1a73e8; text-decoration: none; }}
                        a:hover {{ text-decoration: underline; }}
                        .info {{ background: #f5f5f5; padding: 10px; border-radius: 5px; }}
                    </style>
                </head>
                <body>
                    <h1>GPS Path Viewer</h1>
                    <div class="info">
                        <p>Total points: {path_count}</p>
                        <p>Last update: {last_update}</p>
                    </div>
                    
                    <div class="map-container">
                        <h2>Interactive Map</h2>
                        <iframe
                            width="100%"
                            height="450"
                            frameborder="0" style="border:0"
                            src="{maps_url}"
                            allowfullscreen>
                        </iframe>
                        <p><a href="{maps_url}" target="_blank">Open in full window</a></p>
                    </div>
                    
                    <div class="map-container">
                        <h2>Static Map</h2>
                        <img src="{static_url}" alt="GPS Path" style="max-width: 100%;">
                    </div>
                    
                    <div class="map-container">
                        <h2>Download</h2>
                        <a href="/kml" download>Download KML file</a>
                    </div>
                </body>
            </html>
            """
            self.wfile.write(html.encode())
        elif self.path == '/kml':
            receiver.save_kml()
            with open(KML_FILE, 'rb') as f:
                self.send_response(200)
                self.send_header('Content-type', 'application/vnd.google-earth.kml+xml')
                self.send_header('Content-Disposition', f'attachment; filename={KML_FILE}')
                self.end_headers()
                self.wfile.write(f.read())
        else:
            self.send_response(404)
            self.end_headers()

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
                                if len(receiver.gps_path) % 10 == 0:  # Save more frequently
                                    receiver.save_kml()
                            
                            # Update display
                            receiver.display(data, current_delay, avg_delay)
                            receiver.oldlat = lat
                            receiver.oldlon = lon
                            
                except (ConnectionResetError, ValueError) as e:
                    print(f"Connection error: {e}")
                    break

if __name__ == "__main__":
    start_receiver()
