# RTA-Project: IoT Signal Datastream Anomalies Detection

Real-time anomaly detection in IoT signal datastreams using Quantum Reservoir Computing (QRC) with Kafka streaming.

## Project Overview

This project implements a real-time anomaly detection system for IoT data streams, specifically focused on CPU utilization metrics. The system uses Quantum Reservoir Computing (QRC) for anomaly detection and Apache Kafka for data streaming.

### Architecture

The system consists of the following components:

1. **Data Streaming Component**: Reads data from a source (CSV file or synthetic generator) and publishes it to a Kafka topic.
2. **QRC Model Component**: Consumes data from Kafka, trains a QRC model, and performs real-time anomaly detection.
3. **Visualization Component**: Displays real-time data and anomaly detection results.
4. **Kafka Infrastructure**: Serves as the central message bus for communication between components.

### Technologies Used

- **Python**: Primary programming language
- **Apache Kafka**: Message broker for data streaming
- **PennyLane**: Quantum machine learning framework
- **Dash/Plotly**: Interactive visualization
- **Docker**: Containerization
- **Docker Compose**: Container orchestration

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
│   └── model.py
├── visualization/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── dashboard.py
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
   git clone https://github.com/yourusername/rta-project.git
   cd rta-project
   ```

2. Download the CPU utilization dataset:
   ```
   mkdir -p data
   curl -o data/cpu_utilization_asg_misconfiguration.csv https://raw.githubusercontent.com/numenta/NAB/master/data/realKnownCause/cpu_utilization_asg_misconfiguration.csv
   ```

3. Build and start the containers:
   ```
   docker-compose up -d
   ```

4. Access the dashboard:
   Open your browser and navigate to `http://localhost:8050`

### Running Individual Components (for Development)

#### Data Streamer
```
cd data_streamer
pip install -r requirements.txt
python streamer.py --bootstrap-servers localhost:29092 --topic iot-data --data-source ../data/cpu_utilization_asg_misconfiguration.csv --delay 0.5
```

#### QRC Model
```
cd qrc_model
pip install -r requirements.txt
python model.py --bootstrap-servers localhost:29092 --input-topic iot-data --output-topic qrc-predictions --window-size 10 --n-qubits 8 --n-layers 3 --train-size 1000
```

#### Visualization
```
cd visualization
pip install -r requirements.txt
python dashboard.py --bootstrap-servers localhost:29092 --raw-topic iot-data --predictions-topic qrc-predictions --window-size 200 --update-interval 1000
```

## How It Works

### Data Streaming

The data streamer reads CPU utilization data from a CSV file and publishes it to a Kafka topic (`iot-data`). It simulates real-time streaming by adding a delay between data points.

### Quantum Reservoir Computing Model

The QRC model consumes data from the Kafka topic, trains on historical data, and then performs real-time anomaly detection. The model uses a quantum circuit implemented with PennyLane to create a reservoir computing system. Anomalies are detected by comparing prediction errors with a threshold.

The model's predictions and anomaly detection results are published to another Kafka topic (`qrc-predictions`).

### Visualization

The visualization component consumes both raw data and model predictions from Kafka topics and displays them in a real-time dashboard. The dashboard includes:

- Time series plot of actual vs. predicted values
- Error plot with threshold
- Anomaly detection signal
- Statistics and current status

## Customization

### Using Different Data Sources

You can use different data sources by:

1. Modifying the data streamer to read from different files or APIs
2. Adjusting the data schema if necessary
3. Updating the QRC model parameters to better fit the new data

### Adjusting QRC Model Parameters

You can adjust the QRC model parameters by modifying the arguments passed to the model in the `docker-compose.yml` file:

- `--n-qubits`: Number of qubits in the quantum circuit
- `--n-layers`: Number of layers in the quantum circuit
- `--window-size`: Size of the sliding window for input sequences
- `--train-size`: Number of samples to use for training

### Scaling the System

To scale the system for higher throughput:

1. Increase Kafka partitions in the `kafka-init` service
2. Add more instances of the QRC model by scaling the container
3. Consider using a Kafka Streams application for parallelized processing

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Dataset from the Numenta Anomaly Benchmark (NAB)
- Inspired by research in Quantum Reservoir Computing for time series processing