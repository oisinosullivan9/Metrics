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

#new ORM model for esp32 temperature metrics
class ESP32TemperatureSnapshot(db.Model):
    __tablename__ = 'esp32_temperature_snapshot'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    device_name = Column(String(255), nullable=False)
    timestamp = Column(DateTime, default=func.now())
    temperature = Column(Float, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'device_name': self.device_name,
            'timestamp': self.timestamp.isoformat(),
            'temperature': self.temperature,
        }
    
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

# Flask endpoints
@app.route('/metrics', methods=['POST'])
def receive_metrics():
    try:
        #validate incoming data
        data = request.get_json()
        # Check for required fields
        required_fields = ['device_name', 'num_threads', 'num_processes', 'ram_usage_mb']
        for field in required_fields:
            if field not in data:
                logger.warning(f'Missing required field: {field}')
                return jsonify({'status': 'error', 'message': f'Missing required field: {field}'}), 400
        # Create a new snapshot
        new_snapshot = DevicePerformanceSnapshot(
            device_name=data['device_name'],
            num_threads=data['num_threads'],
            num_processes=data['num_processes'],
            ram_usage_mb=data['ram_usage_mb']
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

@app.route('/metrics', methods=['GET'])
def get_metrics():
    try:
        #optional query parameters to filter and limit the results
        device_name = request.args.get('device_name')
        limit = request.args.get('limit', default=100, type=int)
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
        
        logger.info(f'Retrieved {len(snapshots)} metrics{" for device " + device_name if device_name else ""}')
        return jsonify({'status': 'success', 'metrics': [snapshot.to_dict() for snapshot in snapshots]}), 200
    
    except Exception as e:
        logger.error(f'Error retrieving metrics: {str(e)}')
        return jsonify({'status': 'error', 'message': str(e)}), 500

# New endpoint for ESP32 metrics
@app.route('/esp32metrics', methods=['POST'])
def receive_esp32_metrics():
    try:
        # Validate incoming data
        data = request.get_json()
        
        # Check for required fields
        required_fields = ['temperature']
        for field in required_fields:
            if field not in data:
                logger.warning(f'Missing required field: {field}')
                return jsonify({'status': 'error', 'message': f'Missing required field: {field}'}), 400
        
        # Create a new temperature snapshot
        new_snapshot = ESP32TemperatureSnapshot(
            device_name = data.get('device_name', 'ESP32'),
            temperature=data['temperature']
        )
        db.session.add(new_snapshot)
        db.session.commit()
        
        logger.info(f'Temperature metrics recorded')
        return jsonify({'status': 'success', 'message': 'Temperature metrics recorded', 'snapshot': new_snapshot.to_dict()}), 201
    
    except Exception as e:
        # Rollback the session in case of an error
        db.session.rollback()
        logger.error(f'Error receiving ESP32 metrics: {str(e)}')
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
# New endpoint to retrieve ESP32 metrics
@app.route('/esp32metrics', methods=['GET'])
def get_esp32_metrics():
    try:
        # Optional query parameters to filter and limit the results
        device_name = request.args.get('device_name')
        limit = request.args.get('limit', default=100, type=int)
        
        if device_name:
            snapshots = ESP32TemperatureSnapshot.query \
                .filter_by(device_name=device_name) \
                .order_by(ESP32TemperatureSnapshot.timestamp.desc()) \
                .limit(limit) \
                .all()
        else:
            snapshots = ESP32TemperatureSnapshot.query \
                .order_by(ESP32TemperatureSnapshot.timestamp.desc()) \
                .limit(limit) \
                .all()
        
        logger.info(f'Retrieved {len(snapshots)} ESP32 temperature metrics{" for device " + device_name if device_name else ""}')
        return jsonify({'status': 'success', 'metrics': [snapshot.to_dict() for snapshot in snapshots]}), 200
    
    except Exception as e:
        logger.error(f'Error retrieving ESP32 metrics: {str(e)}')
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
# Integrate Dash with Flask
dash_app = dash.Dash(__name__, server=app, url_base_pathname='/dashboard/')

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
                {'label': 'ESP32 Temperature', 'value': 'temperature'}
            ],
            placeholder="Select a metric",
        ),
        dcc.Graph(id='line-graph'),
    ])
])
# Callback to populate the dropdown with device names
@dash_app.callback(
    Output('device-dropdown', 'options'),
    Input('interval-component', 'n_intervals')  # Periodically refresh device names
)
def update_device_dropdown(_):
    # Combine device names from both performance and temperature snapshots
    performance_devices = db.session.query(DevicePerformanceSnapshot.device_name).distinct().all()
    temperature_devices = db.session.query(ESP32TemperatureSnapshot.device_name).distinct().all()
    
    # Combine and remove duplicates
    all_devices = set(device[0] for device in performance_devices + temperature_devices)
    
    return [{'label': name, 'value': name} for name in all_devices]

# Callback to update the gauge chart
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

# Callback to update the table dynamically
@dash_app.callback(
    Output('table-container', 'children'),
    Input('interval-component', 'n_intervals')
)
def update_table(_):
    snapshots = DevicePerformanceSnapshot.query.order_by(DevicePerformanceSnapshot.timestamp.desc()).all()
    if not snapshots:
        return html.Div("No data available.")

    table_data = {
        "ID": [snapshot.id for snapshot in snapshots],
        "Device Name": [snapshot.device_name for snapshot in snapshots],
        "Timestamp": [snapshot.timestamp.strftime('%Y-%m-%d %H:%M:%S') for snapshot in snapshots],
        "Num Threads": [snapshot.num_threads for snapshot in snapshots],
        "Num Processes": [snapshot.num_processes for snapshot in snapshots],
        "RAM Usage (MB)": [snapshot.ram_usage_mb for snapshot in snapshots],
    }

    return dcc.Graph(
        figure=go.Figure(
            data=[
                go.Table(
                    header=dict(
                        values=list(table_data.keys()),
                        fill_color='paleturquoise',
                        align='left'
                    ),
                    cells=dict(
                        values=list(table_data.values()),
                        fill_color='lavender',
                        align='left'
                    )
                )
            ]
        )
    )

# Callback to update the line graph
@dash_app.callback(
    Output('line-graph', 'figure'),
    [Input('metric-dropdown', 'value'),
     Input('device-dropdown', 'value')]
)
def update_line_graph(selected_metric, device_name):
    if not device_name or not selected_metric:
        return go.Figure()
    
    #Handle ESP32 temperature metrics
    if selected_metric == 'temperature':
        snapshots = ESP32TemperatureSnapshot.query \
            .filter_by(device_name=device_name) \
            .order_by(ESP32TemperatureSnapshot.timestamp.asc()) \
            .all()
    else:    
        snapshots = DevicePerformanceSnapshot.query \
            .filter_by(device_name=device_name) \
            .order_by(DevicePerformanceSnapshot.timestamp.asc()) \
            .all()

    if not snapshots:
        return go.Figure()
    
    if selected_metric == 'temperature':
        timestamps = [snapshot.timestamp for snapshot in snapshots]
        values = [snapshot.temperature for snapshot in snapshots]
        metric_title = "ESP32 Temperature"
    else:
        timestamps = [snapshot.timestamp for snapshot in snapshots]
        values = [getattr(snapshot, selected_metric) for snapshot in snapshots]
        metric_title = selected_metric.replace('_', ' ').title()

    figure = go.Figure(
        data=go.Scatter(x=timestamps, y=values, mode='lines+markers', name=selected_metric),
        layout=go.Layout(
            title=f"{metric_title} Over Time for {device_name}",
            xaxis=dict(title="Time"),
            yaxis=dict(title=selected_metric.replace('_', ' ').title()),
        )
    )

    return figure

if __name__ == '__main__':
    server_config = config['server']
    logger.info(f"Starting server on {server_config['host']}:{server_config['port']}")
    app.run(debug=True, host=server_config['host'], port=server_config['port'])
