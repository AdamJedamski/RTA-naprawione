import argparse
import logging
from data_consumer import KafkaDataConsumer
from dashboard import DashDashboard

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Main function to run the visualization dashboard."""
    # Parse command line arguments
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

if __name__ == "__main__":
    main()