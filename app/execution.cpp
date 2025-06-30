#include "kafka_consumer_base.hpp"
#include <nlohmann/json.hpp>
#include <fstream>
#include <iostream>

class ExecutionEngine : public KafkaConsumerBase {
    std::ofstream profitBook;

public:
    ExecutionEngine(const std::string& brokers)
      : KafkaConsumerBase(brokers, "execution_group") {
        subscribe("trade_signal");
        profitBook.open("profit_book.csv", std::ios::app);
        if (profitBook.tellp() == 0) {
            profitBook << "symbol,action,filled_price,qty,notional\n";
        }
    }

    ~ExecutionEngine() {
        if (profitBook.is_open()) profitBook.close();
    }

    void processMessage(const std::string& key, const std::string& payload) override {
        auto signal = nlohmann::json::parse(payload);
        std::string action = signal["action"];
        double price = signal["price"];
        int qty = 100;
        double notional = price * qty;

        nlohmann::json fill = {
            {"symbol", key},
            {"action", action},
            {"filled_price", price},
            {"qty", qty}
        };
        std::cout << "FILL: " << fill.dump() << std::endl;

        profitBook << key << "," << action << "," << price << "," << qty << "," << notional << "\n";
    }
};

int main() {
    ExecutionEngine exec("localhost:9092");
    exec.run();
    return 0;
}
