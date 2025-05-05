import json
import logging
import threading
from collections import deque
from datetime import datetime
from kafka import KafkaConsumer

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