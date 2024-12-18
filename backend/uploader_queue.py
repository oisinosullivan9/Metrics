# Description: This script reads metrics files from the queue directory and sends them to the server.
# The script is designed to run continuously and process the queue at regular intervals.
# The script reads metrics files from the queue directory, determines the endpoint based on the filename, and sends the metrics to the server.
# The script logs the processing of each file and any errors that occur during processing.

import os
import time
import json
import logging
import requests
import yaml

class MetricsUploader:
    def __init__(self, config_path='config.yaml', queue_dir='metrics_queue'):
        # Load configuration
        with open(config_path, 'r') as file:
            self.config = yaml.safe_load(file)
        
        # Setup logging
        self.logger = self._setup_logging()
        
        # Queue directory
        self.queue_dir = queue_dir
        
        # Server endpoints
        self.server_endpoints = {
            'pc': self.config['server']['pc_metrics_endpoint'],
            'esp32': self.config['server']['esp32_metrics_endpoint']
        }

    def _setup_logging(self):
        # Create logs directory if it doesn't exist
        log_dir = 'logs'
        os.makedirs(log_dir, exist_ok=True)

        # Create logger
        logger = logging.getLogger('metrics_uploader')
        logger.setLevel(logging.INFO)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(console_handler)

        # File handler
        file_handler = logging.FileHandler(os.path.join(log_dir, 'uploader.log'))
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(file_handler)

        return logger

    def send_metrics(self, file_path, endpoint):
        """
        Send metrics to the specified endpoint
        
        Args:
        file_path (str): Path to the metrics file
        endpoint (str): URL to send metrics to
        
        Returns:
        bool: True if successful, False otherwise
        """
        try:
            # Read metrics from file
            with open(file_path, 'r') as f:
                metrics = json.load(f)
            
            # Send metrics
            response = requests.post(
                endpoint, 
                json=metrics, 
                headers={'Content-Type': 'application/json'},
                timeout=5  # 10-second timeout
            )
            
            # Check response
            if response.status_code in [200, 201]:
                self.logger.info(f"Successfully uploaded metrics from {file_path}")
                return True
            else:
                self.logger.error(f"Failed to upload metrics. Status code: {response.status_code}")
                return False
        
        except Exception as e:
            self.logger.error(f"Error uploading metrics from {file_path}: {e}")
            return False

    def process_queue(self):
        """
        Process metrics files in the queue directory
        """
        try:
            # Iterate through files in queue directory
            for filename in sorted(os.listdir(self.queue_dir)):
                file_path = os.path.join(self.queue_dir, filename)
                
                # Determine endpoint based on filename
                if 'pc_metrics' in filename:
                    endpoint = self.server_endpoints['pc']
                elif 'esp32_metrics' in filename:
                    endpoint = self.server_endpoints['esp32']
                else:
                    self.logger.warning(f"Unrecognized metrics file: {filename}")
                    continue
                
                # Attempt to send metrics
                if self.send_metrics(file_path, endpoint):
                    # Remove file if successfully uploaded
                    os.remove(file_path)
        
        except Exception as e:
            self.logger.error(f"Error processing queue: {e}")

    def run(self, interval=20):
        """
        Continuously process the metrics queue
        
        Args:
        interval (int): Time between queue processing attempts (in seconds)
        """
        self.logger.info("Starting metrics uploader...")
        
        try:
            while True:
                # Process metrics queue
                self.process_queue()
                
                # Wait before next processing
                time.sleep(interval)
        
        except KeyboardInterrupt:
            self.logger.info("Metrics uploader stopped by user.")
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")

def main():
    uploader = MetricsUploader()
    uploader.run()

if __name__ == '__main__':
    main()