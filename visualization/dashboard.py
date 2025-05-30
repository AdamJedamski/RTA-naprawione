import logging
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objs as go



logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
        def update_graphs(_):
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
        
                ## Create “Prediction vs Threshold” figure (zamiast starego wykresu błędu)
        error_fig = go.Figure()

        if data['predictions_available']:
            # Wykres prognoz
            error_fig.add_trace(go.Scatter(
                x=timestamps_str,
                y=data['predicted_values'],
                mode='lines',
                name='Predicted',
                line=dict(dash='dash')
            ))

            # Poziom progu (z każdego rekordu Kafka)
            error_fig.add_trace(go.Scatter(
                x=timestamps_str,
                y=data['thresholds'],
                mode='lines',
                name='Threshold',
                line=dict(dash='dash')
            ))
    
            # Markery tam, gdzie prognoza > próg
            anomaly_indices = [i for i, a in enumerate(data['anomalies']) if a]
            if anomaly_indices:
                error_fig.add_trace(go.Scatter(
                    x=[timestamps_str[i] for i in anomaly_indices],
                    y=[data['predicted_values'][i] for i in anomaly_indices],
                    mode='markers',
                    name='Anomalies',
                    marker=dict(color='red', size=10, symbol='x')
                ))

        error_fig.update_layout(
            title='Prediction vs Threshold',
            xaxis=dict(title='Time'),
            yaxis=dict(title='Value'),
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