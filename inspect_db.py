import sqlite3
import os

db_path = 'instance/financial_data.db'

if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("--- Tables ---")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
for table in tables:
    print(f"Table: {table[0]}")
    cursor.execute(f"PRAGMA table_info({table[0]})")
    columns = cursor.fetchall()
    for col in columns:
        print(f"  Column: {col[1]} ({col[2]})")

print("\n--- Latest Data in historical_data_etfs ---")
cursor.execute("SELECT MAX(date) FROM historical_data_etfs")
print(f"Latest date: {cursor.fetchone()[0]}")

print("\n--- ETFs ---")
cursor.execute("SELECT id, name, ticker, yfinance_name, alphavantage_name FROM etfs")
etfs = cursor.fetchall()
for etf in etfs:
    print(f"ID: {etf[0]}, Name: {etf[1]}, Ticker: {etf[2]}, YF: {etf[3]}, AV: {etf[4]}")

conn.close()
