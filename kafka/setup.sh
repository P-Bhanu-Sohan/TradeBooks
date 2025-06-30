#!/usr/bin/env bash
docker exec kafka kafka-topics --create --topic market_data --bootstrap-server kafka:9092 --partitions 1 --replication-factor 1
docker exec kafka kafka-topics --create --topic order_book_snapshot --bootstrap-server kafka:9092 --partitions 1 --replication-factor 1
docker exec kafka kafka-topics --create --topic trade_signal --bootstrap-server kafka:9092 --partitions 1 --replication-factor 1
docker exec kafka kafka-topics --create --topic fills --bootstrap-server kafka:9092 --partitions 1 --replication-factor 1
