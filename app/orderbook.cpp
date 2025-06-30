#include "kafka_consumer_base.hpp"
#include <nlohmann/json.hpp>
#include <librdkafka/rdkafkacpp.h>
#include <algorithm>

class OrderBookEngine : public KafkaConsumerBase {
    RdKafka::Producer* producer;
    double bestBid = 0.0;
    double bestAsk = 1e9;

public:
    OrderBookEngine(const std::string& brokers)
      : KafkaConsumerBase(brokers, "order_book_group") {
        subscribe("market_data");
        std::string err;
        auto pconf = RdKafka::Conf::create(RdKafka::Conf::CONF_GLOBAL);
        pconf->set("bootstrap.servers", brokers, err);
        producer = RdKafka::Producer::create(pconf, err);
        delete pconf;
    }

    ~OrderBookEngine() { delete producer; }

    void processMessage(const std::string& key, const std::string& payload) override {
        auto j = nlohmann::json::parse(payload);
        bestBid = std::max(bestBid, j["low"].get<double>());
        bestAsk = std::min(bestAsk, j["high"].get<double>());

        nlohmann::json snapshot = {
            {"symbol", key},
            {"bid", bestBid},
            {"ask", bestAsk},
            {"spread", bestAsk - bestBid},
            {"timestamp", j["timestamp"]}
        };
        auto msg = snapshot.dump();
        producer->produce("order_book_snapshot",
                          RdKafka::Topic::PARTITION_UA,
                          RdKafka::Producer::RK_MSG_COPY,
                          const_cast<char*>(msg.c_str()),
                          msg.size(),
                          key,
                          nullptr);
        producer->poll(0);
    }
};

int main() {
    OrderBookEngine engine("localhost:9092");
    engine.run();
    return 0;
}
