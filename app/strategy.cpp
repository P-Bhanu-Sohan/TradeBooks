#include "kafka_consumer_base.hpp"
#include <nlohmann/json.hpp>
#include <librdkafka/rdkafkacpp.h>
#include <unordered_map>

class StrategyEngine : public KafkaConsumerBase {
    RdKafka::Producer* producer;
    std::unordered_map<std::string, double> latestBid, latestAsk;

public:
    StrategyEngine(const std::string& brokers)
      : KafkaConsumerBase(brokers, "strategy_group") {
        subscribe("order_book_snapshot");
        std::string err;
        auto pconf = RdKafka::Conf::create(RdKafka::Conf::CONF_GLOBAL);
        pconf->set("bootstrap.servers", brokers, err);
        producer = RdKafka::Producer::create(pconf, err);
        delete pconf;
    }

    ~StrategyEngine() { delete producer; }

    void processMessage(const std::string& key, const std::string& payload) override {
        auto j = nlohmann::json::parse(payload);
        latestBid[key] = j["bid"].get<double>();
        latestAsk[key] = j["ask"].get<double>();
        double spread = j["ask"].get<double>() - j["bid"].get<double>();

        if (spread < 0.05 && j["ask"].get<double>() < 150.0) {
            nlohmann::json signal = {
                {"symbol", key},
                {"action", "BUY"},
                {"price", j["ask"]}
            };
            auto msg = signal.dump();
            producer->produce("trade_signal",
                              RdKafka::Topic::PARTITION_UA,
                              RdKafka::Producer::RK_MSG_COPY,
                              const_cast<char*>(msg.c_str()),
                              msg.size(),
                              key,
                              nullptr);
            producer->poll(0);
        }
    }
};

int main() {
    StrategyEngine strat("localhost:9092");
    strat.run();
    return 0;
}
