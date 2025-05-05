import argparse
import logging
from kafka_handler import QRCKafkaHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Main function to run the QRC model for anomaly detection."""
    # Parse command line arguments
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

if __name__ == "__main__":
    main()