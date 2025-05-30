import numpy as np
import pennylane as qml
import logging
from config import DEFAULT_QRC_PARAMS, DEFAULT_ANOMALY_PARAMS

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class QuantumReservoirModel:
    def __init__(self, n_qubits=DEFAULT_QRC_PARAMS['n_qubits'], 
                 n_layers=DEFAULT_QRC_PARAMS['n_layers'], 
                 leakage_rate=DEFAULT_QRC_PARAMS['leakage_rate'], 
                 lambda_reg=DEFAULT_QRC_PARAMS['lambda_reg'], 
                 device_name=DEFAULT_QRC_PARAMS['device_name']):
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
        self.value_threshold = DEFAULT_ANOMALY_PARAMS['value_threshold']
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
        self.error_threshold = np.mean(train_errors) + DEFAULT_ANOMALY_PARAMS['threshold_factor'] * np.std(train_errors)
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
    
    def detect_anomalies(self, input_seq):
        """
        Wczesne ostrzeganie: prognoza > value_threshold → anomalia.
        """
        prediction = self.predict([input_seq])[0]
        is_anomaly = prediction > self.value_threshold
        return prediction, is_anomaly
    
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