#!/bin/bash

# Zatrzymaj i usuń wszystkie kontenery
echo "Zatrzymywanie wszystkich kontenerów..."
docker-compose down

# Usuń wszystkie wolumeny, aby mieć czysty start
echo "Usuwanie wolumenów..."
docker volume rm $(docker volume ls -q | grep 'rta-project_') 2>/dev/null || true

# Usuń obrazy kontenerów, aby wymusić pełne przebudowanie
echo "Usuwanie obrazów kontenerów..."
docker rmi rta-project-data-streamer rta-project-qrc-model rta-project-visualization 2>/dev/null || true

# Sprawdź, czy plik danych istnieje
if [ ! -f "./data/cpu_utilization_asg_misconfiguration.csv" ]; then
  echo "BŁĄD: Plik danych nie istnieje. Upewnij się, że plik ./data/cpu_utilization_asg_misconfiguration.csv jest dostępny."
  exit 1
fi

# Przebuduj kontenery
echo "Przebudowywanie kontenerów..."
docker-compose build

# Uruchom cały stos jednocześnie, ale w odpowiedniej kolejności
echo "Uruchamianie Zookeepera..."
docker-compose up -d zookeeper
sleep 5

echo "Uruchamianie Kafki..."
docker-compose up -d kafka
sleep 10

echo "Inicjalizacja tematów Kafki..."
docker-compose up -d kafka-init
sleep 5

echo "Uruchamianie data-streamer..."
docker-compose up -d data-streamer
sleep 3

echo "Uruchamianie qrc-model..."
docker-compose up -d qrc-model
sleep 3

echo "Uruchamianie visualization..."
docker-compose up -d visualization

echo "Wszystkie usługi zostały uruchomione!"
echo "Dashboard jest dostępny pod adresem: http://localhost:8050"
echo "Aby sprawdzić status usług, użyj: docker-compose ps"
echo "Aby zobaczyć logi, użyj: docker-compose logs -f"