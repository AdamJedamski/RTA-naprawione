# visualization/dashboard.py
import json
import time
import logging
import numpy as np
import threading
from collections import deque
from kafka import KafkaConsumer
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import Rectangle
import matplotlib.dates as mdates
from datetime import datetime
import pandas as pd
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objs as go
from flask import Flask

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KafkaDataConsumer:
    def __init__(self, bootstrap_servers, raw_topic, predictions_topic, window_size=200):
        """
        Initialize Kafka consumer for raw data and predictions.
        
        Args:
            bootstrap_servers (str): Kafka bootstrap servers
            raw_topic (str): Topic with raw data
            predictions_topic (str): Topic with model predictions
            window_size (int): Number of data points to keep in memory
        """
        self.bootstrap_servers = bootstrap_servers
        self.raw_topic = raw_topic
        self.predictions_topic = predictions_topic
        self.window_size = window_size
        
        # Data storage
        self.timestamps = deque(maxlen=window_size)
        self.actual_values = deque(maxlen=window_size)
        self.predicted_values = deque(maxlen=window_size)
        self.errors = deque(maxlen=window_size)
        self.thresholds = deque(maxlen=window_size)
        self.anomalies = deque(maxlen=window_size)
        
        # Prediction availability flag
        self.predictions_available = False
        
        # Mutex for thread-safe data access
        self.data_lock = threading.Lock()
        
        # Consumers
        self.raw_consumer = KafkaConsumer(
            raw_topic,
            bootstrap_servers=bootstrap_servers,
            value_deserializer=lambda v: json.loads(v.decode('utf-8')),
            auto_offset_reset='latest',
            group_id='dashboard-raw-consumer'
        )
        
        self.predictions_consumer = KafkaConsumer(
            predictions_topic,
            bootstrap_servers=bootstrap_servers,
            value_deserializer=lambda v: json.loads(v.decode('utf-8')),
            auto_offset_reset='latest',
            group_id='dashboard-predictions-consumer'
        )
        
        logger.info(f"Connected to Kafka at {bootstrap_servers}")
        logger.info(f"Consuming raw data from topic: {raw_topic}")
        logger.info(f"Consuming predictions from topic: {predictions_topic}")
    
    def start_consuming(self):
        """
        Start consuming data from Kafka topics.
        """
        # Start consumer threads
        self.raw_thread = threading.Thread(target=self._consume_raw_data, daemon=True)
        self.predictions_thread = threading.Thread(target=self._consume_predictions, daemon=True)
        
        self.raw_thread.start()
        self.predictions_thread.start()
        
        logger.info("Started consuming data from Kafka")
    
    def _consume_raw_data(self):
        """
        Consume raw data from Kafka topic.
        """
        try:
            for message in self.raw_consumer:
                record = message.value
                
                # If predictions are available, we don't need to store raw data separately
                if not self.predictions_available:
                    with self.data_lock:
                        try:
                            timestamp = datetime.fromisoformat(record['timestamp'])
                            self.timestamps.append(timestamp)
                            self.actual_values.append(float(record['value']))
                            # No predictions yet
                            self.predicted_values.append(None)
                            self.errors.append(None)
                            self.thresholds.append(None)
                            self.anomalies.append(None)
                        except Exception as e:
                            logger.error(f"Error processing raw data: {e}")
        except Exception as e:
            logger.error(f"Error in raw data consumer: {e}")
    
    def _consume_predictions(self):
        """
        Consume predictions from Kafka topic.
        """
        try:
            for message in self.predictions_consumer:
                record = message.value
                
                with self.data_lock:
                    try:
                        timestamp = datetime.fromisoformat(record['timestamp'])
                        self.timestamps.append(timestamp)
                        self.actual_values.append(float(record['actual_value']))
                        self.predicted_values.append(float(record['predicted_value']))
                        self.errors.append(float(record['error']))
                        self.thresholds.append(float(record['threshold']))
                        self.anomalies.append(bool(record['is_anomaly']))
                        
                        # Mark that predictions are available
                        self.predictions_available = True
                    except Exception as e:
                        logger.error(f"Error processing prediction data: {e}")
        except Exception as e:
            logger.error(f"Error in predictions consumer: {e}")
    
    def get_data(self):
        """
        Get current data for visualization.
        
        Returns:
            dict: Dictionary with data arrays
        """
        with self.data_lock:
            return {
                'timestamps': list(self.timestamps),
                'actual_values': list(self.actual_values),
                'predicted_values': list(self.predicted_values),
                'errors': list(self.errors),
                'thresholds': list(self.thresholds),
                'anomalies': list(self.anomalies),
                'predictions_available': self.predictions_available
            }


class DashDashboard:
    def __init__(self, kafka_consumer, update_interval=1000):
        """
        Initialize Dash dashboard.
        
        Args:
            kafka_consumer (KafkaDataConsumer): Kafka data consumer
            update_interval (int): Update interval in milliseconds
        """
        self.kafka_consumer = kafka_consumer
        self.update_interval = update_interval
        
        # Initialize Dash app
        self.app = dash.Dash(__name__)
        self.app.title = 'QRC Anomaly Detection Dashboard'
        
        # Define layout
        self.app.layout = html.Div([
            html.H1('Quantum Reservoir Computing - Anomaly Detection Dashboard'),
            
            html.Div([
                html.Div([
                    html.H3('Time Series Data'),
                    dcc.Graph(id='time-series-graph'),
                ], className='six columns'),
                
                html.Div([
                    html.H3('Prediction Error'),
                    dcc.Graph(id='error-graph'),
                ], className='six columns'),
            ], className='row'),
            
            html.Div([
                html.Div([
                    html.H3('Anomaly Detection'),
                    dcc.Graph(id='anomaly-graph'),
                ], className='six columns'),
                
                html.Div([
                    html.H3('Statistics'),
                    html.Div(id='stats-div'),
                ], className='six columns'),
            ], className='row'),
            
            dcc.Interval(
                id='interval-component',
                interval=self.update_interval,
                n_intervals=0
            )
        ])
        
        # Define callbacks
        @self.app.callback(
            [Output('time-series-graph', 'figure'),
             Output('error-graph', 'figure'),
             Output('anomaly-graph', 'figure'),
             Output('stats-div', 'children')],
            [Input('interval-component', 'n_intervals')]
        )
        def update_graphs(n):
            return self._update_graphs()
    
    def _update_graphs(self):
        """
        Update all graphs with current data.
        
        Returns:
            tuple: (time_series_fig, error_fig, anomaly_fig, stats_div)
        """
        # Get current data
        data = self.kafka_consumer.get_data()
        
        # Check if we have any data
        if not data['timestamps']:
            # Return empty figures
            empty_fig = go.Figure()
            empty_fig.update_layout(
                title='Waiting for data...',
                xaxis=dict(title='Time'),
                yaxis=dict(title='Value')
            )
            stats_div = html.Div([
                html.P('Waiting for data...')
            ])
            return empty_fig, empty_fig, empty_fig, stats_div
        
        # Convert timestamps to string for Plotly
        timestamps_str = [ts.isoformat() if ts else None for ts in data['timestamps']]
        
        # Create time series figure
        time_series_fig = go.Figure()
        
        # Add actual values
        time_series_fig.add_trace(go.Scatter(
            x=timestamps_str,
            y=data['actual_values'],
            mode='lines',
            name='Actual'
        ))
        
        # Add predicted values if available
        if data['predictions_available']:
            time_series_fig.add_trace(go.Scatter(
                x=timestamps_str,
                y=data['predicted_values'],
                mode='lines',
                name='Predicted',
                line=dict(dash='dash')
            ))
        
        # Add anomaly points if available
        if data['predictions_available']:
            # Find indices of anomalies
            anomaly_indices = [i for i, is_anomaly in enumerate(data['anomalies']) if is_anomaly]
            
            if anomaly_indices:
                time_series_fig.add_trace(go.Scatter(
                    x=[timestamps_str[i] for i in anomaly_indices],
                    y=[data['actual_values'][i] for i in anomaly_indices],
                    mode='markers',
                    name='Anomalies',
                    marker=dict(color='red', size=10, symbol='x')
                ))
        
        time_series_fig.update_layout(
            title='Time Series Data',
            xaxis=dict(title='Time'),
            yaxis=dict(title='Value'),
            legend=dict(x=0, y=1, orientation='h')
        )
        
        # Create error figure
        error_fig = go.Figure()
        
        if data['predictions_available']:
            # Add error
            error_fig.add_trace(go.Scatter(
                x=timestamps_str,
                y=data['errors'],
                mode='lines',
                name='Error',
                line=dict(color='blue')
            ))
            
            # Add threshold
            error_fig.add_trace(go.Scatter(
                x=timestamps_str,
                y=data['thresholds'],
                mode='lines',
                name='Threshold',
                line=dict(color='red', dash='dash')
            ))
            
            # Find indices of anomalies
            anomaly_indices = [i for i, is_anomaly in enumerate(data['anomalies']) if is_anomaly]
            
            if anomaly_indices:
                error_fig.add_trace(go.Scatter(
                    x=[timestamps_str[i] for i in anomaly_indices],
                    y=[data['errors'][i] for i in anomaly_indices],
                    mode='markers',
                    name='Anomalies',
                    marker=dict(color='red', size=10, symbol='x')
                ))
        
        error_fig.update_layout(
            title='Prediction Error',
            xaxis=dict(title='Time'),
            yaxis=dict(title='Error'),
            legend=dict(x=0, y=1, orientation='h')
        )
        
        # Create anomaly detection figure
        anomaly_fig = go.Figure()
        
        if data['predictions_available']:
            # Create binary anomaly signal
            anomaly_signal = [1 if a else 0 for a in data['anomalies']]
            
            anomaly_fig.add_trace(go.Scatter(
                x=timestamps_str,
                y=anomaly_signal,
                mode='lines',
                name='Anomaly Signal',
                fill='tozeroy',
                line=dict(color='red')
            ))
        
        anomaly_fig.update_layout(
            title='Anomaly Detection',
            xaxis=dict(title='Time'),
            yaxis=dict(title='Anomaly (1=Yes, 0=No)'),
            legend=dict(x=0, y=1, orientation='h')
        )
        
        # Create statistics div
        stats_div = html.Div([
            html.H4('Current Statistics'),
            html.Table([
                html.Tr([html.Td('Data Points:'), html.Td(str(len(data['timestamps'])))]),
                html.Tr([html.Td('Latest Value:'), html.Td(f"{data['actual_values'][-1]:.4f}")]),
                html.Tr([html.Td('Latest Prediction:'), 
                         html.Td(f"{data['predicted_values'][-1]:.4f}" if data['predictions_available'] else 'N/A')]),
                html.Tr([html.Td('Latest Error:'), 
                         html.Td(f"{data['errors'][-1]:.4f}" if data['predictions_available'] else 'N/A')]),
                html.Tr([html.Td('Current Threshold:'), 
                         html.Td(f"{data['thresholds'][-1]:.4f}" if data['predictions_available'] else 'N/A')]),
                html.Tr([html.Td('Anomalies Detected:'), 
                         html.Td(str(sum(1 for a in data['anomalies'] if a)) if data['predictions_available'] else 'N/A')]),
                html.Tr([html.Td('Latest Status:'), 
                         html.Td(html.Span('ANOMALY DETECTED', style={'color': 'red', 'font-weight': 'bold'}) 
                                if data['predictions_available'] and data['anomalies'][-1] 
                                else html.Span('Normal', style={'color': 'green'}))]),
            ])
        ])
        
        return time_series_fig, error_fig, anomaly_fig, stats_div
    
    def run(self, host='0.0.0.0', port=8050, debug=False):
        """
        Run the Dash app.
        
        Args:
            host (str): Host to run the app on
            port (int): Port to run the app on
            debug (bool): Whether to run in debug mode
        """
        # Start Kafka consumer
        self.kafka_consumer.start_consuming()
        
        # Run Dash app
        self.app.run_server(host=host, port=port, debug=debug)


if __name__ == "__main__":
    # Parse command line arguments
    import argparse
    
    parser = argparse.ArgumentParser(description='Real-time visualization dashboard')
    parser.add_argument('--bootstrap-servers', default='localhost:9092', help='Kafka bootstrap servers')
    parser.add_argument('--raw-topic', default='iot-data', help='Kafka topic with raw data')
    parser.add_argument('--predictions-topic', default='qrc-predictions', help='Kafka topic with predictions')
    parser.add_argument('--window-size', type=int, default=200, help='Number of data points to keep in memory')
    parser.add_argument('--update-interval', type=int, default=1000, help='Update interval in milliseconds')
    parser.add_argument('--host', default='0.0.0.0', help='Host to run the app on')
    parser.add_argument('--port', type=int, default=8050, help='Port to run the app on')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    
    args = parser.parse_args()
    
    # Create Kafka consumer
    consumer = KafkaDataConsumer(
        bootstrap_servers=args.bootstrap_servers,
        raw_topic=args.raw_topic,
        predictions_topic=args.predictions_topic,
        window_size=args.window_size
    )
    
    # Create and run dashboard
    dashboard = DashDashboard(consumer, args.update_interval)
    dashboard.run(args.host, args.port, args.debug)