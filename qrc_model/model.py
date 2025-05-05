
import numpy as np
import pennylane as qml
import logging
from collections import deque
import json
from kafka import KafkaConsumer, KafkaProducer
import threading
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class QuantumReservoirModel:
    def __init__(self, n_qubits, n_layers, leakage_rate=0.1, lambda_reg=1e-6, device_name="default.qubit"):
        """
        Initialize the Quantum Reservoir Computing model.
        
        Args:
            n_qubits (int): Number of qubits to use
            n_layers (int): Number of layers in the quantum circuit
            leakage_rate (float): Leakage rate for the reservoir
            lambda_reg (float): Regularization parameter
            device_name (str): PennyLane device name
        """
        self.n_qubits = n_qubits
        self.n_layers = n_layers
        self.leakage_rate = leakage_rate
        self.lambda_reg = lambda_reg
        self.n_observables = 3 * n_qubits
        self.dev = qml.device(device_name, wires=n_qubits)

        # Will be initialized in fit()
        self.weights = None
        self.biases = None
        self.W_out = None
        
        # For anomaly detection
        self.error_threshold = None
        self.error_history = []
        
        # Compile QNode
        self.reservoir_circuit = qml.QNode(self._reservoir_circuit, self.dev)
        
        logger.info(f"Initialized QRC model with {n_qubits} qubits and {n_layers} layers")

    def _quantum_reservoir(self, inputs, weights, biases, leakage_rate, previous_state):
        if previous_state is None:
            previous_state = np.zeros(self.n_observables)

        for i in range(self.n_qubits):
            input_component = leakage_rate * (inputs[i % len(inputs)] + biases[i])
            memory_component = (1 - leakage_rate) * previous_state[i]
            total_angle = input_component + memory_component
            qml.RX(total_angle, wires=i)

        for layer in range(self.n_layers):
            for i in range(self.n_qubits):
                qml.Rot(*weights[layer, i], wires=i)
            for i in range(self.n_qubits - 1):
                qml.CNOT(wires=[i, i + 1])

        return [qml.expval(qml.PauliX(i)) for i in range(self.n_qubits)] + \
               [qml.expval(qml.PauliY(i)) for i in range(self.n_qubits)] + \
               [qml.expval(qml.PauliZ(i)) for i in range(self.n_qubits)]

    def _reservoir_circuit(self, inputs, weights, biases, leakage_rate, previous_state):
        return self._quantum_reservoir(inputs, weights, biases, leakage_rate, previous_state)

    def fit(self, train_inputs, train_outputs, n_epochs=1):
        """
        Train the QRC model.
        
        Args:
            train_inputs (np.ndarray): Training input sequences
            train_outputs (np.ndarray): Training output values
            n_epochs (int): Number of epochs to train
        """
        logger.info(f"Training QRC model with {len(train_inputs)} samples, {n_epochs} epochs")
        
        self.weights = np.random.uniform(-np.pi, np.pi, (self.n_layers, self.n_qubits, 3))
        self.biases = np.random.uniform(-0.5, 0.5, self.n_qubits)

        all_epoch_states = []

        for epoch in range(n_epochs):
            logger.info(f"Epoch {epoch+1}/{n_epochs}")
            epoch_states = []
            prev_state = np.zeros(self.n_observables)

            for i, input_seq in enumerate(train_inputs):
                if i % 100 == 0:
                    logger.info(f"Processing training sample {i}/{len(train_inputs)}")
                
                current_state = self.reservoir_circuit(
                    inputs=input_seq,
                    weights=self.weights,
                    biases=self.biases,
                    leakage_rate=self.leakage_rate,
                    previous_state=prev_state
                )
                epoch_states.append(current_state)
                prev_state = current_state

            all_epoch_states.append(np.vstack(epoch_states))

        R = np.mean(all_epoch_states, axis=0) if n_epochs > 1 else all_epoch_states[0]
        Y = train_outputs.reshape(-1, 1)

        I = np.eye(self.n_observables)
        self.W_out = np.linalg.solve(R.T @ R + self.lambda_reg * I, R.T @ Y).flatten()
        
        logger.info("QRC model training completed")
        
        # Calculate error threshold for anomaly detection
        train_predictions = self.predict(train_inputs)
        train_errors = np.abs(train_predictions - train_outputs)
        self.error_threshold = np.mean(train_errors) + 3 * np.std(train_errors)
        logger.info(f"Calculated error threshold for anomaly detection: {self.error_threshold}")
        
        return self

    def predict(self, test_inputs):
        """
        Generate predictions using the trained QRC model.
        
        Args:
            test_inputs (np.ndarray): Test input sequences
            
        Returns:
            np.ndarray: Predicted values
        """
        if self.W_out is None:
            raise ValueError("Model must be fitted before prediction.")

        predictions = []
        prev_state = np.zeros(self.n_observables)

        for input_seq in test_inputs:
            current_state = self.reservoir_circuit(
                inputs=input_seq,
                weights=self.weights,
                biases=self.biases,
                leakage_rate=self.leakage_rate,
                previous_state=prev_state
            )
            y_pred = np.dot(self.W_out, current_state)
            predictions.append(y_pred)
            prev_state = current_state

        return np.array(predictions)
    
    def detect_anomalies(self, input_seq, actual_value):
        """
        Detect anomalies by comparing prediction error with threshold.
        
        Args:
            input_seq (np.ndarray): Input sequence
            actual_value (float): Actual observed value
            
        Returns:
            tuple: (prediction, error, is_anomaly)
        """
        prediction = self.predict([input_seq])[0]
        error = abs(prediction - actual_value)
        self.error_history.append(error)
        
        # Dynamic threshold update (optional)
        if len(self.error_history) > 100:
            self.error_history.pop(0)
            self.error_threshold = np.mean(self.error_history) + 3 * np.std(self.error_history)
        
        is_anomaly = error > self.error_threshold
        return prediction, error, is_anomaly
    
    def save_model(self, filepath):
        """Save model parameters to a file"""
        if self.W_out is None:
            raise ValueError("Model must be fitted before saving.")
        
        np.savez(
            filepath,
            weights=self.weights,
            biases=self.biases,
            W_out=self.W_out,
            error_threshold=self.error_threshold
        )
        logger.info(f"Model saved to {filepath}")
    
    def load_model(self, filepath):
        """Load model parameters from a file"""
        data = np.load(filepath)
        self.weights = data['weights']
        self.biases = data['biases']
        self.W_out = data['W_out']
        self.error_threshold = float(data['error_threshold'])
        logger.info(f"Model loaded from {filepath}")
        
        return self

class QRCKafkaHandler:
    def __init__(self, bootstrap_servers, input_topic, output_topic, window_size=10):
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
            group_id='qrc-model-consumer'
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
        
    def train_model(self, n_qubits=8, n_layers=3, train_size=1000):
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
    
    def run(self, train_first=True, n_qubits=8, n_layers=3, train_size=1000):
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

if __name__ == "__main__":
    # Parse command line arguments
    import argparse
    
    parser = argparse.ArgumentParser(description='QRC Model for anomaly detection')
    parser.add_argument('--bootstrap-servers', default='localhost:9092', help='Kafka bootstrap servers')
    parser.add_argument('--input-topic', default='iot-data', help='Kafka topic to consume data from')
    parser.add_argument('--output-topic', default='qrc-predictions', help='Kafka topic to publish predictions to')
    parser.add_argument('--window-size', type=int, default=10, help='Window size for input sequences')
    parser.add_argument('--n-qubits', type=int, default=8, help='Number of qubits to use')
    parser.add_argument('--n-layers', type=int, default=3, help='Number of layers in the quantum circuit')
    parser.add_argument('--train-size', type=int, default=1000, help='Number of samples to use for training')
    parser.add_argument('--no-train', action='store_true', help='Skip training and try to load an existing model')
    
    args = parser.parse_args()
    
    # Create handler and run
    handler = QRCKafkaHandler(
        bootstrap_servers=args.bootstrap_servers,
        input_topic=args.input_topic,
        output_topic=args.output_topic,
        window_size=args.window_size
    )
    
    handler.run(
        train_first=not args.no_train,
        n_qubits=args.n_qubits,
        n_layers=args.n_layers,
        train_size=args.train_size
    )