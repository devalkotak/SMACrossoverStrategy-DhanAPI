import datetime as dt
import xlwings as xw
import pandas as pd
import talib
import logging
import json

# ==========================================
#          DATA & EXCEL MANAGEMENT
# ==========================================

def get_empty_order_template():
    return {
        'name': None, 'date': None, 'entry_signal': None, 'entry_time': None,
        'entry_price': None, 'qty': 0, 'target_price': None, 'stoploss': None,
        'exit_signal': None, 'exit_time': None, 'exit_price': None, 
        'pnl': 0.0, 'remark': None, 'status': 'EMPTY', 'max_holding_time': None
    }

def setup_sheets():
    """Initializes the Excel dashboard safely."""
    filename = f'PaperTrade_{dt.date.today()}.xlsx'
    try:
        wb = xw.Book(filename)
    except:
        wb = xw.Book()
        wb.save(filename)
    
    for sheet in ['live_trading', 'completed_orders']:
        if sheet not in [s.name for s in wb.sheets]:
            wb.sheets.add(sheet)

    live = wb.sheets['live_trading']
    comp = wb.sheets['completed_orders']
    live.clear()
    comp.clear()
    
    # Init Headers
    headers = pd.DataFrame([get_empty_order_template()])
    live.range('A1').value = headers
    comp.range('A1').value = headers
    
    return live, comp

def update_sheets(live_sheet, comp_sheet, orderbook, completed_orders):
    """Updates Excel without overwriting headers."""
    # Active Orders
    active_data = [v for k, v in orderbook.items() if v['status'] == 'ACTIVE']
    if active_data:
        live_sheet.range('A2').value = pd.DataFrame(active_data).values
    else:
        live_sheet.range('A2:Z100').clear_contents()

    # Completed Orders
    if completed_orders:
        comp_sheet.range('A2').value = pd.DataFrame(completed_orders).values

def save_to_csv(completed_orders):
    """Exports all completed trades to a timestamped CSV file."""
    if not completed_orders:
        logging.info("No trades executed. Skipping CSV export.")
        return
    
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"TradeLog_{timestamp}.csv"
    
    try:
        df = pd.DataFrame(completed_orders)
        df.to_csv(filename, index=False)
        logging.info(f"Successfully exported trade data to {filename}")
        print(f"\n[INFO] Data saved to {filename}")
    except Exception as e:
        logging.error(f"Failed to save CSV: {e}")

def get_historical_data_safe(tsl, name, exchange, timeframe):
    """Fetches data, calculates Indicators, and handles API errors."""
    try:
        chart = tsl.get_historical_data(tradingsymbol=name, exchange=exchange, timeframe=timeframe)
        if chart is None or chart.empty: 
            return None
        
        # --- ADD INDICATORS HERE ---
        chart['sma10'] = talib.SMA(chart['close'], timeperiod=10)
        chart['sma20'] = talib.SMA(chart['close'], timeperiod=20)
        return chart
    except Exception as e:
        logging.error(f"Data Fetch Error {name}: {e}")
        return None

# ==========================================
#          STRATEGY LOGIC
# ==========================================

def check_crossover(chart):
    """
    Checks for SMA Crossover on the LAST COMPLETED candle.
    Index -1 = Current forming candle (IGNORE)
    Index -2 = Last completed candle (USE THIS)
    Index -3 = Previous completed candle (USE THIS)
    """
    try:
        sma10_prev = chart['sma10'].iloc[-3]
        sma20_prev = chart['sma20'].iloc[-3]
        sma10_curr = chart['sma10'].iloc[-2]
        sma20_curr = chart['sma20'].iloc[-2]
        
        return sma10_prev < sma20_prev and sma10_curr > sma20_curr
    except IndexError:
        return False

def check_global_max_loss(completed_orders, orderbook, all_ltp, max_loss):
    """Calculates Realized + Unrealized PnL to protect account."""
    realized = sum(o['pnl'] for o in completed_orders)
    unrealized = 0
    
    for name, order in orderbook.items():
        if order['status'] == 'ACTIVE':
            try:
                ltp = float(all_ltp[name])
                if order['entry_signal'] == 'BUY':
                    unrealized += (ltp - order['entry_price']) * order['qty']
            except:
                continue 
            
    total_pnl = realized + unrealized
    if total_pnl <= -max_loss:
        logging.warning(f"CRITICAL: GLOBAL MAX LOSS HIT | Net PnL: {total_pnl}")
        return True
    return False

# ==========================================
#          ORDER EXECUTION (PAPER)
# ==========================================

def paper_entry(orderbook, name, ltp, signal, qty, sl_perc, tp_perc, hold_min):
    """Opens a virtual position and logs full state."""
    current_time = dt.datetime.now()
    
    # Calc Risk Levels
    sl_points = ltp * (sl_perc / 100)
    tg_points = ltp * (tp_perc / 100)
    
    if signal == 'BUY':
        sl = ltp - sl_points
        tp = ltp + tg_points
        exit_sig = 'SELL'
    
    # Update Orderbook
    order = orderbook[name]
    order.update({
        'name': name,
        'date': current_time.strftime('%Y-%m-%d'),
        'entry_time': current_time.strftime('%H:%M:%S'),
        'entry_price': ltp,
        'entry_signal': signal,
        'exit_signal': exit_sig,
        'qty': qty,
        'target_price': round(tp, 2),
        'stoploss': round(sl, 2),
        'max_holding_time': current_time + dt.timedelta(minutes=hold_min),
        'status': 'ACTIVE',
        'remark': 'Open',
        'pnl': 0.0
    })
    
    # VERBOSE LOGGING
    log_payload = {
        "event": "ENTRY_EXECUTION",
        "symbol": name,
        "price": ltp,
        "time": str(current_time),
        "risk_metrics": {"stoploss": sl, "target": tp},
        "full_order_state": order
    }
    logging.info(f"ENTRY SIGNAL | {json.dumps(log_payload, default=str)}")
    return True

def paper_exit(orderbook, completed_orders, name, ltp, current_time, remark):
    """Closes a virtual position and logs full state."""
    order = orderbook[name]
    
    order['exit_time'] = current_time.strftime('%H:%M:%S')
    order['exit_price'] = ltp
    
    # Calc PnL
    if order['entry_signal'] == 'BUY':
        order['pnl'] = (ltp - order['entry_price']) * order['qty']
    
    order['pnl'] = round(order['pnl'], 2)
    order['remark'] = remark
    order['status'] = 'CLOSED'
    
    # Archive
    completed_orders.append(order.copy())
    
    # VERBOSE LOGGING
    log_payload = {
        "event": "EXIT_EXECUTION",
        "symbol": name,
        "exit_price": ltp,
        "pnl": order['pnl'],
        "reason": remark,
        "final_trade_record": order
    }
    logging.info(f"EXIT SIGNAL | {json.dumps(log_payload, default=str)}")
    
    # Reset Slot
    orderbook[name] = get_empty_order_template()
    return True

def check_sl_tp_exit(orderbook, completed_orders, name, ltp, current_time):
    """Checks active orders for Exit conditions."""
    order = orderbook[name]
    if order['status'] != 'ACTIVE': return False

    exit_triggered = False
    remark = ""

    # 1. Price Checks
    if order['entry_signal'] == 'BUY':
        if ltp <= order['stoploss']: exit_triggered, remark = True, "SL Hit"
        elif ltp >= order['target_price']: exit_triggered, remark = True, "Target Hit"
    
    # 2. Time Checks
    if current_time > order['max_holding_time']:
        exit_triggered, remark = True, "Time Exit"

    if exit_triggered:
        return paper_exit(orderbook, completed_orders, name, ltp, current_time, remark)
    
    return False