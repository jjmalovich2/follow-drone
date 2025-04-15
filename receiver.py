from socket import socket, AF_INET, SOCK_STREAM
from datetime import datetime
import struct
import os
from statistics import mean

# Constants
MSG_FORMAT = "!fffd"  # lat(float), lon(float), alt(float), timestamp(double)
MSG_SIZE = struct.calcsize(MSG_FORMAT)  # 24 bytes
DELAY_WINDOW = 5  # Only keep last 5 latency measurements

def calculate_latency(sent_ts):
    """Compute latency in milliseconds"""
    return round((datetime.now().timestamp() - sent_ts) * 1000, 2)

def unpack_data(binary_data):
    """Unpack binary data with validation"""
    try:
        if len(binary_data) != MSG_SIZE:
            raise ValueError(f"Invalid size: expected {MSG_SIZE}, got {len(binary_data)}")
        return struct.unpack(MSG_FORMAT, binary_data)
    except struct.error as e:
        print(f"Unpack error: {e}")
        return None

def display(data, lat, lon, current_delay, avg_delay, oldlat, oldlon, id, byte_count):
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
        | Connected To: {id}                
        | Bytes Received: {byte_count:,}    
        -------------------------------------

        -------------------------------------                                              
        | Data: {data}                      
        | Drone Latitude: {oldlat}          
        | Drone Longitude: {oldlon}         
        | Drone Altitude: 3m                
        -------------------------------------

        -------------------------------------
        | Person Latitude: {lat:.6f}        
        | Person Longitude: {lon:.6f}       
        | Current Delay: {current_delay:.2f}ms
        | Avg Delay (Last 5): {avg_delay:.2f}ms
        -------------------------------------
    """)

def start_receiver():
    oldlat = '~'
    oldlon = '~'
    total_bytes = 0
    delay_avg = []  # Will only keep last 5 measurements

    with socket(AF_INET, SOCK_STREAM) as s:
        s.bind(('0.0.0.0', 40739))
        s.listen(1)
        print("Receiver started. Waiting for connections...")
        conn, addr = s.accept()
        with conn:
            print(f"Connected to {addr}")
            buffer = bytearray()
            
            while True:
                try:
                    # Receive fixed-size chunks
                    chunk = conn.recv(MSG_SIZE - len(buffer))
                    if not chunk:
                        break
                        
                    total_bytes += len(chunk)
                    buffer.extend(chunk)
                    
                    # Process complete messages
                    while len(buffer) >= MSG_SIZE:
                        message = buffer[:MSG_SIZE]
                        buffer = buffer[MSG_SIZE:]
                        
                        coords = unpack_data(message)
                        if coords:
                            lat, lon, alt, ts = coords
                            current_delay = calculate_latency(ts)
                            
                            # Maintain rolling window of 5 delays
                            delay_avg.append(current_delay)
                            if len(delay_avg) > DELAY_WINDOW:
                                delay_avg.pop(0)
                            
                            avg_delay = mean(delay_avg) if delay_avg else 0
                            
                            display(
                                coords, lat, lon, 
                                current_delay, avg_delay,
                                oldlat, oldlon, addr, 
                                total_bytes
                            )
                            oldlat = lat
                            oldlon = lon
                            
                except (ConnectionResetError, ValueError) as e:
                    print(f"Connection error: {e}")
                    break

if __name__ == "__main__":
    start_receiver()
