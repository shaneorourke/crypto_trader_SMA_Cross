import sqlite3 as sql
conn = sql.connect('Trader.db')
c = conn.cursor()

c.execute('CREATE TABLE IF NOT EXISTS orders (Currency text, quantity float, market text, price float, market_date timestamp DEFAULT CURRENT_TIMESTAMP)')
conn.commit()

c.execute('CREATE TABLE IF NOT EXISTS position (Currency text, position boolean, market_date timestamp DEFAULT CURRENT_TIMESTAMP)')
conn.commit()

c.execute('CREATE TABLE IF NOT EXISTS trigger (Currency text, market_date timestamp DEFAULT CURRENT_TIMESTAMP)')
conn.commit()

c.execute('CREATE TABLE IF NOT EXISTS last_update (last_update timestamp DEFAULT CURRENT_TIMESTAMP)')
conn.commit()

c.execute('CREATE TABLE IF NOT EXISTS logs (Currency text, position text, close float, FastSMA float, SlowSMA float, quantity float, binance_buy boolean, log_datetime timestamp DEFAULT CURRENT_TIMESTAMP)')
conn.commit()