import sqlite3
import os
import shutil

# Database path (absolute path recommended)
DB_PATH = '/home/irieman/Pulpit/1 IT/Antigravity/Simple Investing/instance/financial_data_v2.db'
BACKUP_PATH = DB_PATH + '.cleanup.bak'

def cleanup_database():
    """
    Performs the final database cleanup:
    1. Removes the foreign key constraint from the etfs table.
    2. Drops the legacy inflation_historical_periods table.
    """
    # Create a backup before proceeding
    if os.path.exists(DB_PATH):
        print(f"Creating backup at {BACKUP_PATH}...")
        shutil.copy2(DB_PATH, BACKUP_PATH)
    else:
        print(f"Error: Database file not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # --- 1. Recreate etfs table without FK ---
        print("Recreating etfs table to remove foreign key constraint...")
        # Create new table with same structure but no FK
        cursor.execute("""
            CREATE TABLE etfs_cleanup (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                name VARCHAR NOT NULL,
                ticker VARCHAR NOT NULL,
                isin VARCHAR NOT NULL,
                asset_type VARCHAR NOT NULL,
                currency VARCHAR NOT NULL,
                external_ticker VARCHAR NOT NULL
            )
        """)
        # Copy data
        cursor.execute("""
            INSERT INTO etfs_cleanup (id, name, ticker, isin, asset_type, currency, external_ticker)
            SELECT id, name, ticker, isin, asset_type, currency, external_ticker FROM etfs
        """)
        
        # Drop old etfs and rename
        cursor.execute("DROP TABLE etfs")
        cursor.execute("ALTER TABLE etfs_cleanup RENAME TO etfs")
        
        # --- 2. Drop legacy table ---
        print("Dropping legacy inflation_historical_periods table...")
        cursor.execute("DROP TABLE IF EXISTS inflation_historical_periods")

        conn.commit()
        print("Database cleanup completed successfully.")

    except Exception as e:
        conn.rollback()
        print(f"An error occurred during cleanup: {e}")
        print("Rolled back changes.")
    finally:
        conn.close()

if __name__ == "__main__":
    cleanup_database()
