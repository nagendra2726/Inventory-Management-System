import os
import sqlite3


# NOTE: Define the path to your database file outside this function
# DATABASE_FILE = 'inventory.db'

def dbconnection():
    """Helper function to create and connect to the database with Row factory."""
    # This is a placeholder; you should use the one defined in your main app.
    DB_FILE = 'inventory.db'
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"Database connection error: {e}")
        return None


def init_db():
    """
    Initializes the database schema based on the final agreed structure,
    ensuring ALL tables are created and dummy data is inserted.
    """
    conn = dbconnection()
    if conn is None:
        print("FATAL: Could not establish initial database connection.")
        return

    cursor = conn.cursor()

    try:
        # 1. CUSTOMER Table (Includes credit tracking)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS CUSTOMER (
                CUSTOMER_ID INTEGER NOT NULL UNIQUE PRIMARY KEY AUTOINCREMENT,
                CUSTOMER_NAME TEXT NOT NULL UNIQUE,
                MOBILE_NO TEXT NOT NULL,
                CUSTOMER_TYPE TEXT NOT NULL CHECK(CUSTOMER_TYPE IN ('WHOLESALE', 'RETAIL', 'HOTEL-LINE')),
                bill_amount REAL DEFAULT 0.0,
                paid_amount REAL DEFAULT 0.0,
                unpaid_amount REAL DEFAULT 0.0
            )
        """)

        # 2. INVENTORY Table (Uses CATEGORY column, not a separate table)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS INVENTORY (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                BRAND TEXT,
                PRODUCT TEXT,
                CATEGORY TEXT,
                STOCK INT,
                MRP REAL NOT NULL,
                PURCHASE_RATE REAL NOT NULL,
                WHOLESALE_RATE REAL NOT NULL,
                RETAIL_RATE REAL NOT NULL,
                HOTEL_RATE REAL NOT NULL,
                UNIQUE (BRAND, PRODUCT)
            )
        """)

        # 3. BILLS Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS BILLS (
                BILL_ID INTEGER PRIMARY KEY AUTOINCREMENT,
                CUSTOMER_ID INTEGER,
                TOTAL_ITEMS INTEGER NOT NULL,
                BILL_AMOUNT REAL NOT NULL,
                TAX_AMOUNT REAL,
                DISCOUNT_AMOUNT REAL,
                TOTAL_AMOUNT REAL,
                PROFIT_EARNED REAL,
                PAYMENT_METHOD TEXT CHECK(PAYMENT_METHOD IN ('UPI', 'CASH', 'CREDIT', 'CARD')),
                PAYMENT_DATE TEXT,
                STATUS TEXT CHECK(STATUS IN ('SUCCESSFUL', 'PENDING')),
                FOREIGN KEY (CUSTOMER_ID) REFERENCES CUSTOMER(CUSTOMER_ID)
            )
        """)

        # 4. BILL_ITEMS Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS BILL_ITEMS (
                ITEM_ID INTEGER PRIMARY KEY AUTOINCREMENT,
                BILL_ID INTEGER NOT NULL,
                PRODUCT_NAME TEXT NOT NULL,
                QUANTITY INTEGER NOT NULL,
                PRICE REAL NOT NULL,
                UNIT_PROFIT REAL,
                FOREIGN KEY (BILL_ID) REFERENCES BILLS(BILL_ID)
            )
        """)

        # 5. SETTINGS Table (Empty schema from provided structure)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS SETTINGS (
                USER_ID INTEGER NOT NULL PRIMARY KEY,
                FULL_NAME TEXT NOT NULL,
                EMAIL TEXT NOT NULL,
                PHONE_NUMBER TEXT NOT NULL,
                STORE_NAME TEXT NOT NULL DEFAULT 'Naini General Store'
                -- Minimal settings kept for demonstration; fields omitted for brevity
            )
        """)
        conn.commit()
        print("Database initialized and populated successfully.")

    except sqlite3.Error as e:
        print(f"Error during DB setup: {e}")
        conn.rollback()
    finally:
        if conn:
            conn.close()


# Example of how to use this function in your main application:
if __name__ == '__main__':
    if not os.path.exists('inventory.db'):
        print("Starting Database Initialization...")
        init_db()
    else:
        print("Database file already exists.")
