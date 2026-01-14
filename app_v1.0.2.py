import datetime as dt
import time
import logging
from Dhan_Tradehull import Tradehull
import credentials
import trade_utils as tu 
import talib

# ==========================================
#        USER CONFIGURATION SECTION
# ==========================================

# 1. Strategy Settings
WATCHLIST           = ['NIFTY', 'RELIANCE'] 
EXCHANGE            = 'NSE'
TIMEFRAME           = '5'       # Candle timeframe
MAX_TRADES_PER_DAY  = 5         # Per stock
SMA_PERIOD_1        = 10        # Period for first SMA
SMA_PERIOD_2        = 20        # Period for second SMA
USE_EXCEL_OUTPUT    = True
MARGIN_CHECK        = True

# 2. Risk Management
QUANTITY            = 50        
SL_PERCENT          = 0.5       
TP_PERCENT          = 1.0       
GLOBAL_MAX_LOSS     = 2000      
MAX_HOLDING_MINUTES = 180       

# 3. Market Hours
START_TIME          = dt.time(9, 15)
END_TIME            = dt.time(15, 30)

# ==========================================

# Configure Logging to File and Console
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler("strategy_logs.log"),
        logging.StreamHandler()
    ]
)

tsl = Tradehull(client_id=credentials.client_id, access_token=credentials.access_token)

# Setup
if USE_EXCEL_OUTPUT:
    live_sheet, comp_sheet = tu.setup_sheets()
completed_orders = []
orderbook = {name: tu.get_empty_order_template() for name in WATCHLIST}
last_candle_processed = {name: None for name in WATCHLIST}

def main():
    logging.info("Initializing Strategy Engine...")
    
    while True:
        try:
            now = dt.datetime.now()
            
            # 1. Market Hours
            if now.time() < START_TIME or now.time() > END_TIME:
                print(f"Market Closed ({now.strftime('%H:%M:%S')})...", end='\r')
                time.sleep(10)
                continue

            # 2. Update Data
            all_ltp = tsl.get_ltp(names=WATCHLIST)
            update_excel = False
            
            for name in WATCHLIST:
                if name not in all_ltp: continue
                ltp = float(all_ltp[name])
                
                # --- A. EXIT LOGIC (If Position exists) ---
                if orderbook[name]['status'] == 'ACTIVE':
                    exit_triggered, orderbook, remark = tu.check_sl_tp_exit(orderbook, name, ltp, now)
                    if exit_triggered:
                        tu.paper_exit(orderbook, completed_orders, name, ltp, now, remark)
                        update_excel = True
                    continue 

                # --- B. ENTRY LOGIC (If No Position) ---
                chart = tu.get_historical_data_safe(tsl, name, EXCHANGE, TIMEFRAME)
                chart['sma{SMA_PERIOD_1}'] = talib.SMA(chart['close'], timeperiod=SMA_PERIOD_1)
                chart['sma{SMA_PERIOD_2}'] = talib.SMA(chart['close'], timeperiod=SMA_PERIOD_2)  
                if chart is None: continue
                last_completed_time = chart.index[-2]
                

                #Entry Conditions
                if last_candle_processed[name] != last_completed_time:
                    is_crossover = tu.check_sma_crossover(chart, SMA_PERIOD_1, SMA_PERIOD_2)
                    trades_today = len([o for o in completed_orders if o['name'] == name])
                    can_trade    = trades_today < MAX_TRADES_PER_DAY
                    
                    if is_crossover and can_trade:
                        tu.paper_entry(
                            orderbook, name, ltp, 'BUY', 
                            QUANTITY, SL_PERCENT, TP_PERCENT, MAX_HOLDING_MINUTES
                        )
                        update_excel = True
                    
                    last_candle_processed[name] = last_completed_time

            # 3. Global Risk
            if tu.check_global_max_loss(completed_orders, orderbook, all_ltp, GLOBAL_MAX_LOSS):
                tu.save_to_csv(completed_orders) # Export before breaking
                break

            # 4. Excel Update
            if update_excel and USE_EXCEL_OUTPUT:
                tu.update_sheets(live_sheet, comp_sheet, orderbook, completed_orders)
            
            time.sleep(1)

        except KeyboardInterrupt:
            print("\nStrategy Stopped by User.")
            tu.save_to_csv(completed_orders) # Export on Ctrl+C
            break
        except Exception as e:
            logging.error(f"Critical Loop Error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()