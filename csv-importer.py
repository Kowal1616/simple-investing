import csv
import sqlite3
import sys
import os

'''
usage: python csv-importer.py CSV-files/to_be_imported_file.csv
'''

# Connect SQLite database
db = sqlite3.connect("instance/financial_data.db")

# Get the filename from the command line arguments
file_path = sys.argv[1]

# Open the CSV file and create a DictReader
reader = csv.DictReader(open(file_path))

# Get the column names from the first row
columns = reader.fieldnames

# Get the base name of the file_path
base = os.path.basename(file_path)  # This will return "file_name.csv"

# Split the base name into the filename and extension
filename, _ = os.path.splitext(base)  # This will return "file_name"

'''
# Open csv file
with open(filename, "r") as file:
    reader = csv.reader(file)
    next(reader)
    csv_data = []
    for row in reader:
        csv_data.append(row)
'''

# Create the INSERT statement
query = f"INSERT INTO {filename} ({', '.join(columns)}) VALUES ({', '.join(['?' for _ in columns])})"

# Loop through the rows in the reader
for row in reader:
    # Get the values from the row
    values = [row[column] for column in columns]

    # Execute the INSERT statement
    try:
        db.execute(query, values)
    except Exception as e:
        print(f"An error occured: {e}")

'''
# Choose SQL INSERT statement for the right table via filename
if filename == "CSV-files/inflation_rates.csv":
    for row in csv_data:
        try:
            db.execute(
                "INSERT INTO inflation (year, EUR_inflation_rate, PLN_inflation_rate) VALUES (?,?,?)",
                row,
            )
        except Exception as e:
            print(f"An error occured: {e}")

elif filename == "CSV-files/inflation_historical_periods.csv":
    for row in csv_data:
        try:
            db.execute(
                "INSERT INTO inflation_historical_periods (currency, inflation5, inflation10, inflation20, inflation30) VALUES (?,?,?,?,?)",
                row,
            )
        except Exception as e:
            print(f"An error occured: {e}")

elif filename == "CSV-files/etfs.csv":
    for row in csv_data:
        try:
            db.execute(
                "INSERT INTO etfs (name, ticker, isin, asset_type, currency, yfinance_name, alphavantage_name) VALUES (?,?,?,?,?,?,?)",
                row,
            )
        except Exception as e:
            print(f"An error occured: {e}")

elif filename == "CSV-files/historical_data_etfs.csv":
    for row in csv_data:
        try:
            db.execute(
                "INSERT INTO historical_data_etfs (date, etf1_price, etf2_price, etf3_price, etf4_price, etf5_price, etf6_price) VALUES (?,?,?,?,?,?,?)",
                row,
            )
        except Exception as e:
            print(f"An error occured: {e}")

elif filename == "CSV-files/portfolios.csv":
    for row in csv_data:
        try:
            db.execute(
                "INSERT INTO portfolios (name, assets, stocks, bonds, other, return5, return10, return20, return30) VALUES (?,?,?,?,?,?,?,?,?)",
                row,
            )
        except Exception as e:
            print(f"An error occured: {e}")

elif filename == "CSV-files/portfolio_composition.csv":
    for row in csv_data:
        try:
            db.execute(
                "INSERT INTO portfolio_composition (portfolio_id, etf_id, percentage) VALUES (?,?,?)",
                row,
            )
        except Exception as e:
            print(f"An error occured: {e}")

else:
    print("ERROR: No import made")
'''

# Commit the changes
db.commit()

# Close the connection
db.close()
