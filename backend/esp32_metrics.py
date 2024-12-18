# description: This script listens for UDP packets from an ESP32 device and saves the temperature readings to a file in a queue directory.
# The script is designed to run continuously and save the metrics to a file each time a packet is received.
# The metrics are saved in JSON format with the device name, temperature reading, and timestamp.
# The script also logs the received messages and any errors that occur during processing.
# The script can be run as a standalone program and will listen for packets on the specified host and port.
# The queue directory is created if it does not exist, and the metrics are saved to a file with a unique filename based on the timestamp.
# The script can be stopped by pressing Ctrl+C, which will close the UDP socket and exit the program.

#define imports
import os
import socket
import time
import re
import json
import logging

class ESP32MetricsCollector:

    def __init__(self, host="192.168.251.61", port=12345, queue_dir='metrics_queue'): #change ip as required
        # Configure UDP socket
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.host, self.port))
        
        # Setup logging
        self.logger = self._setup_logging()
        
        # Create queue directory
        self.queue_dir = queue_dir
        os.makedirs(self.queue_dir, exist_ok=True)

    def _setup_logging(self):
        # Create logs directory
        log_dir = 'logs'
        os.makedirs(log_dir, exist_ok=True)

        # Create logger
        logger = logging.getLogger('esp32_metrics')
        logger.setLevel(logging.INFO)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(console_handler)

        # File handler 
        file_handler = logging.FileHandler(os.path.join(log_dir, 'esp32_metrics.log'))
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(file_handler)

        return logger

    def save_metrics(self, temperature):
        """
        Save metrics to a file in the queue directory
        
        Args:
        temperature (float): Temperature reading
        """
        try:
            # Create metrics payload
            metrics = {
                'device_name': 'esp32_device',
                'temperature': temperature,
                'timestamp': int(time.time())
            }
            
            # Create a unique filename with timestamp
            filename = os.path.join(
                self.queue_dir, 
                f"esp32_metrics_{int(time.time())}.json"
            )
            
            # Write metrics to file
            with open(filename, 'w') as f:
                json.dump(metrics, f)
            
            self.logger.info(f"Saved metrics to {filename}")
        except Exception as e:
            self.logger.error(f"Error saving metrics: {e}")

    def run(self):
        """
        Main method to run metrics collection
        """
        self.logger.info(f"Listening on {self.host}:{self.port}")

        try:
            while True:
                data, addr = self.sock.recvfrom(1024)  # Buffer size is 1024 bytes
                try:
                    # Parse received data
                    message = data.decode('utf-8').strip()

                    # Use regex to extract temperature
                    match = re.match(r'Temperature: (\d+\.\d+) C', message)
                    if match:
                        temperature = float(match.group(1))
                        
                        # Save metrics to queue
                        self.save_metrics(temperature)
                        
                        self.logger.info(f"Received from {addr}: {message}")
                    else:
                        self.logger.warning(f"Unrecognized message format: {message}")
                except (ValueError, TypeError) as e:
                    self.logger.error(f"Error processing received data: {e}")
        # Handle keyboard interrupt            
        except KeyboardInterrupt:
            self.logger.info("Exiting...")
        finally:
            self.sock.close()

def main():
    # Create an instance of the ESP32MetricsCollector class
    collector = ESP32MetricsCollector()
    # Run the metrics collection process
    collector.run()

if __name__ == "__main__":
    main()