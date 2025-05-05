import os
import time
import json
import numpy as np
import pandas as pd
from datetime import datetime
from kafka import KafkaProducer
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DataStreamer:
    def __init__(self, bootstrap_servers, topic_name, data_source=None, synthetic=False):
        """
        Initialize the data streamer.
        
        Args:
            bootstrap_servers (str): Kafka bootstrap servers
            topic_name (str): Kafka topic to publish data
            data_source (str, optional): Path to the data source file
            synthetic (bool): Whether to generate synthetic data
        """
        self.bootstrap_servers = bootstrap_servers
        self.topic_name = topic_name
        self.data_source = data_source
        self.synthetic = synthetic
        
        # Initialize Kafka producer
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: str(k).encode('utf-8')
        )
        
        logger.info(f"Connected to Kafka at {bootstrap_servers}")
        logger.info(f"Publishing to topic: {topic_name}")
    
    def generate_synthetic_data(self, length=1500, anomaly_start=1400, seed=42):
        """
        Generate synthetic time series with anomaly.
        """
        np.random.seed(seed)
        time = np.arange(length)
        
        # Base trend and oscillation
        trend = 0.003 * time
        periodic = 0.5 * np.sin(0.02 * time)
        noise = 0.05 * np.random.randn(length)
        
        signal = trend + periodic + noise
        
        # Add anomaly: accelerated growth
        if anomaly_start < length:
            anomaly_time = np.arange(length - anomaly_start)
            anomaly_curve = 0.02 * np.exp(0.05 * anomaly_time)  # exponential growth
            signal[anomaly_start:] += anomaly_curve
        
        data = []
        for i, val in enumerate(signal):
            data.append({
                'timestamp': datetime.now().isoformat(),
                'value': float(val),
                'is_anomaly': i >= anomaly_start
            })
            time.sleep(0.05)  # Small delay between points
        
        return data

    def load_csv_data(self, file_path):
        """
        Load data from CSV file.
        """
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return []
        
        df = pd.read_csv(file_path)
        # Assuming the CSV has timestamp and value columns
        data = []
        
        # Detect anomalies - this is a simplified approach
        # For real applications, use a proper anomaly detection method
        values = df['value'].values
        mean = np.mean(values)
        std = np.std(values)
        threshold = mean + 3 * std  # 3 sigma rule
        
        for _, row in df.iterrows():
            is_anomaly = row['value'] > threshold
            data.append({
                'timestamp': row['timestamp'],
                'value': float(row['value']),
                'is_anomaly': is_anomaly
            })
        
        return data

    def stream_data(self, delay=1.0):
        """
        Stream data to Kafka topic.
        """
        if self.synthetic:
            logger.info("Generating synthetic data")
            data = self.generate_synthetic_data()
        elif self.data_source:
            logger.info(f"Loading data from {self.data_source}")
            data = self.load_csv_data(self.data_source)
        else:
            logger.error("No data source specified")
            return
        
        logger.info(f"Starting to stream {len(data)} data points")
        
        for i, record in enumerate(data):
            # Add metadata
            record['record_id'] = i
            record['streaming_time'] = datetime.now().isoformat()
            
            # Send to Kafka
            self.producer.send(self.topic_name, key=i, value=record)
            logger.debug(f"Sent record {i}: {record}")
            
            # Flush to ensure delivery
            if i % 100 == 0:
                self.producer.flush()
                logger.info(f"Streamed {i} records so far")
            
            # Delay to simulate real-time streaming
            time.sleep(delay)
        
        self.producer.flush()
        logger.info(f"Finished streaming {len(data)} records")

if __name__ == "__main__":
    # Parse command line arguments
    import argparse
    
    parser = argparse.ArgumentParser(description='Stream data to Kafka')
    parser.add_argument('--bootstrap-servers', default='localhost:9092', help='Kafka bootstrap servers')
    parser.add_argument('--topic', default='iot-data', help='Kafka topic to publish data')
    parser.add_argument('--data-source', help='Path to data source file')
    parser.add_argument('--synthetic', action='store_true', help='Generate synthetic data')
    parser.add_argument('--delay', type=float, default=1.0, help='Delay between records (seconds)')
    
    args = parser.parse_args()
    
    # Create streamer and start streaming
    streamer = DataStreamer(
        bootstrap_servers=args.bootstrap_servers,
        topic_name=args.topic,
        data_source=args.data_source,
        synthetic=args.synthetic
    )
    
    streamer.stream_data(delay=args.delay)