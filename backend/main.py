import os
import logging
from logging.handlers import RotatingFileHandler
import yaml
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.sql import func

# Load configuration
def load_config(config_path='config.yaml'):
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)

# Configure logging
def setup_logging(config):
    # Create logs directory if it doesn't exist
    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)

    # Create logger
    logger = logging.getLogger('performance_tracker')
    logger.setLevel(getattr(logging, config['logging']['level'].upper()))

    # Console handler
    if config['logging']['console']['enabled']:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(console_handler)

    # File handler
    if config['logging']['file']['enabled']:
        file_handler = RotatingFileHandler(
            config['logging']['file']['path'], 
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(file_handler)

    return logger

# Load config
config = load_config()

# Setup Flask and SQLAlchemy
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{config['database']['path']}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Setup logging
logger = setup_logging(config)

# ORM Model for Device Performance
class DevicePerformanceSnapshot(db.Model):
    __tablename__ = 'device_performance_snapshot'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    device_name = Column(String(255), nullable=False)
    timestamp = Column(DateTime, default=func.now())
    num_threads = Column(Integer, nullable=False)
    num_processes = Column(Integer, nullable=False)
    ram_usage_mb = Column(Float, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'device_name': self.device_name,
            'timestamp': self.timestamp.isoformat(),
            'num_threads': self.num_threads,
            'num_processes': self.num_processes,
            'ram_usage_mb': self.ram_usage_mb
        }

# Ensure database and tables are created
with app.app_context():
    db.create_all()

# Endpoint to receive performance metrics
@app.route('/metrics', methods=['POST'])
def receive_metrics():
    try:
        # Validate incoming JSON data
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['device_name', 'num_threads', 'num_processes', 'ram_usage_mb']
        for field in required_fields:
            if field not in data:
                logger.warning(f'Missing required field: {field}')
                return jsonify({
                    'status': 'error', 
                    'message': f'Missing required field: {field}'
                }), 400
        
        # Create new snapshot
        new_snapshot = DevicePerformanceSnapshot(
            device_name=data['device_name'],
            num_threads=data['num_threads'],
            num_processes=data['num_processes'],
            ram_usage_mb=data['ram_usage_mb']
        )
        
        # Add and commit to database
        db.session.add(new_snapshot)
        db.session.commit()
        
        logger.info(f'Metrics recorded for device: {data["device_name"]}')
        
        return jsonify({
            'status': 'success', 
            'message': 'Metrics recorded',
            'snapshot': new_snapshot.to_dict()
        }), 201
    
    except Exception as e:
        # Rollback in case of error
        db.session.rollback()
        logger.error(f'Error receiving metrics: {str(e)}')
        return jsonify({
            'status': 'error', 
            'message': str(e)
        }), 500

# Endpoint to retrieve metrics
@app.route('/metrics', methods=['GET'])
def get_metrics():
    try:
        # Optional query parameters
        device_name = request.args.get('device_name')
        limit = request.args.get('limit', default=100, type=int)
        
        # Query snapshots
        if device_name:
            snapshots = DevicePerformanceSnapshot.query \
                .filter_by(device_name=device_name) \
                .order_by(DevicePerformanceSnapshot.timestamp.desc()) \
                .limit(limit) \
                .all()
        else:
            snapshots = DevicePerformanceSnapshot.query \
                .order_by(DevicePerformanceSnapshot.timestamp.desc()) \
                .limit(limit) \
                .all()
        
        logger.info(f'Retrieved {len(snapshots)} metrics{"" if device_name is None else f" for device {device_name}"}')
        
        return jsonify({
            'status': 'success',
            'metrics': [snapshot.to_dict() for snapshot in snapshots]
        }), 200
    
    except Exception as e:
        logger.error(f'Error retrieving metrics: {str(e)}')
        return jsonify({
            'status': 'error', 
            'message': str(e)
        }), 500

if __name__ == '__main__':
    # Get server configuration from config
    server_config = config['server']
    
    logger.info(f"Starting server on {server_config['host']}:{server_config['port']}")
    app.run(
        debug=True, 
        host=server_config['host'], 
        port=server_config['port']
    )