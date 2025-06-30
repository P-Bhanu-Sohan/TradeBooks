#pragma once
#include <librdkafka/rdkafkacpp.h>
#include <string>
#include <memory>

class KafkaConsumerBase {
public:
    KafkaConsumerBase(const std::string& brokers, const std::string& groupId);
    virtual ~KafkaConsumerBase();
    void subscribe(const std::string& topic);
    void run();
    virtual void processMessage(const std::string& key, const std::string& payload) = 0;

protected:
    std::unique_ptr<RdKafka::KafkaConsumer> consumer;
};


