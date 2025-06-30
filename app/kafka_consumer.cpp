#include "kafka_consumer.hpp"
#include <iostream>

KafkaConsumerBase::KafkaConsumerBase(const std::string& brokers, const std::string& groupId) {
    std::string errstr;
    auto conf = RdKafka::Conf::create(RdKafka::Conf::CONF_GLOBAL);
    conf->set("bootstrap.servers", brokers, errstr);
    conf->set("group.id", groupId, errstr);
    consumer.reset(RdKafka::KafkaConsumer::create(conf, errstr));
    delete conf;
}

KafkaConsumerBase::~KafkaConsumerBase() {
    consumer->close();
}

void KafkaConsumerBase::subscribe(const std::string& topic) {
    consumer->subscribe({topic});
}

void KafkaConsumerBase::run() {
    while (true) {
        auto msg = consumer->consume(1000);
        if (msg->err() == RdKafka::ERR_NO_ERROR) {
            processMessage(msg->key(), static_cast<const char*>(msg->payload()));
        }
        delete msg;
    }
}
