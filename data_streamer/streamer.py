import os
import time
import json
import logging
import pandas as pd
from datetime import datetime
from kafka import KafkaProducer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DataStreamer:
    def __init__(self, bootstrap_servers, topic_name, data_source):
        """
        Initialize the data streamer.
        
        Args:
            bootstrap_servers (str): Kafka bootstrap servers
            topic_name (str): Kafka topic to publish data
            data_source (str): Path to the data source file
        """
        self.bootstrap_servers = bootstrap_servers
        self.topic_name = topic_name
        self.data_source = data_source
        
        # Initialize Kafka producer
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: str(k).encode('utf-8')
        )
        
        logger.info(f"Connected to Kafka at {bootstrap_servers}")
        logger.info(f"Publishing to topic: {topic_name}")

    def load_csv_data(self, file_path):
        """
        Load data from CSV file.
        """
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return []
        
        df = pd.read_csv(file_path)
        logger.info(f"Loaded {len(df)} records from {file_path}")
        
        data = []
        for _, row in df.iterrows():
            data.append({
                'timestamp': row['timestamp'],
                'value': float(row['value'])
            })
        
        return data

    def stream_data(self, delay=1.0):
        """
        Stream data to Kafka topic.
        """
        logger.info(f"Loading data from {self.data_source}")
        data = self.load_csv_data(self.data_source)
        
        if not data:
            logger.error("No data to stream")
            return
        
        logger.info(f"Starting to stream {len(data)} data points")
        
        for i, record in enumerate(data):
            # Add metadata
            record['record_id'] = i
            record['streaming_time'] = datetime.now().isoformat()
            
            # Send to Kafka
            self.producer.send(self.topic_name, key=i, value=record)
            
            # Flush periodically
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
    parser.add_argument('--data-source', required=True, help='Path to data source file')
    parser.add_argument('--delay', type=float, default=0.05, help='Delay between records (seconds)')
    
    args = parser.parse_args()
    
    # Create streamer and start streaming
    streamer = DataStreamer(
        bootstrap_servers=args.bootstrap_servers,
        topic_name=args.topic,
        data_source=args.data_source
    )
    
    streamer.stream_data(delay=args.delay)