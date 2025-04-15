from socket import socket, AF_INET, SOCK_STREAM
from datetime import datetime
import ast
import os


def calculate_latency(sent_ts):
    """Compute latency in milliseconds"""
    return round((datetime.now().timestamp() - sent_ts) * 1000, 2)


def display(data, lat, lon, ts, oldlat, oldlon, id):
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
        | Connected To: {id} (RPi 3B)       
        -------------------------------------

        -------------------------------------                                              
        | Data: {data}                      
        | Drone Latitude: {oldlat}          
        | Drone Longitude: {oldlon}         
        | Drone Altitude: 3m                
        -------------------------------------

        -------------------------------------
        | Person Latitude: {lat}            
        | Person Longitude: {lon}           
        | Delay: {ts}ms                     
        -------------------------------------
    """)


def start_receiver():
    oldlat = '~'
    oldlon = '~'

    with socket(AF_INET, SOCK_STREAM) as s:
        s.bind(('0.0.0.0', 40739))
        s.listen(1)
        print("Receiver started. Waiting for connections...")
        conn, addr = s.accept()
        with conn:
            print(f"Connected to {addr}")
            while True:
                data = conn.recv(1024).decode()
                if not data:
                    break
                try:
                    coords = ast.literal_eval(data)
                    if len(coords) == 4:  # [lat, lon, alt, timestamp]
                        latency = calculate_latency(coords[3])
                        lat = coords[0]
                        lon = coords[1]

                        display(coords, lat, lon, latency, oldlat, oldlon, addr)

                except (SyntaxError, ValueError, IndexError):
                    print(f"Invalid data: {data}")


if __name__ == "__main__":
    start_receiver()
