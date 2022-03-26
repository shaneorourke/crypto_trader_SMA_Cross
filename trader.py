from binance import Client
import binance_keys
import pandas as pd
import os
import sqlite3 as sql
from datetime import datetime
import csv
import configparser

config = configparser.ConfigParser()
config.read('config.cfg')

conn = sql.connect('Trader.db')
c = conn.cursor()

client = Client(binance_keys.API_KEY,binance_keys.SECRET_KEY)

binance_buy = config.get('DEFAULT','binance_buy')
printout = config.get('DEFAULT','printout')

if binance_buy == 'True':
    binance_buy = True
else:
    binance_buy = False

if printout == 'True':
    printout = True
else:
    printout = False


today = datetime.now().date()
today = str(today).replace('-','')

replace = ['(',')',',','./data/','csv','.','[',']']
replace_number = ['(',')',',','[',']']

def clean_up_sql_out(text,isnumber):
    if isnumber == 1:
        for s in replace_number:
            text = str(text).replace(s,'')      
    else:
        for s in replace:
            text = str(text).replace(s,'')
    return text

def write_to_file(log_file_name,text):
    if not os.path.exists('logs'):
        os.mkdir('logs')
    file_path = os.path.join('logs',today)
    if not os.path.exists(file_path):
        os.mkdir(file_path)
    file_name = os.path.join(file_path,log_file_name)
    text = str(datetime.now()) + '||' + str(text)
    with open(f'{file_name}', 'a', encoding='UTF8') as f:
        writer = csv.writer(f)
        writer.writerow([text])
        f.close()

def get_usdt_holdings():
    usdt = client.get_asset_balance('USDT')
    return usdt['free']

def get_minimum_trade_amount(pair):
    filters = client.get_symbol_info(f'{pair}')["filters"]
    minimum_qty = 0
    for i in filters:
        if i["filterType"] == "LOT_SIZE":
            minimum_qty=i['minQty']
    return minimum_qty

def get_quantity(pair,close):
    usdt = float(get_usdt_holdings())
    qty = float(usdt) / float(close)
    minimum_qty = float(get_minimum_trade_amount(pair))
    if 'e-' in str(qty):
        qty = 0
    else:
        position_of_1 = str(minimum_qty).find('1',)
        minimum_qty = float(str(minimum_qty)[:position_of_1+1])

        usdt = float(str(usdt)[:position_of_1+1])
        qty = float(str(qty)[:position_of_1+1])
    return qty

def last_update():
    c.execute(f'DELETE FROM last_update')
    c.execute(f'INSERT INTO last_update VALUES("{datetime.now()}")')
    conn.commit()

def gethourlydata(symbol):
    frame = pd.DataFrame(client.get_historical_klines(symbol,'1h','100 hours ago UTC'))
    frame = frame.iloc[:,:5]
    frame.columns = ['Time','Open','High','Low','Close']
    frame[['Open','High','Low','Close']] = frame[['Open','High','Low','Close']].astype(float)
    frame.Time = pd.to_datetime(frame.Time, unit='ms')
    frame['Currency'] = symbol
    return frame

def applytechnicals(df):
    df['FastSMA'] = df.Close.rolling(7).mean()
    df['SlowSMA'] = df.Close.rolling(25).mean()

def market_order(curr,qty,buy=True,binance_buy=False,price=float):
    log_datetime = datetime.now()
    error = 0
    buyprice = price
    if buy:
        side='BUY'
    else:
        side='SELL'
    if binance_buy:
        try:
            order = client.create_order(symbol=curr,side=side,type='MARKET',quantity=qty)
        except Exception as e:
            write_to_file(f'{curr}',f'{log_datetime}:Binance Error:{e}')
            error = 1
        buyprice = float(order['fills'][0]['price'])
        db_order = f'''INSERT INTO orders (Currency, quantity, market, price) 
                        VALUES("{curr}",{qty},"{side}",{buyprice})'''
    else:
        db_order = f'''INSERT INTO orders (Currency, quantity, market, price) 
                        VALUES("{curr}",{qty},"{side}",{buyprice})'''
    c.execute(db_order)
    conn.commit()
    return error

def update_position(pair,open=True):
    c.execute(f'UPDATE position SET position = {open} WHERE Currency = "{pair}"')
    conn.commit()

def get_position(pair):
    c.execute(f'SELECT position FROM position WHERE Currency = "{pair}" ORDER BY market_date DESC limit 1')
    pos = c.fetchone()
    pos = clean_up_sql_out(pos,0)
    if pos == 'None' or pos == None:
        c.execute(f'INSERT INTO position (Currency, position) VALUES ("{pair}",False)')
    conn.commit()
    return pos

def confirm_recent_cross(df):
    ## IF The Fast WAS Above the Slow (to prevent repeat buy signals or delayed)
    outcome = False
    lags = 3
    for i in range(lags):
        lookback = lags - i
        FastSMA = df.FastSMA.iloc[-lookback]
        SlowSMA = df.SlowSMA.iloc[-lookback]
        if SlowSMA > FastSMA:
            outcome = True
    return outcome

def buy_trigger(position,FastSMA,SlowSMA,df):
    if (position == '0' or position == 0) and confirm_recent_cross(df) and FastSMA > SlowSMA:
        return True
    else:
        False

def sell_trigger(position,FastSMA,SlowSMA):
    if (position == '1' or position == 1) and SlowSMA > FastSMA:
        return True
    else:
        False

def insert_log(Currency,position,close,FastSMA,SlowSMA,quantity,binance_buy,printout=False):
    c.execute(f'''INSERT INTO logs (Currency,position,close,FastSMA,SlowSMA,quantity,binance_buy) 
                VALUES ("{Currency}","{position}",{close},{FastSMA},{SlowSMA},{quantity},{binance_buy})''')
    conn.commit()
    if printout:
        print(f'Currency:{Currency}')
        print(f'position:{position}')
        print(f'Close:{round(close,2)}')
        print(f'FastSMA:{round(FastSMA,2)}')
        print(f'SlowSMA:{round(SlowSMA,2)}')
        print(f'Quantity:{round(quantity,2)}')
        print(f'binance_buy:{binance_buy}')
        print()

def strategy(pair,binance_buy,printout):
    position = get_position(pair)
    df = gethourlydata(pair)
    applytechnicals(df)
    df.to_sql(con=conn,name='hourlydata',if_exists='append')
    conn.commit()
    close = df.Close.iloc[-1]
    FastSMA = df.FastSMA.iloc[-1]
    SlowSMA = df.SlowSMA.iloc[-1]
    qty = float(get_quantity(pair,close))
    if qty == 0:
        binance_buy = False
    if buy_trigger(position,FastSMA,SlowSMA,df): #once signals are set above then wait for these for a buy
        error = market_order(pair,qty,True,binance_buy,close)
        if error != 1:
            update_position(pair,True)
    if sell_trigger(position,FastSMA,SlowSMA):
        error = market_order(pair,qty,False,binance_buy,close)
        if error != 1:
            update_position(pair,False)
    insert_log(pair,position,close,FastSMA,SlowSMA,qty,binance_buy,printout)

strategy('BTCUSDT',binance_buy,printout)
last_update()
