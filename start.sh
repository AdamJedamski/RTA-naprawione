#!/bin/bash

# Zatrzymaj i usuń wszystkie kontenery
echo "Zatrzymywanie wszystkich kontenerów..."
docker-compose down

# Usuń wszystkie wolumeny, aby mieć czysty start
echo "Usuwanie wolumenów..."
docker volume rm $(docker volume ls -q | grep 'rta-project_') 2>/dev/null || true

# Sprawdź, czy plik danych istnieje
if [ ! -f "./data/cpu_utilization_asg_misconfiguration.csv" ]; then
  echo "BŁĄD: Plik danych nie istnieje. Upewnij się, że plik ./data/cpu_utilization_asg_misconfiguration.csv jest dostępny."
  exit 1
fi

# Uruchom Zookeeper
echo "Uruchamianie Zookeepera..."
docker-compose up -d zookeeper

# Sprawdź status Zookeepera po uruchomieniu
echo "Sprawdzanie statusu Zookeepera..."
sleep 2
ZOOKEEPER_STATUS=$(docker ps -f "name=zookeeper" --format "{{.Status}}")
if [[ $ZOOKEEPER_STATUS != *"Up"* ]]; then
  echo "BŁĄD: Zookeeper nie uruchomił się poprawnie. Sprawdź logi:"
  docker logs zookeeper
  exit 1
fi

# Czekaj dodatkowy czas na pełną inicjalizację Zookeepera
echo "Czekanie na pełną inicjalizację Zookeepera (20s)..."
sleep 10

# Uruchom Kafka
echo "Uruchamianie Kafki..."
docker-compose up -d kafka

# Sprawdź status Kafki
echo "Sprawdzanie statusu Kafki..."
sleep 5
KAFKA_STATUS=$(docker ps -f "name=kafka" --format "{{.Status}}")
if [[ $KAFKA_STATUS != *"Up"* ]]; then
  echo "BŁĄD: Kafka nie uruchomiła się poprawnie. Sprawdź logi:"
  docker logs kafka
  exit 1
fi

# Poczekaj na inicjalizację Kafki
echo "Czekanie na inicjalizację Kafki (30s)..."
sleep 10

# Inicjalizuj tematy Kafki
echo "Inicjalizacja tematów Kafki..."
docker-compose up -d kafka-init

# Poczekaj na inicjalizację tematów
echo "Czekanie na inicjalizację tematów (10s)..."
sleep 5

# Sprawdź, czy tematy zostały utworzone
echo "Sprawdzanie, czy tematy zostały utworzone..."
docker exec kafka kafka-topics --list --bootstrap-server kafka:9092 | grep -q "iot-data"
if [ $? -ne 0 ]; then
  echo "OSTRZEŻENIE: Temat iot-data nie został znaleziony. Mimo to kontynuujemy..."
fi

# Uruchom pozostałe usługi
echo "Uruchamianie pozostałych usług..."
docker-compose up -d data-streamer
sleep 2
docker-compose up -d qrc-model
sleep 2
docker-compose up -d visualization

echo "Wszystkie usługi zostały uruchomione!"
echo "Dashboard jest dostępny pod adresem: http://localhost:8050"
echo "Aby sprawdzić status usług, użyj: docker-compose ps"
echo "Aby zobaczyć logi, użyj: docker-compose logs -f"