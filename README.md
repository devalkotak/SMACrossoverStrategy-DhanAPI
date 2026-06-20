# SMA Crossover Trading Bot (Dhan API)

A paper-trading bot for the Dhan API that runs a simple moving average crossover strategy on NSE stocks. I built it to understand how a polling-based trading loop works end to end: pulling live data, generating signals, managing positions, and tracking PnL, without putting real money on the line.

It only paper trades. Orders are simulated in memory and never sent to the exchange. The strategy logic is kept separate from execution, so it could be pointed at live orders later without rewriting the strategy.

## How it works

- `app_v1.0.2.py` is the main loop. It polls during market hours, fetches the last price for the whole watchlist in one call, and for each ticker either looks for an entry (if flat) or checks exit conditions (if in a position). Each ticker is tracked as a small state machine (empty, active, closed) so entry and exit logic never overlap.
- `trade_utils.py` holds the strategy and a simulated broker: the crossover check, paper entry/exit, JSON trade logging, and CSV export.

A few things I wanted to get right:

- **No repainting.** A forming candle's price changes every second, which makes indicators flicker. The signal logic only uses the last closed candle, and a memory pointer locks the decision for that candle until the next one closes, so a signal can't fire twice on the same candle.
- **Risk cutoff.** It tracks total realized and unrealized PnL and shuts the engine down if the drawdown crosses `GLOBAL_MAX_LOSS`.
- **Live view.** Trade status and PnL are pushed to an Excel sheet via xlwings while it runs, and the full trade history is written to CSV on exit.

## Config

Settings live at the top of `app_v1.0.2.py`:

| Setting | Meaning | Default |
|---|---|---|
| `WATCHLIST` | NSE symbols to trade | `['NIFTY', 'RELIANCE']` |
| `TIMEFRAME` | Candle size in minutes | `5` |
| `SL_PERCENT` | Stop loss | `0.5%` |
| `TP_PERCENT` | Take profit | `1.0%` |
| `MAX_HOLDING_MINUTES` | Time-based exit | `180` |

## Running it

1. `pip install -r requirements.txt` (TA-Lib may need a separate binary install depending on your OS)
2. Put your Dhan `client_id` and `access_token` in `credentials.py`
3. Set the watchlist and risk parameters at the top of `app_v1.0.2.py`
4. `python app_v1.0.2.py`

It runs during market hours and prints signals and fills as they happen. On exit it writes the dashboard (`PaperTrade_{date}.xlsx`), logs (`strategy_logs.log`), and a final `TradeLog_{timestamp}.csv`.

## Note

Educational and paper-trading only. It simulates market mechanics but does not model slippage, liquidity, or broker latency.
