import os
import time
import logging
from logging.handlers import RotatingFileHandler
import yaml
import psutil
import requests
import platform
import socket
import json

class MetricsClient:
    def __init__(self, config_path='config.yaml'):
        # Load configuration
        with open(config_path, 'r') as file:
            self.config = yaml.safe_load(file)
        
        # Setup logging
        self.logger = self._setup_logging()
        
        # Construct server URL
        server_config = self.config['server']
        self.server_url = f"{server_config['protocol']}://{server_config['host']}:{server_config['port']}{server_config['endpoint']}"
        
        # Client configuration
        self.client_config = self.config['client']

    def _setup_logging(self):
        # Create logs directory if it doesn't exist
        log_dir = 'logs'
        os.makedirs(log_dir, exist_ok=True)

        # Create logger
        logger = logging.getLogger('metrics_client')
        logger.setLevel(getattr(logging, self.config['logging']['level'].upper()))

        # Console handler
        if self.config['logging']['console']['enabled']:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            logger.addHandler(console_handler)

        # File handler
        if self.config['logging']['file']['enabled']:
            file_handler = RotatingFileHandler(
                os.path.join('logs', 'client.log'), 
                maxBytes=10*1024*1024,  # 10MB
                backupCount=5
            )
            file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            logger.addHandler(file_handler)

        return logger

    def get_system_metrics(self):
        """
        Collect system performance metrics
        
        Returns:
        dict: A dictionary containing system performance metrics
        """
        try:
            # Generate device name with prefix from config
            device_name = f"{self.client_config['device_name_prefix']}-{platform.node()}-{socket.gethostname()}"
            #total number of threads
            total_threads = sum(proc.num_threads() for proc in psutil.process_iter(attrs=['num_threads']))

            
            metrics = {
                'device_name': device_name,
                'num_threads': total_threads,
                'num_processes': len(psutil.pids()),
                'ram_usage_mb': psutil.virtual_memory().used / (1024 * 1024)  # Convert to MB
            }
            
            self.logger.debug(f"Collected metrics: {metrics}")
            return metrics
        except Exception as e:
            self.logger.error(f"Error collecting system metrics: {e}")
            return None

    def send_metrics(self, metrics):
        """
        Send system metrics to the server with retry mechanism
        
        Args:
        metrics (dict): System performance metrics
        """
        for attempt in range(self.client_config['max_retry_attempts']):
            try:
                response = requests.post(
                    self.server_url, 
                    json=metrics, 
                    headers={'Content-Type': 'application/json'},
                    timeout=10  # 10-second timeout
                )
                
                # Parse and log server response
                try:
                    response_data = response.json()
                    self.logger.info(f"Server Response: {json.dumps(response_data, indent=2)}")
                except ValueError:
                    self.logger.warning(f"Received non-JSON response: {response.text}")
                
                # Raise an exception for bad HTTP responses
                response.raise_for_status()
                return True
            
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Error sending metrics (Attempt {attempt + 1}): {e}")
                
                # Wait before retrying
                if attempt < self.client_config['max_retry_attempts'] - 1:
                    time.sleep(self.client_config['retry_delay_seconds'])
        
        self.logger.error("Failed to send metrics after all retry attempts")
        return False

    def run(self):
        """
        Main method to run metrics collection and submission
        """
        self.logger.info("Starting metrics collection and submission...")
        
        try:
            while True:
                # Collect system metrics
                metrics = self.get_system_metrics()
                
                # Send metrics if collection was successful
                if metrics:
                    self.send_metrics(metrics)
                
                # Wait for next interval
                time.sleep(self.client_config['metrics_interval_seconds'])
        
        except KeyboardInterrupt:
            self.logger.info("Metrics collection stopped by user.")
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")

def main():
    client = MetricsClient()
    client.run()

if __name__ == '__main__':
    main()