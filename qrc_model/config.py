"""
Configuration parameters for the Quantum Reservoir Computing (QRC) model.
"""

# Default QRC model parameters
DEFAULT_QRC_PARAMS = {
    'n_qubits': 8,              # Number of qubits in the quantum circuit
    'n_layers': 3,              # Number of layers in the quantum circuit
    'leakage_rate': 0.1,        # Leakage rate for the reservoir
    'lambda_reg': 1e-6,         # Regularization parameter
    'device_name': "default.qubit"  # PennyLane device name
}

# Default Kafka parameters
DEFAULT_KAFKA_PARAMS = {
    'bootstrap_servers': 'localhost:9092',
    'input_topic': 'iot-data',
    'output_topic': 'qrc-predictions',
    'consumer_group': 'qrc-model-consumer'
}

# Training parameters
DEFAULT_TRAINING_PARAMS = {
    'window_size': 10,          # Size of the sliding window for input sequences
    'train_size': 1000,         # Number of samples to use for training
    'n_epochs': 1               # Number of epochs to train
}

# Anomaly detection parameters
DEFAULT_ANOMALY_PARAMS = {
    'threshold_factor': 3.0,    # Number of standard deviations for threshold
    'dynamic_threshold': True,  # Whether to update threshold dynamically
    'history_size': 100,         # Size of error history for dynamic threshold
    'value_threshold': 80
}