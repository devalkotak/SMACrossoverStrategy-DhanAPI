# Technical Documentation: SMA Algo v1

## 1. Introduction
This document provides a comprehensive technical breakdown of the SMA Crossover Algorithm. The system is designed as a **Finite State Machine (FSM)** where each asset in the watchlist transitions between states (`EMPTY`, `ACTIVE`, `CLOSED`) based on market data and strategy logic.

## 2. File Structure Analysis

### A. `app.py` (The Controller)
This file is the entry point of the application. It runs an infinite `while` loop that acts as the heartbeat of the system.

**Key Logic Blocks:**
1.  **Time Gatekeeping:**
    * Before fetching data, the system checks `dt.datetime.now()`.
    * If outside `START_TIME` and `END_TIME`, the loop sleeps for 10 seconds to conserve resources and API limits.

2.  **Data Ingestion:**
    * `tsl.get_ltp(names=WATCHLIST)`: This is optimized to fetch prices for *all* stocks in a single API call, reducing HTTP overhead.
    * `tu.get_historical_data_safe(...)`: Fetches OHLC data for individual tickers to calculate indicators.

3.  **The State Loop:**
    For every ticker in the watchlist, the code checks the `status` flag in the `orderbook`:
    * **If `ACTIVE`:** It bypasses entry logic and strictly checks for Exit Conditions (SL, TP, Time).
    * **If `EMPTY`:** It bypasses exit logic and checks for Entry Signals (SMA Crossover).

4.  **The "Repainting" Fix:**
    One of the most critical logic implementations is the candle indexing:
    ```python
    last_completed_time = chart.index[-2]
    if last_candle_processed[name] != last_completed_time:
         # Check Signal
    ```
    * **The Problem:** In a live 5-minute candle (e.g., 9:15-9:20), the close price changes every second. This causes indicators to flicker.
    * **The Solution:** The code ignores index `-1` (the forming candle) and only makes decisions based on index `-2` (the last fully closed candle).
    * **The Memory Pointer:** `last_candle_processed` ensures that once a decision is made for the 9:15 candle, the logic is **locked** until the 9:20 candle closes.

### B. `trade_utils.py` (The Library)
This file contains pure functions. It does not store state; it only manipulates the data passed to it.

**Key Functions:**
1.  **`paper_entry` & `paper_exit`:**
    * These functions simulate the behavior of a broker.
    * Instead of sending an HTTP request to an exchange, they update a local dictionary (`orderbook`) and append to a list (`completed_orders`).
    * **Logging:** These functions use `json.dumps` to log the entire state of the trade. This allows for post-trade debugging (e.g., "Why did my SL hit? I can see the exact SL price calculated in the logs.").

2.  **`check_crossover`:**
    * Encapsulates the mathematical logic: `SMA(t-1) > SMA(t-1)` AND `SMA(t-2) < SMA(t-2)`.
    * Wrapped in a `try-except` block to prevent crashes during the first few minutes of the market open when sufficient data might not exist for a 20-period SMA.

3.  **`save_to_csv`:**
    * Triggered only on exit.
    * Converts the list of dictionaries `completed_orders` into a Pandas DataFrame and writes it to disk. This is essential for backtesting the performance of the forward test.

## 3. Data Flow Diagram

1.  **Loop Start** -> Check Time
2.  **Fetch Data** -> Get LTP & OHLC
3.  **Check State** (`orderbook['status']`)
    * *Case A: Active Position*
        * Check Current LTP vs `stoploss` and `target_price`.
        * If Hit -> Call `paper_exit` -> Update Excel -> Write to Log.
    * *Case B: No Position*
        * Check `last_candle_processed`.
        * If New Candle -> Calculate SMA.
        * If Crossover -> Call `paper_entry` -> Update Excel -> Write to Log.
4.  **Risk Check** -> Sum(PnL) < Max Loss?
5.  **Sleep** -> Wait 1 second -> Repeat.

## 4. Latency & Optimization
* **Network:** The script makes 1 LTP call per loop (fast) and `N` historical data calls (slow).
* **Excel:** The expensive `update_sheets` function is gated behind an `update_excel` boolean flag. It ONLY runs when a trade actually occurs, keeping the loop speed high (sub-second) during 99% of the runtime.