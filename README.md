# Quantitative SMA Momentum Engine (Paper Trading Module)

## Overview
This repository contains a modular, polling-based algorithmic trading system designed for the Dhan API ecosystem. The current implementation focuses on a **Paper Trading** environment to simulate Simple Moving Average (SMA) crossover strategies with high-fidelity signal processing and risk management protocols.

The architecture is built to decouple strategy logic from execution routing, allowing for seamless transition from forward-testing (paper) to live order placement with minimal refactoring.

## System Architecture

### 1. Polling Engine (`app.py`)
The core event loop operates on a synchronous polling mechanism that queries market data at defined intervals. It serves as the "Controller," orchestrating data ingestion, signal validation, and state updates.
* **Latency Management:** Utilizes batched LTP requests to minimize network overhead.
* **State Persistence:** Maintains an in-memory `orderbook` structure to track active positions and preclude signal duplication.

### 2. Strategy & Execution Library (`trade_utils.py`)
A utility module encapsulating the business logic, mathematical computations, and logging subsystems.
* **Signal Processing:** Implements a strict `[t-2]` and `[t-3]` candle indexing method to eliminate look-ahead bias (repainting).
* **Virtual Order Management:** Simulates broker-side execution for Entry, Stop-Loss (SL), and Take-Profit (TP) orders.
* **Data Serialization:** JSON-formatted logging for granular analysis of order states.

## Key Features

* **Repaint-Proof Execution:** Logic validates crossovers strictly on completed candles, ensuring signals remain static once generated.
* **Real-time Dashboard:** Integrates with `xlwings` to push live trade status and PnL metrics to a local Excel instance.
* **Global Risk Circuit Breaker:** Monitors aggregate realized and unrealized PnL, terminating the engine if the drawdown exceeds the defined `GLOBAL_MAX_LOSS`.
* **Whipsaw Protection:** Implements a `last_candle_processed` memory pointer to prevent multiple entries on a single 5-minute candle.
* **Data Export:** Automatic serialization of trade history to CSV upon termination (SIGINT or Risk Exit).

## Configuration

All strategy parameters are exposed in the `USER CONFIGURATION` section of `app.py`:

| Parameter | Description | Default |
| :--- | :--- | :--- |
| `WATCHLIST` | List of trading symbols (NSE) | `['NIFTY', 'RELIANCE']` |
| `TIMEFRAME` | Candle interval for calculation | `'5'` (Minutes) |
| `SL_PERCENT` | Static Stop Loss percentage | `0.5%` |
| `TP_PERCENT` | Static Take Profit percentage | `1.0%` |
| `MAX_HOLDING_MINUTES` | Time-based exit threshold | `180` |

## Installation & Usage

1.  **Dependencies:**
    Ensure the requisite libraries are installed. Note that `TA-Lib` may require binary installation depending on the OS.
    ```bash
    pip install pandas xlwings Dhan-Tradehull TA-Lib
    ```

2.  **Authentication:**
    Place a `credentials.py` file in the root directory containing your Dhan API keys:
    ```python
    client_id = "YOUR_CLIENT_ID"
    access_token = "YOUR_JWT_TOKEN"
    ```

3.  **Execution:**
    Run the controller script:
    ```bash
    python app.py
    ```

## Output Artifacts

* **`PaperTrade_{Date}.xlsx`**: Live dashboard for monitoring active positions.
* **`strategy_logs.log`**: Detailed system logs including JSON dumps of every order event.
* **`TradeLog_{Timestamp}.csv`**: Final trade report generated upon session termination.

## Disclaimer
This software is intended for educational and testing purposes only. The paper trading module simulates market mechanics but does not account for slippage, liquidity constraints, or broker-side latency. Use at your own risk.