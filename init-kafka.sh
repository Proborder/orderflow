#!/bin/sh
SERVER=${BOOTSTRAP_SERVER:-"kafka:9092"}

echo "Waiting for Kafka ($SERVER)..."

until kafka-topics --bootstrap-server $SERVER --list > /dev/null 2>&1; do
  echo "Kafka is not ready yet..."
  sleep 2
done

echo "Creating topics..."

kafka-topics --bootstrap-server $SERVER --create --if-not-exists --topic order.events --partitions 4 --replication-factor 1
kafka-topics --bootstrap-server $SERVER --create --if-not-exists --topic inventory.commands --partitions 4 --replication-factor 1
kafka-topics --bootstrap-server $SERVER --create --if-not-exists --topic payment.commands --partitions 4 --replication-factor 1
kafka-topics --bootstrap-server $SERVER --create --if-not-exists --topic order.dlq --partitions 1 --replication-factor 1

echo "Successfully created all topics!"