import logging
import json
import numpy as np
from collections import deque
from kafka import KafkaConsumer, KafkaProducer
from model import QuantumReservoirModel
from config import DEFAULT_KAFKA_PARAMS, DEFAULT_TRAINING_PARAMS, DEFAULT_QRC_PARAMS

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class QRCKafkaHandler:
    def __init__(self, bootstrap_servers=DEFAULT_KAFKA_PARAMS['bootstrap_servers'], 
                 input_topic=DEFAULT_KAFKA_PARAMS['input_topic'], 
                 output_topic=DEFAULT_KAFKA_PARAMS['output_topic'], 
                 window_size=DEFAULT_TRAINING_PARAMS['window_size']):
        """
        Initialize the Kafka handler for QRC model.
        
        Args:
            bootstrap_servers (str): Kafka bootstrap servers
            input_topic (str): Topic to consume data from
            output_topic (str): Topic to publish predictions to
            window_size (int): Window size for input sequences
        """
        self.bootstrap_servers = bootstrap_servers
        self.input_topic = input_topic
        self.output_topic = output_topic
        self.window_size = window_size
        
        # Initialize Kafka consumer and producer
        self.consumer = KafkaConsumer(
            input_topic,
            bootstrap_servers=bootstrap_servers,
            value_deserializer=lambda v: json.loads(v.decode('utf-8')),
            auto_offset_reset='earliest',
            group_id=DEFAULT_KAFKA_PARAMS['consumer_group']
        )
        
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        
        # Initialize model
        self.model = None
        self.buffer = deque(maxlen=window_size)
        self.training_data = []
        self.training_complete = False
        
        logger.info(f"Connected to Kafka at {bootstrap_servers}")
        logger.info(f"Consuming from topic: {input_topic}")
        logger.info(f"Publishing to topic: {output_topic}")
        
    def train_model(self, n_qubits=DEFAULT_QRC_PARAMS['n_qubits'], 
                    n_layers=DEFAULT_QRC_PARAMS['n_layers'], 
                    train_size=DEFAULT_TRAINING_PARAMS['train_size']):
        """
        Collect training data and train the QRC model.
        """
        logger.info(f"Collecting {train_size} samples for training")
        self.training_data = []
        
        # Collect training data
        for _ in range(train_size):
            message = next(self.consumer)
            value = float(message.value['value'])
            self.training_data.append(value)
            
            # Update progress
            if len(self.training_data) % 100 == 0:
                logger.info(f"Collected {len(self.training_data)}/{train_size} training samples")
        
        logger.info(f"Collected {len(self.training_data)} training samples")
        
        # Prepare input-output pairs
        X_train, y_train = self._create_io_pairs(self.training_data, self.window_size)
        
        # Initialize and train model
        self.model = QuantumReservoirModel(n_qubits=n_qubits, n_layers=n_layers)
        self.model.fit(X_train, y_train)
        
        self.training_complete = True
        logger.info("Model training completed")
        
        # Save the trained model
        self.model.save_model("qrc_model.npz")
        
        return self.model
    
    def _create_io_pairs(self, data, window_size):
        """
        Create input-output pairs for training/testing.
        """
        inputs = []
        outputs = []
        for i in range(len(data) - window_size):
            inputs.append(data[i:i + window_size])
            outputs.append(data[i + window_size])
        return np.array(inputs), np.array(outputs)
    
    def process_stream(self):
        """
        Process the data stream in real-time.
        """
        if not self.training_complete:
            logger.error("Model must be trained before processing the stream")
            return
        
        logger.info("Starting to process streaming data")
        
        for message in self.consumer:
            # Extract data
            record = message.value
            value = float(record['value'])
            
            # Add to buffer
            self.buffer.append(value)
            
            # If buffer is full, make prediction
            if len(self.buffer) == self.window_size:
                input_seq = np.array(list(self.buffer))
                
                # Detect anomalies
                prediction, error, is_anomaly = self.model.detect_anomalies(input_seq, value)
                
                # Prepare output record
                output_record = {
                    'timestamp': record['timestamp'],
                    'streaming_time': record['streaming_time'],
                    'record_id': record['record_id'],
                    'actual_value': value,
                    'predicted_value': float(prediction),
                    'error': float(error),
                    'is_anomaly': bool(is_anomaly),
                    'threshold': float(self.model.error_threshold)
                }
                
                # Send to output topic
                self.producer.send(self.output_topic, value=output_record)
                
                # Log anomalies
                if is_anomaly:
                    logger.warning(f"Anomaly detected! Record ID: {record['record_id']}, Error: {error:.4f}, Threshold: {self.model.error_threshold:.4f}")
                
                # Flush periodically
                if int(record['record_id']) % 100 == 0:
                    self.producer.flush()
                    logger.info(f"Processed {record['record_id']} records")
    
    def run(self, train_first=True, n_qubits=DEFAULT_QRC_PARAMS['n_qubits'], 
            n_layers=DEFAULT_QRC_PARAMS['n_layers'], 
            train_size=DEFAULT_TRAINING_PARAMS['train_size']):
        """
        Run the QRC handler.
        """
        try:
            if train_first:
                self.train_model(n_qubits, n_layers, train_size)
            else:
                # Try to load an existing model
                try:
                    self.model = QuantumReservoirModel(n_qubits=n_qubits, n_layers=n_layers)
                    self.model.load_model("qrc_model.npz")
                    self.training_complete = True
                except Exception as e:
                    logger.error(f"Failed to load model: {e}")
                    logger.info("Training a new model instead")
                    self.train_model(n_qubits, n_layers, train_size)
            
            # Process the stream
            self.process_stream()
            
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        finally:
            self.consumer.close()
            self.producer.close()
            logger.info("Closed Kafka connections")