import os
import sqlite3
import traceback
from datetime import date

from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, g
from flask_cors import CORS  # type: ignore
from werkzeug.exceptions import abort

from logic import dashboardlogic

# --- Global Configurations ---
app = Flask(__name__)
CORS(app)
app.secret_key = 'a-very-strong-secret-key-for-flashing'

DATABASE_FILE = 'inventory.db'
LOW_STOCK_THRESHOLD = 50
PER_PAGE_INVENTORY = 10
PER_PAGE_CUSTOMER = 15
PER_PAGE_ORDERS = 10
TAX_RATE = 0.05  # 5% tax


# --- Database Connection Management ---

def connect_to_database():
    """Connects to the SQLite database and returns the connection object with Row factory."""
    # Ensure the path is correct
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), DATABASE_FILE) if __file__ else DATABASE_FILE
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"Database connection error: {e}")
        return None


def get_db():
    """Opens a new database connection for the current application context."""
    if 'db' not in g:
        g.db = connect_to_database()
    return g.db


@app.teardown_appcontext
def close_db(e=None):
    """Closes the database connection at the end of the request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


# --- Database Initialization ---

def init_db(app):
    """Initializes the database schema and populates it with dummy data."""
    with app.app_context():
        conn = get_db()
        if conn is None:
            print("FATAL: Could not establish initial database connection.")
            return

        cursor = conn.cursor()

        # 1. Categories Table (Removed the auxiliary 'categories' table. Categories are now an INVENTORY column.)
        # The original code's `CREATE TABLE IF NOT EXISTS categories...` is REMOVED.

        # 2. Inventory Table (Based on user-provided structure)
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

        # 3. Customer Table
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

        # 4. Bills Table
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

        # 5. Bill Items Table
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

        # --- Initial Data Insertion ---
        try:
            cursor.execute("SELECT COUNT(*) FROM CUSTOMER")
            if cursor.fetchone()[0] == 0:
                # Categories are implicitly added via INVENTORY data

                inventory_data = [
                    ('Samsung', 'Galaxy S25', 'Electronics', 15, 75000.00, 60000.00, 65000.00, 70000.00, 68000.00),
                    ('Kwality', 'Milk Pouch', 'Groceries', 200, 60.00, 45.00, 50.00, 55.00, 52.00),
                    ('Hindustan', 'Coffee Jar', 'Groceries', 40, 450.00, 300.00, 350.00, 400.00, 380.00),
                    ('Levi\'s', 'Jeans Blue', 'Apparel', 55, 2500.00, 1500.00, 1800.00, 2200.00, 2000.00)
                ]
                cursor.executemany("""
                    INSERT OR IGNORE INTO INVENTORY 
                    (BRAND, PRODUCT, CATEGORY, STOCK, MRP, PURCHASE_RATE, WHOLESALE_RATE, RETAIL_RATE, HOTEL_RATE)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, inventory_data)

                customer_data = [
                    ('Om Khebade', '9876543210', 'RETAIL', 1000.0, 500.0, 500.0),  # Example Dues
                    ('Prajwal Deshmukh', '9988776655', 'WHOLESALE', 0.0, 0.0, 0.0),
                    ('Akshay Hotel', '9000011111', 'HOTEL-LINE', 2500.0, 0.0, 2500.0)
                ]
                cursor.executemany("""
                    INSERT OR IGNORE INTO CUSTOMER 
                    (CUSTOMER_NAME, MOBILE_NO, CUSTOMER_TYPE, bill_amount, paid_amount, unpaid_amount)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, customer_data)

            conn.commit()
            print("Database initialized successfully.")
        except sqlite3.Error as e:
            print(f"Error inserting dummy data: {e}")
            conn.rollback()
        # conn.close() handled by close_db decorator


# --- Navigational & Dummy Routes ---
@app.route('/')
def index():
    """Default route redirects to the Inventory page."""
    return render_template('index.html')


@app.route("/dashboard")
def dashboard():
    data = {
        'customer_count': dashboardlogic.customer_count(),
        'inventory_items': dashboardlogic.product_count(),
        'low_stock': dashboardlogic.low_stock()
    }
    return render_template('dashboard.html', **data)


@app.route('/report/report.html')
@app.route('/about/about.html')
@app.route('/setting/user.profile.html')
def dummy_nav_links():
    return "Navigation Link Placeholder Page"


# ====================================================================
# === BILLING MODULE (app.py logic) ===
# ====================================================================

@app.route('/billing')
def billing_page():
    return render_template('billing.html')


@app.route('/api/customers', methods=['GET'])
def get_customer_suggestions():
    """Fetches customer suggestions by name/prefix."""
    search_term = request.args.get('term', '').strip()
    if not search_term: return jsonify([])

    conn = get_db()
    if conn is None: return jsonify({"error": "Database connection failed."}), 500

    try:
        cursor = conn.cursor()
        # Using LIKE ? for prefix search
        query = "SELECT CUSTOMER_NAME, MOBILE_NO, CUSTOMER_TYPE FROM CUSTOMER WHERE CUSTOMER_NAME LIKE ?"
        cursor.execute(query, (f'{search_term}%',))
        rows = cursor.fetchall()

        customers = [
            {"name": row['CUSTOMER_NAME'].strip(), "mobile": row['MOBILE_NO'],
             "type": row['CUSTOMER_TYPE'].title().replace('-Line', '-Line')}
            for row in rows
        ]
        return jsonify(customers)
    except sqlite3.Error as e:
        print(f"Database query error: {e}")
        return jsonify({"error": "Failed to query database."}), 500


@app.route('/api/products', methods=['GET'])
def get_product_suggestions():
    """Fetches product suggestions and price/MRP based on customer type."""
    search_term = request.args.get('term', '').strip()
    customer_type = request.args.get('customer_type', '').upper().replace('-', '')

    if not search_term or not customer_type: return jsonify([])

    # Map customer type to the correct price column
    # Corrected map keys to match customer type checks later in process_bill_and_save
    price_column_map = {'WHOLESALE': 'WHOLESALE_RATE', 'RETAIL': 'RETAIL_RATE', 'HOTEL': 'HOTEL_RATE',
                        'WHOLESALER': 'WHOLESALE_RATE', 'RETAILER': 'RETAIL_RATE', 'HOTEL-LINE': 'HOTEL_RATE'}
    price_column = price_column_map.get(customer_type, 'RETAIL_RATE')

    conn = get_db()
    if conn is None: return jsonify({"error": "Database connection failed."}), 500

    try:
        cursor = conn.cursor()
        query = f"SELECT BRAND, PRODUCT, MRP, {price_column} as PRICE FROM INVENTORY WHERE UPPER(BRAND) LIKE ? OR UPPER(PRODUCT) LIKE ?"
        like_term = f'%{search_term.upper()}%'

        # Note: Inventory table has BRAND and PRODUCT columns which are used for searching.
        cursor.execute(query, (like_term, like_term))

        products = [
            {"name": f"{row['BRAND']} {row['PRODUCT']}".strip(), "price": row['PRICE'], "mrp": row['MRP']}
            for row in cursor.fetchall()
        ]
        return jsonify(products)

    except sqlite3.Error as e:
        print(f"Database query error: {e}");
        traceback.print_exc()
        return jsonify({"error": "Failed to query database."}), 500


@app.route('/api/bill/save', methods=['POST'])
def process_bill_and_save():
    """Processes the final bill data sent via AJAX POST (JSON) and updates inventory/dues."""
    data = request.get_json()
    if not data: return jsonify({"error": "Invalid JSON data provided."}), 400

    customer_name = data.get('customer_name')
    customer_phone = data.get('phone')
    customer_type_input = data.get('customer_type', 'RETAIL').upper().replace('-', '')
    payment_method = data.get('payment_method')
    products_to_bill = data.get('products', [])

    # --- FIX: Correctly map input names (RETAILER, WHOLESALER) to DB values (RETAIL, WHOLESALE) ---
    if 'HOTEL' in customer_type_input:
        customer_type_db = 'HOTEL-LINE'
    elif 'WHOLESALE' in customer_type_input:
        customer_type_db = 'WHOLESALE'
    elif 'RETAIL' in customer_type_input:
        customer_type_db = 'RETAIL'
    else:
        # Default to RETAIL if type is unrecognized, or handle as error
        customer_type_db = 'RETAIL'
        # Summary totals from frontend
    bill_amount = data.get('subtotal', 0.0)
    tax_amount = data.get('tax', 0.0)
    discount_amount = data.get('discount', 0.0)
    total_amount = data.get('total', 0.0)

    if not customer_name or not customer_phone or not products_to_bill:
        return jsonify({"error": "Missing customer or product data."}), 400

    conn = get_db()
    if conn is None: return jsonify({"error": "Database connection failed."}), 500

    try:
        cursor = conn.cursor()

        # 1. Customer Handling
        cursor.execute("SELECT CUSTOMER_ID, CUSTOMER_TYPE FROM CUSTOMER WHERE MOBILE_NO=?", (customer_phone,))
        customer_row = cursor.fetchone()
        if customer_row:
            customer_id = customer_row['CUSTOMER_ID']
        else:
            # Insert new customer
            cursor.execute("INSERT INTO CUSTOMER (CUSTOMER_NAME, MOBILE_NO, CUSTOMER_TYPE) VALUES (?, ?, ?)",
                           (customer_name, customer_phone, customer_type_db))
            customer_id = cursor.lastrowid

        # --- 2. Per-Item Profit Calculation and Inventory Update ---
        total_items = 0
        profit_earned = 0.0
        bill_items_data = []

        for item in products_to_bill:
            prod_name = item['name']
            qty = item['quantity']
            sell_price = item['price']

            # Find the product's purchase rate (COST PRICE) and current stock
            # The split logic must match the product name concatenation in get_product_suggestions
            parts = prod_name.split(' ', 1)
            brand_search = parts[0]
            product_search = parts[1] if len(parts) > 1 else prod_name

            cursor.execute("SELECT ID, PURCHASE_RATE, STOCK FROM INVENTORY WHERE BRAND=? AND PRODUCT=?",
                           (brand_search, product_search))
            inventory_row = cursor.fetchone()

            if not inventory_row:
                raise Exception(f"Product not found in inventory: {prod_name}")

            # Check stock availability
            current_stock = inventory_row['STOCK']
            if current_stock < qty:
                raise Exception(f"Insufficient stock for {prod_name}. Available: {current_stock}")

            purchase_rate = inventory_row['PURCHASE_RATE'] if inventory_row['PURCHASE_RATE'] is not None else 0.0

            # CORE PROFIT LOGIC: (Selling Price - Cost Price) * Quantity
            unit_profit = sell_price - purchase_rate
            profit_earned += unit_profit * qty
            total_items += qty

            bill_items_data.append((prod_name, qty, sell_price, unit_profit))

            # Inventory Update
            cursor.execute("UPDATE INVENTORY SET STOCK = STOCK - ? WHERE ID=?",
                           (qty, inventory_row['ID']))

        # 3. Insert main BILLS record
        payment_date = date.today().isoformat()
        status = "PENDING" if payment_method.upper() == 'CREDIT' else "SUCCESSFUL"

        cursor.execute("""
            INSERT INTO BILLS (
                CUSTOMER_ID, TOTAL_ITEMS, BILL_AMOUNT, TAX_AMOUNT, DISCOUNT_AMOUNT, TOTAL_AMOUNT, PROFIT_EARNED, PAYMENT_METHOD, PAYMENT_DATE, STATUS
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            customer_id, total_items, bill_amount, tax_amount, discount_amount, total_amount, profit_earned,
            payment_method.upper(),
            payment_date, status
        ))
        bill_id = cursor.lastrowid

        # 4. Update Customer Dues if Credit
        if payment_method.upper() == 'CREDIT':
            cursor.execute("""
                UPDATE CUSTOMER SET unpaid_amount = unpaid_amount + ?, bill_amount = bill_amount + ? 
                WHERE CUSTOMER_ID = ?
            """, (total_amount, total_amount, customer_id))

        # 5. Insert BILL_ITEMS records
        bill_items_insert_data = [(bill_id, prod, qty, price, unit_profit) for prod, qty, price, unit_profit in
                                  bill_items_data]
        cursor.executemany("""
            INSERT INTO BILL_ITEMS (BILL_ID, PRODUCT_NAME, QUANTITY, PRICE, UNIT_PROFIT) 
            VALUES (?, ?, ?, ?, ?)
        """, bill_items_insert_data)

        conn.commit()

        return jsonify({
            "message": f"Bill #{bill_id} saved successfully.",
            "bill_id": bill_id,
            "total_amount": round(total_amount, 2),
            "profit_earned": round(profit_earned, 2)
        })

    except sqlite3.Error as e:
        conn.rollback()
        print(f"SQLite Transaction Error: {e}");
        traceback.print_exc()
        return jsonify({"error": f"Database Transaction Failed: {e}"}), 500
    except Exception as e:
        conn.rollback()
        print(f"General Error: {e}");
        traceback.print_exc()
        return jsonify({"error": f"General Server Error: {e}"}), 500


# ====================================================================
# === INVENTORY MODULE (harshit.py logic) ===
# ====================================================================

@app.route('/inventory')
def inventory_page():
    conn = get_db()
    # Removed the conn.close() from the finally block as get_db/close_db handle it via g.db/teardown
    if conn is None: abort(500)
    try:
        cursor = conn.cursor()
        page = request.args.get('page', 1, type=int)
        search_query = request.args.get('search', '').strip()
        sort_by = request.args.get('sort_by', 'ID')
        sort_order = request.args.get('sort_order', 'ASC')

        valid_sort_columns = ['ID', 'BRAND', 'PRODUCT', 'STOCK', 'MRP', 'CATEGORY']
        if sort_by not in valid_sort_columns: sort_by = 'ID'
        if sort_order.upper() not in ['ASC', 'DESC']: sort_order = 'ASC'

        base_query = "FROM INVENTORY WHERE 1=1"
        params = []
        if search_query:
            base_query += " AND (PRODUCT LIKE ? OR BRAND LIKE ? OR CATEGORY LIKE ?)"
            params.extend([f"%{search_query}%"] * 3)

        total_sql = f"SELECT COUNT(*) {base_query}"
        total_products = cursor.execute(total_sql, params).fetchone()[0] or 0
        total_pages = (total_products + PER_PAGE_INVENTORY - 1) // PER_PAGE_INVENTORY if total_products > 0 else 1
        offset = (page - 1) * PER_PAGE_INVENTORY

        sql = f"""
            SELECT ID, BRAND, PRODUCT, STOCK, MRP, PURCHASE_RATE,
                   WHOLESALE_RATE, RETAIL_RATE, HOTEL_RATE, CATEGORY
            {base_query} ORDER BY {sort_by} {sort_order} LIMIT ? OFFSET ?
        """
        query_params = params + [PER_PAGE_INVENTORY, offset]
        products = cursor.execute(sql, query_params).fetchall()

        low_stock_sql = f"SELECT PRODUCT, STOCK FROM INVENTORY WHERE STOCK < {LOW_STOCK_THRESHOLD} ORDER BY STOCK ASC LIMIT 10"
        low_stock_products = cursor.execute(low_stock_sql).fetchall()

        # CORRECTED: Get unique categories directly from INVENTORY table
        categories_sql = "SELECT DISTINCT CATEGORY FROM INVENTORY WHERE CATEGORY IS NOT NULL AND CATEGORY != '' ORDER BY CATEGORY ASC"
        categories = [row['CATEGORY'] for row in cursor.execute(categories_sql).fetchall()]

        value_sql = "SELECT SUM(STOCK * PURCHASE_RATE) FROM INVENTORY"
        total_inventory_value = cursor.execute(value_sql).fetchone()[0] or 0

        category_chart_sql = """
            SELECT 
                CASE 
                    WHEN CATEGORY IS NULL OR CATEGORY = '' THEN 'Unknown'
                    ELSE CATEGORY 
                END as CATEGORY,
                COUNT(ID) as count 
            FROM INVENTORY 
            GROUP BY CATEGORY 
            ORDER BY count DESC
        """
        category_results = cursor.execute(category_chart_sql).fetchall()

        category_labels = [row['CATEGORY'] for row in category_results] if category_results else ['No Data']
        category_data = [row['count'] for row in category_results] if category_results else [1]

        return render_template(
            'inventory.html',
            products=products, page=page, total_pages=total_pages, low_stock_products=low_stock_products,
            categories=categories, search_query=search_query, sort_by=sort_by, sort_order=sort_order,
            total_inventory_value=total_inventory_value, category_labels=category_labels, category_data=category_data
        )

    except Exception as e:
        # This catch block prevents the redirect loop by stopping if the template is missing
        if 'inventory.html' not in str(e):
            print(f"Error caught in inventory_page: {str(e)}");
            traceback.print_exc()

        # The redirect inside a try/except block for a potentially missing template can be tricky
        # Keep the flash but return an abort or an error template if the template itself is missing.
        flash(f"Error loading inventory: {str(e)}. Please check database or template.", "danger")
        return redirect(url_for('inventory_page'))
    # Removed finally block since get_db/teardown handles conn closing


@app.route('/inventory/add', methods=['POST'])
def inventory_add():
    conn = get_db()
    if conn is None: abort(500)
    try:
        cursor = conn.cursor()
        category = request.form.get('category')
        new_category = request.form.get('new_category', '').strip()
        final_category = new_category if new_category else category

        if not final_category:
            flash("Category is required.", "danger")
            return redirect(url_for('inventory_page'))

        # Removed redundant logic for inserting into 'categories' table
        # Category is just a text column in INVENTORY now.

        sql = """
            INSERT INTO INVENTORY (BRAND, PRODUCT, STOCK, MRP, PURCHASE_RATE, WHOLESALE_RATE, RETAIL_RATE, HOTEL_RATE, CATEGORY)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        cursor.execute(sql, (
            request.form.get('brand'), request.form.get('product'),
            request.form.get('stock'), request.form.get('mrp'),
            request.form.get('purchase_rate'), request.form.get('wholesale_rate'),
            request.form.get('retail_rate'), request.form.get('hotel_rate'),
            final_category
        ))
        conn.commit()
        flash("Product added successfully!", "success")
    except sqlite3.IntegrityError:
        flash("Error: A product with similar BRAND and PRODUCT details might already exist.", "danger")
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")
    finally:
        # Removed finally block since get_db/teardown handles conn closing
        pass  # Leaving pass for structure, but conn is closed by @app.teardown_appcontext
    return redirect(url_for('inventory_page'))


@app.route('/inventory/edit/<int:product_id>', methods=['POST'])
def inventory_edit(product_id):
    conn = get_db()
    if conn is None: abort(500)
    try:
        cursor = conn.cursor()
        sql = """
            UPDATE INVENTORY SET BRAND = ?, PRODUCT = ?, STOCK = ?, MRP = ?,
            PURCHASE_RATE = ?, WHOLESALE_RATE = ?, RETAIL_RATE = ?, HOTEL_RATE = ?, CATEGORY = ?
            WHERE ID = ?
        """
        cursor.execute(sql, (
            request.form.get('brand'), request.form.get('product'), request.form.get('stock'),
            request.form.get('mrp'), request.form.get('purchase_rate'), request.form.get('wholesale_rate'),
            request.form.get('retail_rate'), request.form.get('hotel_rate'), request.form.get('category'),
            product_id
        ))
        conn.commit()
        flash(f"Product ID {product_id} updated successfully!", "success")
    except Exception as e:
        flash(f"Error updating product: {e}", "danger")
    finally:
        # Removed finally block since get_db/teardown handles conn closing
        pass
    return redirect(url_for('inventory_page'))


@app.route('/api/inventory/delete', methods=['POST'])
def inventory_delete():
    conn = get_db()
    if conn is None: return jsonify({"status": "error", "message": "Database error"}), 500
    try:
        cursor = conn.cursor()
        data = request.get_json()
        product_ids = data.get('ids')
        current_page = data.get('current_page', 1)

        if not product_ids:
            return jsonify({"status": "error", "message": "No IDs provided"}), 400

        placeholders = ', '.join('?' for _ in product_ids)
        sql = f"DELETE FROM INVENTORY WHERE ID IN ({placeholders})"
        cursor.execute(sql, product_ids)
        conn.commit()
        flash(f"Successfully deleted {len(product_ids)} product(s).", "success")

        remaining_products = cursor.execute("SELECT COUNT(*) FROM INVENTORY").fetchone()[0] or 0
        new_total_pages = (
                                  remaining_products + PER_PAGE_INVENTORY - 1) // PER_PAGE_INVENTORY if remaining_products > 0 else 1

        redirect_page = min(current_page, new_total_pages)

        return jsonify({"status": "success", "redirect_page": redirect_page})

    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        # Removed finally block since get_db/teardown handles conn closing
        pass


@app.route('/api/inventory/low_stock_all')
def get_all_low_stock():
    conn = get_db()
    if conn is None: return jsonify([]), 500
    try:
        sql = f"SELECT PRODUCT, STOCK FROM INVENTORY WHERE STOCK < {LOW_STOCK_THRESHOLD} ORDER BY STOCK ASC"
        results = conn.execute(sql).fetchall()
        return jsonify([dict(row) for row in results])
    finally:
        # Removed finally block since get_db/teardown handles conn closing
        pass


@app.route('/api/inventory/<int:product_id>')
def get_product_data(product_id):
    conn = get_db()
    if conn is None: return jsonify({"status": "error", "message": "Database error"}), 500
    try:
        sql = "SELECT * FROM INVENTORY WHERE ID = ?"
        result = conn.execute(sql, (product_id,)).fetchone()
        if result:
            return jsonify({k: str(v) for k, v in dict(result).items()})
        return jsonify({"status": "error", "message": "Product not found"}), 404
    finally:
        # Removed finally block since get_db/teardown handles conn closing
        pass


@app.route('/api/categories', methods=['GET'])
def get_categories():
    conn = get_db()
    if conn is None: return jsonify([]), 500
    try:
        # CORRECTED: Fetch categories from the INVENTORY table's CATEGORY column
        categories_sql = "SELECT DISTINCT CATEGORY FROM INVENTORY WHERE CATEGORY IS NOT NULL AND CATEGORY != '' ORDER BY CATEGORY ASC"
        categories = [row['CATEGORY'] for row in conn.execute(categories_sql).fetchall()]
        return jsonify(categories)
    finally:
        # Removed finally block since get_db/teardown handles conn closing
        pass


# --- Reports Routes (From harshit.py logic) ---

@app.route('/reports/customer')
def customer_report():
    conn = get_db()
    if conn is None: abort(500)
    try:
        cursor = conn.cursor()
        page = request.args.get('page', 1, type=int)
        search_query = request.args.get('search', '').strip()

        base_query = "FROM CUSTOMER WHERE 1=1"
        params = []
        if search_query:
            base_query += " AND (CUSTOMER_NAME LIKE ? OR CUSTOMER_ID LIKE ? OR MOBILE_NO LIKE ?)"
            params.extend([f"%{search_query}%"] * 3)

        total_sql = f"SELECT COUNT(*) {base_query}"
        total_customers = cursor.execute(total_sql, params).fetchone()[0] or 0
        total_pages = (total_customers + PER_PAGE_CUSTOMER - 1) // PER_PAGE_CUSTOMER if total_customers > 0 else 1
        offset = (page - 1) * PER_PAGE_CUSTOMER

        customers_sql = f"""
            SELECT CUSTOMER_ID, CUSTOMER_NAME, MOBILE_NO, CUSTOMER_TYPE, unpaid_amount
            {base_query} ORDER BY CUSTOMER_ID ASC LIMIT ? OFFSET ?
        """
        query_params = params + [PER_PAGE_CUSTOMER, offset]
        customers = cursor.execute(customers_sql, query_params).fetchall()

        return render_template(
            'customer_report.html',
            customers=customers, page=page, total_pages=total_pages, search_query=search_query
        )
    except Exception as e:
        flash(f"Error loading customer report: {e}", "danger")
        # Assuming a redirect to the index if reports_hub is a placeholder
        return redirect(url_for('index'))
    finally:
        # Removed finally block since get_db/teardown handles conn closing
        pass


@app.route('/reports/order_history')
def order_history():
    conn = get_db()
    if conn is None: abort(500)
    try:
        cursor = conn.cursor()
        page = request.args.get('page', 1, type=int)
        search_query = request.args.get('search', '').strip()

        base_query = """
            FROM BILLS b
            JOIN CUSTOMER c ON b.CUSTOMER_ID = c.CUSTOMER_ID
            WHERE 1=1
        """
        params = []
        if search_query:
            base_query += " AND (c.CUSTOMER_NAME LIKE ? OR b.BILL_ID LIKE ?)"
            params.extend([f"%{search_query}%"] * 2)

        total_sql = f"SELECT COUNT(*) {base_query}"
        total_orders = cursor.execute(total_sql, params).fetchone()[0] or 0
        total_pages = (total_orders + PER_PAGE_ORDERS - 1) // PER_PAGE_ORDERS if total_orders > 0 else 1
        offset = (page - 1) * PER_PAGE_ORDERS

        orders_sql = f"""
            SELECT
                b.BILL_ID,
                b.PAYMENT_DATE,
                b.STATUS,
                b.TOTAL_AMOUNT,
                c.CUSTOMER_NAME,
                c.MOBILE_NO
            {base_query}
            ORDER BY b.PAYMENT_DATE DESC, b.BILL_ID DESC
            LIMIT ? OFFSET ?
        """
        query_params = params + [PER_PAGE_ORDERS, offset]
        orders = cursor.execute(orders_sql, query_params).fetchall()

        return render_template(
            'order_history.html',
            orders=orders, page=page, total_pages=total_pages, total_orders=total_orders, search_query=search_query
        )

    except Exception as e:
        flash(f"Error loading order history: {e}", "danger")
        # Assuming a redirect to the index if reports_hub is a placeholder
        return redirect(url_for('index'))
    finally:
        # Removed finally block since get_db/teardown handles conn closing
        pass


# All other Report routes (credit, stock, downloads) need a valid 'reports.html' template
@app.route('/reports')
def reports_hub():
    # If this template is missing, routes like /reports/customer will fail.
    return render_template('reports.html')


# --- Main Execution ---
if __name__ == '__main__':
    # Initialize DB only if file doesn't exist
    if not os.path.exists(DATABASE_FILE):
        print(f"Database file '{DATABASE_FILE}' not found. Initializing database...")
        # Since init_db needs the app context, we run it this way
        with app.app_context():
            init_db(app)
    else:
        # Check if INVENTORY is created but categories table exists (legacy cleanup, for future runs)
        # This prevents an error if the user ran the previous version and deleted the db file, but
        # is harmless if run on an existing, correctly-structured DB.
        with app.app_context():
            conn = get_db()
            if conn:
                try:
                    # Attempt to drop the obsolete table if it exists
                    conn.execute("DROP TABLE IF EXISTS categories")
                    conn.commit()
                    print("Cleaned up obsolete 'categories' table.")
                except Exception as e:
                    print(f"Error during category table cleanup: {e}")

    print(f"Starting server, using database '{DATABASE_FILE}'...")
    print("Access Billing at http://127.0.0.1:5001/billing")
    print("Access Inventory at http://127.0.0.1:5001/inventory")
    app.run(debug=True, host='0.0.0.0', port=5001)
