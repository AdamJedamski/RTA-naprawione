#!/bin/bash

# Zatrzymaj i usuń wszystkie kontenery
docker-compose down

# Uruchom Zookeeper
echo "Uruchamianie Zookeeper..."
docker-compose up -d zookeeper

# Poczekaj na inicjalizację Zookeepera
echo "Czekanie na inicjalizację Zookeepera (30s)..."
sleep 30

# Uruchom Kafka
echo "Uruchamianie Kafki..."
docker-compose up -d kafka

# Poczekaj na inicjalizację Kafki
echo "Czekanie na inicjalizację Kafki (60s)..."
sleep 60

# Inicjalizuj tematy Kafki
echo "Inicjalizacja tematów Kafki..."
docker-compose up -d kafka-init

# Poczekaj na inicjalizację tematów
echo "Czekanie na inicjalizację tematów (10s)..."
sleep 10

# Uruchom pozostałe usługi
echo "Uruchamianie pozostałych usług..."
docker-compose up -d data-streamer qrc-model visualization

echo "Wszystkie usługi zostały uruchomione!"
echo "Dashboard jest dostępny pod adresem: http://localhost:8050"