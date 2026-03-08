from init_db import dbconnection


def customer_count():
    conn = dbconnection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM CUSTOMER;")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def product_count():
    conn = dbconnection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM inventory;")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def low_stock():
    conn = dbconnection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM inventory WHERE stock < 30;")
    count = cursor.fetchone()[0]
    conn.close()
    return count
