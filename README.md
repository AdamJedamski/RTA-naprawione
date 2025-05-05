# RTA-Project: Real-Time Anomaly Detection in IoT Datastreams

This project implements a real-time anomaly detection system for IoT signal datastreams using Quantum Reservoir Computing (QRC) with Apache Kafka for streaming data processing.

## Project Overview

The system detects anomalies in CPU utilization metrics by using a Quantum Reservoir Computing model. The architecture employs Apache Kafka for streaming data between components, creating a real-time processing pipeline.

### Architecture

The system consists of three main components:

1. **Data Streaming Component**: Reads CPU utilization data from a CSV file and publishes it to a Kafka topic.
2. **QRC Model Component**: Consumes data from Kafka, trains a QRC model, and performs real-time anomaly detection.
3. **Visualization Component**: Displays real-time data and anomaly detection results in an interactive dashboard.

### Technologies Used

- **Python**: Primary programming language
- **Apache Kafka & Zookeeper**: Message broker for data streaming
- **PennyLane**: Quantum machine learning framework
- **Dash & Plotly**: Interactive visualization
- **Docker & Docker Compose**: Containerization and orchestration

## Project Structure

```
rta-project/
├── data/
│   └── cpu_utilization_asg_misconfiguration.csv
├── data_streamer/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── streamer.py
├── qrc_model/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── config.py
│   ├── model.py
│   ├── kafka_handler.py
│   └── main.py
├── visualization/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── data_consumer.py
│   ├── dashboard.py
│   └── main.py
├── docker-compose.yml
└── README.md
```

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Git

### Installation and Setup

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/RTA-Project.git
   cd RTA-Project
   ```

2. Download the CPU utilization dataset:
   ```
   mkdir -p data
   curl -o data/cpu_utilization_asg_misconfiguration.csv https://raw.githubusercontent.com/numenta/NAB/master/data/realKnownCause/cpu_utilization_asg_misconfiguration.csv
   ```

3. Start the services in correct order to ensure proper initialization:
   ```
   # Start Zookeeper first
   docker-compose up -d zookeeper
   
   # Wait for Zookeeper to initialize (10-15 seconds)
   sleep 15
   
   # Start Kafka
   docker-compose up -d kafka
   
   # Wait for Kafka to initialize (20-30 seconds)
   sleep 30
   
   # Initialize Kafka topics
   docker-compose up -d kafka-init
   
   # Check if topics were created successfully
   docker-compose logs kafka-init
   
   # Start remaining services
   docker-compose up -d data-streamer qrc-model visualization
   ```

4. Access the dashboard:
   - Open your browser and navigate to `http://localhost:8050`

5. Monitor the system:
   ```
   docker-compose logs -f
   ```

### Troubleshooting

If you encounter connection issues between services, try the following:

1. Ensure Kafka is properly initialized before starting other services:
   ```
   docker-compose logs kafka
   ```

2. If DNS resolution issues persist, you can use the Kafka container's IP directly:
   ```
   # Find Kafka container IP
   docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' kafka
   
   # Update the bootstrap-servers parameter in docker-compose.yml with this IP
   ```

3. Restart services in correct order if needed:
   ```
   docker-compose down
   # Then follow the startup sequence described above
   ```

## How It Works

### Data Streaming

The data streamer reads CPU utilization data from a CSV file and publishes it to a Kafka topic (`iot-data`), simulating real-time streaming by adding a configured delay between data points.

### Quantum Reservoir Computing Model

The QRC model consumes data from Kafka, trains on historical data, and performs real-time anomaly detection. Using PennyLane for quantum circuit implementation, it creates a reservoir computing system that detects anomalies by comparing prediction errors with a dynamically updated threshold.

The model's predictions and anomaly detections are published to a Kafka topic (`qrc-predictions`) for visualization.

### Visualization Dashboard

The visualization component consumes data from both Kafka topics and displays a real-time dashboard featuring:

- Time series plots of actual vs. predicted values
- Error plot with threshold visualization
- Anomaly detection signal
- Current statistics and status

## Customization

### Adjusting QRC Model Parameters

Customize model behavior by changing parameters in `docker-compose.yml`:

- `--n-qubits`: Number of qubits in the quantum circuit (default: 8)
- `--n-layers`: Number of layers in the quantum circuit (default: 3)
- `--window-size`: Size of the sliding window for input sequences (default: 10)
- `--train-size`: Number of samples to use for training (default: 1000)

### Adjusting Visualization Settings

Customize visualization with parameters in `docker-compose.yml`:

- `--window-size`: Number of data points to display (default: 200)
- `--update-interval`: Dashboard refresh rate in milliseconds (default: 1000)

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Dataset from the Numenta Anomaly Benchmark (NAB)
- Inspired by research in Quantum Reservoir Computing for time series analysis