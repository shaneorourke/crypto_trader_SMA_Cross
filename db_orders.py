import sqlite3 as sql

conn = sql.connect('Trader.db')
c = conn.cursor()

c.execute('SELECT * FROM orders')
result = c.fetchall()
for row in result:
    print(row)
