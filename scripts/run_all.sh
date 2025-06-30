#!/usr/bin/env bash
# Start producer
tmux new-session -d -s quant 'python3 python_producer/yfinance_data_dumper.py'

# Start Order Book
tmux split-window -h -t quant 'scripts/build.sh && ./order_book_engine'

# Start Strategy
tmux split-window -v -t quant 'scripts/build.sh && ./strategy_engine'

# Start Execution
tmux split-window -v -t quant 'scripts/build.sh && ./execution_engine'

tmux select-layout tiled
tmux attach -t quant
