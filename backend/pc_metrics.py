import os
import time
import logging
from logging.handlers import RotatingFileHandler
import yaml
import psutil
import platform
import socket
import json

class MetricsClient:
    def __init__(self, config_path='config.yaml', queue_dir='metrics_queue'):
        # Load configuration
        with open(config_path, 'r') as file:
            self.config = yaml.safe_load(file)
        
        # Setup logging
        self.logger = self._setup_logging()
        
        # Create queue directory if it doesn't exist
        self.queue_dir = queue_dir
        os.makedirs(self.queue_dir, exist_ok=True)
        
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
            
            # Total number of threads
            total_threads = sum(proc.num_threads() for proc in psutil.process_iter(attrs=['num_threads']))
            
            metrics = {
                'device_name': device_name,
                'num_threads': total_threads,
                'num_processes': len(psutil.pids()),
                'ram_usage_mb': psutil.virtual_memory().used / (1024 * 1024),  # Convert to MB
                'timestamp': int(time.time())
            }
            
            self.logger.debug(f"Collected metrics: {metrics}")
            return metrics
        except Exception as e:
            self.logger.error(f"Error collecting system metrics: {e}")
            return None

    def save_metrics(self, metrics):
        """
        Save metrics to a file in the queue directory
        
        Args:
        metrics (dict): System performance metrics
        """
        if metrics:
            try:
                # Create a unique filename with timestamp
                filename = os.path.join(
                    self.queue_dir, 
                    f"pc_metrics_{int(time.time())}.json"
                )
                
                # Write metrics to file
                with open(filename, 'w') as f:
                    json.dump(metrics, f)
                
                self.logger.info(f"Saved metrics to {filename}")
            except Exception as e:
                self.logger.error(f"Error saving metrics: {e}")

    def run(self):
        """
        Main method to run metrics collection and queueing
        """
        self.logger.info("Starting metrics collection...")
        
        try:
            while True:
                # Collect system metrics
                metrics = self.get_system_metrics()
                
                # Save metrics to queue
                self.save_metrics(metrics)
                
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