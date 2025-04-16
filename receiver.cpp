#include <iostream>
#include <vector>
#include <deque>
#include <chrono>
#include <cstring>
#include <sys/socket.h>
#include <netinet/in.h>
#include <unistd.h>
#include <cmath>
#include <algorithm>
#include <iomanip>
#include <arpa/inet.h>
#include <endian.h>
#include <string>

// Constants
const int PORT = 40739;
const std::string IP = "172.16.18.74";
const int MSG_SIZE = 24;  // 4+4+4+8 bytes (3 floats + 1 double)
const int DELAY_WINDOW = 5;

// Global metrics
struct {
    int total_received = 0;
    int corrupted_packets = 0;
    double max_delay = 0.0;
    double min_delay = std::numeric_limits<double>::infinity();
    std::deque<double> delay_history;
    std::vector<char> buffer;
    size_t total_bytes = 0;
} metrics;

struct GPSData {
    float lat;
    float lon;
    float alt;
    double timestamp;
};

// Function declarations
void clear_screen();
GPSData unpack_data(const char* data);
void display(const GPSData& data, double current_delay, double avg_delay, 
             const std::string& old_coords, const sockaddr_in& client_addr);
double calculate_latency(double sent_ts);
void start_receiver();

int main() {
    start_receiver();
    return 0;
}

void clear_screen() {
    std::cout << "\033[2J\033[1;1H";  // ANSI escape codes
}

GPSData unpack_data(const char* data) {
    GPSData result;
    
    // Copy and convert network byte order to host
    uint32_t temp;
    memcpy(&temp, data, 4);
    result.lat = ntohl(temp);
    memcpy(&temp, data+4, 4);
    result.lon = ntohl(temp);
    memcpy(&temp, data+8, 4);
    result.alt = ntohl(temp);
    
    uint64_t timestamp_temp;
    memcpy(&timestamp_temp, data+12, 8);
    result.timestamp = be64toh(timestamp_temp);
    
    return result;
}

void display(const GPSData& data, double current_delay, double avg_delay,
             const std::string& old_coords, const sockaddr_in& client_addr) {
    clear_screen();
    
    char client_ip[INET_ADDRSTRLEN];
    inet_ntop(AF_INET, &(client_addr.sin_addr), client_ip, INET_ADDRSTRLEN);
    
    auto now = std::chrono::system_clock::now();
    auto ts = std::chrono::system_clock::to_time_t(now);
    
    std::cout << "\n        GPS DATA RECEIVER (C++)"
              << "\n        -------------------------------------"
              << "\n        | Connected To: " << client_ip << ":" << ntohs(client_addr.sin_port)
              << "\n        | Bytes Received: " << metrics.total_bytes
              << "\n        | Buffer: " << metrics.buffer.size() << " bytes"
              << "\n        | Queued Messages: " << metrics.buffer.size() / MSG_SIZE
              << "\n        | Partial Message: " << metrics.buffer.size() % MSG_SIZE << " bytes"
              << "\n        -------------------------------------"
              << "\n        | Last Timestamp: " << std::put_time(std::localtime(&ts), "%H:%M:%S")
              << "\n        | Current Delay: " << std::fixed << std::setprecision(2) << current_delay << "ms"
              << "\n        | Avg Delay (Last 5): " << avg_delay << "ms"
              << "\n        -------------------------------------"
              << "\n        | Latitude: " << std::setprecision(6) << data.lat
              << "\n        | Longitude: " << data.lon
              << "\n        | Altitude: " << data.alt << "m"
              << "\n        -------------------------------------\n";
}

double calculate_latency(double sent_ts) {
    auto now = std::chrono::system_clock::now();
    double current_ts = std::chrono::duration_cast<std::chrono::milliseconds>(
        now.time_since_epoch()).count() / 1000.0;
    return (current_ts - sent_ts) * 1000;  // Convert to milliseconds
}

void start_receiver() {
    int server_fd, new_socket;
    struct sockaddr_in address;
    int opt = 1;
    int addrlen = sizeof(address);
    
    // Create socket
    if ((server_fd = socket(AF_INET, SOCK_STREAM, 0)) == 0) {
        perror("socket failed");
        exit(EXIT_FAILURE);
    }
    
    // Set socket options
    if (setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR | SO_REUSEPORT, &opt, sizeof(opt))) {
        perror("setsockopt");
        exit(EXIT_FAILURE);
    }
    
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = INADDR_ANY;
    address.sin_port = htons(PORT);
    
    // Bind socket
    if (bind(server_fd, (struct sockaddr *)&address, sizeof(address)) < 0) {
        perror("bind failed");
        exit(EXIT_FAILURE);
    }
    
    // Listen for connections
    if (listen(server_fd, 3) < 0) {
        perror("listen");
        exit(EXIT_FAILURE);
    }
    
    std::cout << "Receiver started. Waiting for connections...\n"
              << "Port: " << PORT
              << "IP:   " << IP;
    
    // Accept connection
    if ((new_socket = accept(server_fd, (struct sockaddr *)&address, (socklen_t*)&addrlen)) < 0) {
        perror("accept");
        exit(EXIT_FAILURE);
    }
    
    std::string old_coords = "~, ~";
    std::deque<double> delay_avg;
    
    while (true) {
        char buffer[1024];
        int valread = read(new_socket, buffer, sizeof(buffer));
        
        if (valread <= 0) {
            break;  // Connection closed or error
        }
        
        metrics.total_bytes += valread;
        metrics.buffer.insert(metrics.buffer.end(), buffer, buffer + valread);
        
        while (metrics.buffer.size() >= MSG_SIZE) {
            GPSData data = unpack_data(metrics.buffer.data());
            metrics.buffer.erase(metrics.buffer.begin(), metrics.buffer.begin() + MSG_SIZE);
            
            double latency = calculate_latency(data.timestamp);
            
            // Update delay statistics
            delay_avg.push_back(latency);
            if (delay_avg.size() > DELAY_WINDOW) {
                delay_avg.pop_front();
            }
            
            double avg_delay = 0.0;
            if (!delay_avg.empty()) {
                avg_delay = std::accumulate(delay_avg.begin(), delay_avg.end(), 0.0) / delay_avg.size();
            }
            
            // Update metrics
            metrics.total_received++;
            metrics.max_delay = std::max(metrics.max_delay, latency);
            metrics.min_delay = std::min(metrics.min_delay, latency);
            metrics.delay_history.push_back(latency);
            
            // Update display
            old_coords = std::to_string(data.lat) + ", " + std::to_string(data.lon);
            display(data, latency, avg_delay, old_coords, address);
        }
    }
    
    close(new_socket);
    close(server_fd);
}
