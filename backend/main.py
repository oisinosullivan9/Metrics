import os
import logging
from logging.handlers import RotatingFileHandler
import yaml
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.sql import func
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objs as go

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
            maxBytes=10*1024*1024, # 10MB
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

# Updated ORM Model to include both device performance and ESP32 temperature
class DevicePerformanceSnapshot(db.Model):
    __tablename__ = 'device_performance_snapshot'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    device_name = Column(String(255), nullable=False)
    timestamp = Column(DateTime, default=func.now())
    
    # Laptop/System Metrics
    num_threads = Column(Integer, nullable=True)
    num_processes = Column(Integer, nullable=True)
    ram_usage_mb = Column(Float, nullable=True)
    
    # ESP32 Metrics
    temperature = Column(Float, nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'device_name': self.device_name,
            'timestamp': self.timestamp.isoformat(),
            'num_threads': self.num_threads,
            'num_processes': self.num_processes,
            'ram_usage_mb': self.ram_usage_mb,
            'temperature': self.temperature
        }

# Ensure database and tables are created
with app.app_context():
    db.create_all()

# Updated metrics endpoint to handle both system and ESP32 metrics
@app.route('/metrics', methods=['POST'])
def receive_metrics():
    try:
        # Validate incoming data
        data = request.get_json()
        
        # Check for required device_name field
        if 'device_name' not in data:
            logger.warning('Missing required field: device_name')
            return jsonify({'status': 'error', 'message': 'Missing required field: device_name'}), 400
        
        # Create a new snapshot
        new_snapshot = DevicePerformanceSnapshot(
            device_name=data['device_name'],
            # Laptop/System Metrics (optional)
            num_threads=data.get('num_threads'),
            num_processes=data.get('num_processes'),
            ram_usage_mb=data.get('ram_usage_mb'),
            # ESP32 Metrics (optional)
            temperature=data.get('temperature')
        )
        
        db.session.add(new_snapshot)
        db.session.commit()
        logger.info(f'Metrics recorded for device: {data["device_name"]}')
        return jsonify({'status': 'success', 'message': 'Metrics recorded', 'snapshot': new_snapshot.to_dict()}), 201
    
    except Exception as e:
        # Rollback the session in case of an error
        db.session.rollback()
        logger.error(f'Error receiving metrics: {str(e)}')
        return jsonify({'status': 'error', 'message': str(e)}), 500

dash_app = dash.Dash(__name__, server=app, url_base_pathname='/dashboard/')
# Updated dashboard layout to include temperature
dash_app.layout = html.Div([
        html.H1("Device Performance Dashboard"),
    html.Div([
        html.H2("Gauge Chart for Device Metrics"),
        html.Div([
            html.Div([
                html.Label("Select a device:"),
                dcc.Dropdown(
                    id='device-dropdown',
                    placeholder="Select a device",
                    style={'width': '100%'}
                )
            ], style={'width': '50%', 'padding': '0 10px'}),
            html.Div([
                html.Label("Select a metric:"),
                dcc.Dropdown(
                    id='metric-dropdown-gauge',
                    options=[
                        {'label': 'RAM Usage (MB)', 'value': 'ram_usage_mb'},
                        {'label': 'Num Threads', 'value': 'num_threads'},
                        {'label': 'Num Processes', 'value': 'num_processes'}
                    ],
                    placeholder="Select a metric",
                    style={'width': '100%'}
                )
            ], style={'width': '50%', 'padding': '0 10px'}),
        ], style={'display': 'flex', 'gap': '10px'}),
        dcc.Graph(id='gauge-chart'),
    ]),
    html.Div([
        html.H2("Device Metrics Table"),
        dcc.Interval(
            id='interval-component',
            interval=5*1000,  # Update every 5 seconds
            n_intervals=0
        ),
        html.Div(id='table-container'),
    ]),
    html.Div([
        html.H2("Device Metrics History"),
        dcc.Dropdown(
            id='metric-dropdown',
            options=[
                {'label': 'RAM Usage (MB)', 'value': 'ram_usage_mb'},
                {'label': 'Num Threads', 'value': 'num_threads'},
                {'label': 'Num Processes', 'value': 'num_processes'},
                {'label': 'Temperature (°C)', 'value': 'temperature'}  # New option
            ],
            placeholder="Select a metric",
        ),
        dcc.Graph(id='line-graph'),
    ])
])

# Updated line graph callback to support temperature
@dash_app.callback(
    Output('line-graph', 'figure'),
    [Input('metric-dropdown', 'value'),
     Input('device-dropdown', 'value')]
)
def update_line_graph(selected_metric, device_name):
    if not device_name or not selected_metric:
        return go.Figure()

    snapshots = DevicePerformanceSnapshot.query \
        .filter_by(device_name=device_name) \
        .order_by(DevicePerformanceSnapshot.timestamp.asc()) \
        .all()

    if not snapshots:
        return go.Figure()

    timestamps = [snapshot.timestamp for snapshot in snapshots]
    values = [getattr(snapshot, selected_metric) for snapshot in snapshots]

    # Special handling for temperature to add °C
    title = selected_metric.replace('_', ' ').title()
    if selected_metric == 'temperature':
        title += ' (°C)'

    figure = go.Figure(
        data=go.Scatter(x=timestamps, y=values, mode='lines+markers', name=selected_metric),
        layout=go.Layout(
            title=f"{title} Over Time for {device_name}",
            xaxis=dict(title="Time"),
            yaxis=dict(title=title),
        )
    )

    return figure

# Update dashboard callbacks to support temperature
@dash_app.callback(
    Output('gauge-chart', 'figure'),
    [Input('device-dropdown', 'value'),
     Input('metric-dropdown-gauge', 'value')]
)
def update_gauge(device_name, selected_metric):
    if not device_name or not selected_metric:
        return go.Figure()

    snapshot = DevicePerformanceSnapshot.query \
        .filter_by(device_name=device_name) \
        .order_by(DevicePerformanceSnapshot.timestamp.desc()) \
        .first()
    
    if not snapshot:
        return go.Figure()
    
    # Determine the value and range based on the selected metric
    metric_configs = {
        'ram_usage_mb': {
            'range': [0, 16000],
            'steps': [
                {'range': [0, 6000], 'color': "lightgreen"},
                {'range': [6000, 10000], 'color': "yellow"},
                {'range': [10000, 16000], 'color': "red"}
            ],
            'title': "RAM Usage (MB)"
        },
        'num_threads': {
            'range': [0, 10000],
            'steps': [
                {'range': [0, 2500], 'color': "lightgreen"},
                {'range': [2500, 5000], 'color': "yellow"},
                {'range': [5000, 10000], 'color': "red"}
            ],
            'title': "Number of Threads"
        },
        'num_processes': {
            'range': [0, 500],
            'steps': [
                {'range': [0, 200], 'color': "lightgreen"},
                {'range': [200, 400], 'color': "yellow"},
                {'range': [400, 500], 'color': "red"}
            ],
            'title': "Number of Processes"
        },
        'temperature': {
            'range': [0, 100],
            'steps': [
                {'range': [0, 30], 'color': "lightgreen"},
                {'range': [30, 60], 'color': "yellow"},
                {'range': [60, 100], 'color': "red"}
            ],
            'title': "Temperature (°C)"
        }
    }

    config = metric_configs.get(selected_metric, {})
    value = getattr(snapshot, selected_metric)

    figure = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            title={'text': config.get('title', selected_metric)},
            gauge={
                'axis': {'range': config.get('range', [0, 100])},
                'bar': {'color': "blue"},
                'steps': config.get('steps', [])
            }
        )
    )
    return figure

if __name__ == '__main__':
    server_config = config['server']
    logger.info(f"Starting server on {server_config['host']}:{server_config['port']}")
    app.run(debug=True, host=server_config['host'], port=server_config['port'])
