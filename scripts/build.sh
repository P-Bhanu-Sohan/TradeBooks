#!/usr/bin/env bash
g++ -std=c++17 cpp_core/kafka_consumer_base.cpp cpp_core/order_book_engine.cpp \
    -lrdkafka++ -lrdkafka -o order_book_engine

g++ -std=c++17 cpp_core/kafka_consumer_base.cpp cpp_core/strategy_engine.cpp \
    -lrdkafka++ -lrdkafka -o strategy_engine

g++ -std=c++17 cpp_core/kafka_consumer_base.cpp cpp_core/execution_engine.cpp \
    -lrdkafka++ -lrdkafka -o execution_engine

echo "Build complete."

