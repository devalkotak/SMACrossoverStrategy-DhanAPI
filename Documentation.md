# How the SMA bot works

Notes on the internals, mostly for my own reference. Each symbol in the watchlist is handled as a small state machine with three states: empty (no position), active (in a trade), and closed.

## app_v1.0.2.py (the loop)

The entry point. It runs a `while` loop that repeats every second.

**Time check.** Each pass compares the current time against `START_TIME` and `END_TIME`. Outside market hours it just sleeps 10 seconds so it isn't hitting the API for no reason.

**Data.** `tsl.get_ltp(names=WATCHLIST)` pulls the last price for every symbol in one call, which is cheaper than one call per symbol. `tu.get_historical_data_safe(...)` then pulls OHLC per ticker to compute the moving averages.

**State loop.** For each ticker it checks the `status` in the `orderbook`:
- active: skip entry logic, only check exits (stop loss, take profit, time)
- empty: skip exit logic, only check for an entry signal (the crossover)

**The repainting fix.** This is the part I cared most about. A live 5-minute candle (say 9:15 to 9:20) keeps changing price until it closes, so any indicator built on it flickers. The fix is to ignore the forming candle (index -1) and only act on the last fully closed one (index -2):

```python
last_completed_time = chart.index[-2]
if last_candle_processed[name] != last_completed_time:
    # check signal
```

`last_candle_processed` is a per-ticker pointer. Once a decision is made for the 9:15 candle it stays locked until the 9:20 candle closes, so the same candle can't trigger two entries.

## trade_utils.py (the functions)

Stateless helpers. They don't hold any state of their own, they just act on whatever is passed in.

- `paper_entry` / `paper_exit`: stand in for a broker. Instead of sending an order to the exchange they update the local `orderbook` dict and append to `completed_orders`. Both dump the full trade state with `json.dumps`, so I can go back later and see exactly why a stop or target fired.
- `check_crossover`: the signal. A crossover means the fast SMA was below the slow SMA on the previous closed candle and is above it on the latest one. It's wrapped in a try/except because right after open there often isn't enough data for a 20-period SMA yet.
- `save_to_csv`: runs on exit. Turns `completed_orders` into a pandas DataFrame and writes it out, so I can review the forward test afterward.

## One pass through the loop

1. Check the time.
2. Fetch LTP and OHLC.
3. For each ticker, check `orderbook['status']`:
   - in a position: compare LTP against `stoploss` and `target_price`; if either is hit, call `paper_exit`, update Excel, log it.
   - flat: if there's a new closed candle, recompute the SMAs; on a crossover, call `paper_entry`, update Excel, log it.
4. Sum the PnL and stop everything if it's past the max loss.
5. Sleep one second and repeat.

## Speed

Each loop makes one fast LTP call plus N slower historical calls (one per ticker). The Excel update is the expensive part, so it's gated behind a flag and only runs when a trade actually happens. The rest of the time the loop stays under a second.
