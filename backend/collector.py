import socket
import requests
import re

# Replace with your cloud server's URL and port
SERVER_URL = "https://device-metrics.onrender.com/esp32metrics"

# UDP socket configuration
HOST = "192.168.89.61"  #this value changes!
PORT = 12345

def send_metrics_to_server(temperature):
    try:
        payload = {
            "device_name": 'esp32_device',
            "temperature": temperature,
        }
        response = requests.post(SERVER_URL, json=payload)
        
        if response.status_code == 201:
            print(f"Successfully sent metrics: Temperature {temperature}")
        else:
            print(f"Failed to send metrics. Status code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Error sending metrics: {e}")

def main():
    # Create a UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST, PORT))
    print(f"Listening on {HOST}:{PORT}")

    try:
        while True:
            data, addr = sock.recvfrom(1024)  # Buffer size is 1024 bytes
            try:
                # Parse received data
                message = data.decode('utf-8').strip()

                # Use regex to extract temperature
                match = re.match(r'Temperature: (\d+\.\d+) C', message)
                if match:
                    temperature = float(match.group(1))
                    
                    # Send metrics to the server
                    send_metrics_to_server(temperature
                    )
                    
                    print(f"Received from {addr}: {message}")
                else:
                    print(f"Unrecognized message format: {message}")
            except (ValueError, TypeError) as e:
                print(f"Error processing received data: {e}")
    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        sock.close()

if __name__ == "__main__":
    main()