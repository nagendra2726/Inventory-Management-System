# --- Combined D-Mart Application ---
# To run this file, first install the Pillow library: pip install Pillow
# Then, in the terminal, run: python app.py

import os
import sqlite3
import traceback
import sys
from datetime import date, timedelta, datetime
from collections import OrderedDict
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, g, send_from_directory, session
from flask_cors import CORS  # type: ignore
from werkzeug.exceptions import abort
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image, ImageDraw, ImageFont
import functools

# --- Global Configurations ---
app = Flask(__name__)
CORS(app)
app.secret_key = 'a-very-strong-secret-key-for-flashing'

DATABASE_FILE = os.environ.get('DATABASE_URL', 'inventory.db')
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

LOW_STOCK_THRESHOLD = 50
PER_PAGE_INVENTORY = 10
PER_PAGE_CUSTOMER = 15
PER_PAGE_ORDERS = 10
TAX_RATE = 0.05  # 5% tax


# --- App-Level Setup (Runs on startup for Render/Gunicorn) ---
def setup_app():
    """Initial setup to ensure DB and folders exist."""
    print(f"Checking application setup. Database: {DATABASE_FILE}")
    
    # Pre-run checks for Pillow
    try:
        from PIL import Image
    except ImportError:
        print("WARNING: Pillow not installed. Image features may fail.")

    db_path = DATABASE_FILE
    if not os.path.isabs(db_path):
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), DATABASE_FILE)
    
    # Initialize DB if it doesn't exist
    if not os.path.exists(db_path):
        print(f"Database file '{db_path}' not found. Initializing database...")
        with app.app_context():
            init_db(app)
    else:
        # Legacy cleanup for old table, if it exists
        with app.app_context():
            conn = connect_to_database() # Direct call since g might not be ready
            if conn:
                try:
                    conn.execute("DROP TABLE IF EXISTS categories")
                    conn.commit()
                    conn.close()
                    print("Cleaned up obsolete 'categories' table.")
                except Exception:
                    pass

# Call setup immediately
setup_app()


# --- Helper Functions (For User Profile Module) ---

def allowed_file(filename):
    """Checks if the file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def create_placeholder_image(path, text, size=(100, 100)):
    """Creates a simple placeholder image to prevent 404 errors."""
    if not os.path.exists(path):
        try:
            img = Image.new('RGB', size, color = (230, 230, 230))
            d = ImageDraw.Draw(img)
            try:
                font = ImageFont.truetype("arial.ttf", 15)
            except IOError:
                font = ImageFont.load_default()
            d.text((10,10), text, fill=(100,100,100), font=font)
            img.save(path)
            print(f"Created placeholder image: {path}")
        except Exception as e:
            print(f"Could not create placeholder image: {e}")

# --- Authentication Decorator ---

def login_required(view):
    """View decorator that redirects anonymous users to the login page."""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('login'))
        return view(**kwargs)
    return wrapped_view

@app.before_request
def load_logged_in_user():
    """If a user id is stored in the session, load the user object from the database into g.user."""
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        conn = get_db()
        g.user = conn.execute(
            'SELECT * FROM USERS WHERE ID = ?', (user_id,)
        ).fetchone()


# --- Database Connection Management ---

def connect_to_database():
    """Connects to the SQLite database and returns the connection object with Row factory."""
    # Use absolute path if it's just a filename, otherwise use as is (for persistent disks)
    if not os.path.isabs(DATABASE_FILE):
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), DATABASE_FILE)
    else:
        db_path = DATABASE_FILE
        
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


# --- Database Initialization (Merged) ---

def init_db(app):
    """Initializes the database schema and populates it with dummy data."""
    with app.app_context():
        # --- Create Uploads Folder & Placeholders (from profile app) ---
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)
            print(f"Created directory: {UPLOAD_FOLDER}")
        
        create_placeholder_image(os.path.join(UPLOAD_FOLDER, 'default-avatar.png'), "User")
        create_placeholder_image(os.path.join(UPLOAD_FOLDER, 'default-logo.png'), "Logo")

        conn = get_db()
        if conn is None:
            print("FATAL: Could not establish initial database connection.")
            return

        cursor = conn.cursor()

        # 1. Inventory Table
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

        # 2. Customer Table
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

        # 3. Bills Table
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

        # 4. Bill Items Table
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
        
        # 5. Settings Table (Added from profile app)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS SETTINGS (
                USER_ID INTEGER PRIMARY KEY DEFAULT 1,
                FULL_NAME TEXT,
                EMAIL TEXT,
                PHONE_NUMBER TEXT,
                SOCIAL_MEDIA TEXT,
                PHOTO_URL TEXT,
                STORE_ID INTEGER DEFAULT 1,
                STORE_NAME TEXT,
                STORE_NO TEXT,
                ADDRESS TEXT,
                GST_NUMBER TEXT,
                LICENSE_URL TEXT,
                LOGO_URL TEXT
            )
        """)

        # 6. USERS Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS USERS (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                FULL_NAME TEXT NOT NULL,
                EMAIL TEXT UNIQUE NOT NULL,
                PHONE TEXT,
                PASSWORD_HASH TEXT NOT NULL,
                CREATED_AT TEXT DEFAULT CURRENT_TIMESTAMP,
                PROFILE_IMAGE TEXT DEFAULT '/uploads/default-avatar.png'
            )
        """)

        # --- Initial Data Insertion ---
        try:
            cursor.execute("SELECT COUNT(*) FROM CUSTOMER")
            if cursor.fetchone()[0] == 0:
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
                    ('Om Khebade', '9876543210', 'RETAIL', 1000.0, 500.0, 500.0),
                    ('Prajwal Deshmukh', '9988776655', 'WHOLESALE', 0.0, 0.0, 0.0),
                    ('Akshay Hotel', '9000011111', 'HOTEL-LINE', 2500.0, 0.0, 2500.0),
                    ('Ajit Kumar', '9876543211', 'RETAIL', 34500.0, 0.0, 34500.0),
                    ('Parth', '9876543212', 'WHOLESALE', 39100.0, 0.0, 39100.0),
                ]
                cursor.executemany("""
                    INSERT OR IGNORE INTO CUSTOMER 
                    (CUSTOMER_NAME, MOBILE_NO, CUSTOMER_TYPE, bill_amount, paid_amount, unpaid_amount)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, customer_data)

            # Insert default settings if table is empty (from profile app)
            cursor.execute("SELECT COUNT(*) FROM SETTINGS")
            if cursor.fetchone()[0] == 0:
                print("Settings table is empty. Inserting default data...")
                cursor.execute("""
                    INSERT INTO SETTINGS (
                        FULL_NAME, EMAIL, PHONE_NUMBER, SOCIAL_MEDIA, PHOTO_URL, 
                        STORE_ID, STORE_NAME, STORE_NO, ADDRESS, GST_NUMBER, LICENSE_URL, LOGO_URL
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    'OM KHEBADE', 'om.khebade@example.com', '', '', '/uploads/default-avatar.png', 
                    1, 'Naini General Store', '', '', '', '', '/uploads/default-logo.png'
                ))


            conn.commit()
            print("Database initialized successfully.")
        except sqlite3.Error as e:
            print(f"Error inserting dummy data: {e}")
            conn.rollback()


# ====================================================================
# === USER PROFILE MODULE (Added from profile app) ===
# ====================================================================

@app.route('/store_settings')
@login_required
def store_settings():
    """Renders the main user profile and store settings page."""
    conn = get_db()
    store_name = "Naini General Store" # Default name in case of an error
    if conn:
        try:
            settings = conn.execute("SELECT STORE_NAME FROM SETTINGS WHERE USER_ID = 1").fetchone()
            if settings and settings['STORE_NAME']:
                store_name = settings['STORE_NAME']
        except sqlite3.Error as e:
            print(f"Error fetching store name for profile page: {e}")
            
    return render_template('user_profile.html', STORE_NAME=store_name)

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """Serves uploaded files from the UPLOAD_FOLDER."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/settings', methods=['GET', 'POST'])
@login_required
def manage_settings():
    """Gets or saves user and store information."""
    conn = get_db()
    if not conn: return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cursor = conn.cursor()
        if request.method == 'POST':
            data = request.get_json()
            if not data:
                return jsonify({"error": "No data received."}), 400

            cursor.execute("""
                UPDATE SETTINGS SET 
                    FULL_NAME = ?, EMAIL = ?, PHONE_NUMBER = ?, SOCIAL_MEDIA = ?,
                    STORE_NAME = ?, STORE_NO = ?, ADDRESS = ?, GST_NUMBER = ?
                WHERE USER_ID = 1
            """, (
                data.get('fullName'), data.get('email'), data.get('phone'), data.get('social'),
                data.get('storeName'), data.get('storeNo'), data.get('address'), data.get('gstNumber')
            ))
            conn.commit()
            return jsonify({"message": "Settings successfully saved!"})

        else: # GET request
            settings = cursor.execute("SELECT * FROM SETTINGS WHERE USER_ID = 1").fetchone()
            if not settings:
                return jsonify({}), 200 
            
            response = jsonify(dict(settings))
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            return response
    
    except Exception as e:
        print(f"ERROR in manage_settings: {e}")
        if conn: conn.rollback()
        return jsonify({"error": "Server error occurred"}), 500

@app.route('/api/upload-file', methods=['POST'])
@login_required
def upload_file_route():
    """Handles uploads for profile photo, store logo, or license."""
    if 'file' not in request.files: return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    upload_type = request.form.get('type')

    if file.filename == '' or not upload_type: return jsonify({"error": "No selected file or type"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(f"{upload_type}_{datetime.now().timestamp()}_{file.filename}")
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(save_path)
        
        conn = get_db()
        try:
            cursor = conn.cursor()
            db_path = f'/uploads/{filename}'
            
            column_map = {'profile': 'PHOTO_URL', 'logo': 'LOGO_URL', 'license': 'LICENSE_URL'}
            column_to_update = column_map.get(upload_type)

            if not column_to_update:
                return jsonify({"error": "Invalid upload type"}), 400

            query = f"UPDATE SETTINGS SET {column_to_update} = ? WHERE USER_ID = 1"
            cursor.execute(query, (db_path,))
            conn.commit()
            
            return jsonify({"message": "File uploaded successfully!", "path": db_path})
        except Exception as e:
            print(f"Database error during file upload: {e}")
            if conn: conn.rollback()
            return jsonify({"error": "Failed to save file path"}), 500
    
    return jsonify({"error": "File type not allowed"}), 400


# ====================================================================
# === AUTHENTICATION MODULE ===
# ====================================================================

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    try:
        if request.method == 'POST':
            full_name = request.form.get('full_name')
            email = request.form.get('email')
            phone = request.form.get('phone')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')

            error = None

            if not full_name or not email or not password:
                error = 'Required fields missing.'
            elif password != confirm_password:
                error = 'Passwords do not match.'

            if error is None:
                conn = get_db()
                try:
                    conn.execute(
                        "INSERT INTO USERS (FULL_NAME, EMAIL, PHONE, PASSWORD_HASH) VALUES (?, ?, ?, ?)",
                        (full_name, email, phone, generate_password_hash(password, method='pbkdf2:sha256')),
                    )
                    conn.commit()
                    flash('Registration successful! Please login.', 'success')
                    return redirect(url_for('login'))
                except sqlite3.IntegrityError:
                    error = f"Email {email} is already registered."
            
            flash(error, 'danger')

        return render_template('signup.html')
    except Exception as e:
        print("DEBUG SIGNUP ERROR:")
        traceback.print_exc()
        return f"Internal Server Error: {e}", 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    try:
        if request.method == 'POST':
            email = request.form.get('email')
            password = request.form.get('password')
            
            conn = get_db()
            user = conn.execute(
                'SELECT * FROM USERS WHERE EMAIL = ?', (email,)
            ).fetchone()

            if user is None or not check_password_hash(user['PASSWORD_HASH'], password):
                flash('Invalid email or password.', 'danger')
            else:
                session.clear()
                session['user_id'] = user['ID']
                return redirect(url_for('dashboard'))

        return render_template('login.html')
    except Exception as e:
        print("DEBUG LOGIN ERROR:")
        traceback.print_exc()
        return f"Internal Server Error: {e}", 500

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user=g.user)

@app.route('/api/profile/upload', methods=['POST'])
@login_required
def upload_profile_image():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(f"profile_{g.user['ID']}_{datetime.now().timestamp()}_{file.filename}")
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(save_path)
        
        db_path = f'/uploads/{filename}'
        conn = get_db()
        conn.execute("UPDATE USERS SET PROFILE_IMAGE = ? WHERE ID = ?", (db_path, g.user['ID']))
        conn.commit()
        return jsonify({"message": "Profile picture updated!", "path": db_path})
    return jsonify({"error": "File type not allowed"}), 400

@app.route('/api/profile/update', methods=['POST'])
@login_required
def update_profile():
    data = request.get_json()
    full_name = data.get('full_name')
    email = data.get('email')
    phone = data.get('phone')

    if not full_name or not email:
        return jsonify({"error": "Full Name and Email are required."}), 400

    conn = get_db()
    try:
        conn.execute(
            "UPDATE USERS SET FULL_NAME = ?, EMAIL = ?, PHONE = ? WHERE ID = ?",
            (full_name, email, phone, g.user['ID'])
        )
        conn.commit()
        return jsonify({"message": "Profile updated successfully!"})
    except sqlite3.IntegrityError:
        return jsonify({"error": "Email is already taken."}), 400

@app.route('/api/profile/password', methods=['POST'])
@login_required
def change_password():
    data = request.get_json()
    current_password = data.get('current_password')
    new_password = data.get('new_password')

    if not check_password_hash(g.user['PASSWORD_HASH'], current_password):
        return jsonify({"error": "Incorrect current password."}), 400

    conn = get_db()
    conn.execute(
        "UPDATE USERS SET PASSWORD_HASH = ? WHERE ID = ?",
        (generate_password_hash(new_password, method='pbkdf2:sha256'), g.user['ID'])
    )
    conn.commit()
    return jsonify({"message": "Password changed successfully!"})

# --- Navigational Routes ---
@app.route('/')
def index():
    """Default route redirects to dashboard if logged in, else login."""
    if g.user:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()
    if conn is None:
        abort(500)
    cursor = conn.cursor()

    # --- Top Cards Data ---
    customer_count = cursor.execute("SELECT COUNT(*) FROM CUSTOMER").fetchone()[0] or 0
    inventory_items = cursor.execute("SELECT COUNT(*) FROM INVENTORY").fetchone()[0] or 0
    low_stock = cursor.execute(f"SELECT COUNT(*) FROM INVENTORY WHERE STOCK < {LOW_STOCK_THRESHOLD}").fetchone()[0] or 0

    # --- Chart Data ---
    # 1. Sales Reports Data (last 7 months)
    today = date.today()
    sales_by_month = OrderedDict()
    for i in range(6, -1, -1):
        year = today.year + (today.month - i - 1) // 12
        month = (today.month - i - 1) % 12 + 1
        month_key = f"{year}-{month:02d}"
        sales_by_month[month_key] = {'sales': 0, 'orders': 0}

    seven_months_ago_str = list(sales_by_month.keys())[0] + "-01"
    sales_query = "SELECT strftime('%Y-%m', PAYMENT_DATE) as month, SUM(TOTAL_AMOUNT) as total_sales, COUNT(BILL_ID) as order_count FROM BILLS WHERE PAYMENT_DATE >= ? GROUP BY month;"
    sales_results = cursor.execute(sales_query, (seven_months_ago_str,)).fetchall()
    for row in sales_results:
        if row['month'] in sales_by_month:
            sales_by_month[row['month']]['sales'] = row['total_sales'] or 0
            sales_by_month[row['month']]['orders'] = row['order_count'] or 0

    sales_labels = [datetime.strptime(m, '%Y-%m').strftime('%b') for m in sales_by_month.keys()]
    sales_flow_data = [d['sales'] for d in sales_by_month.values()]
    sales_order_count_data = [d['orders'] for d in sales_by_month.values()]

    # 2. Category Distribution (by Customer Type)
    category_query = "SELECT CUSTOMER_TYPE, COUNT(CUSTOMER_ID) as count FROM CUSTOMER GROUP BY CUSTOMER_TYPE;"
    category_results = cursor.execute(category_query).fetchall()
    category_map = {'WHOLESALE': 'Wholesaler', 'RETAIL': 'Retailer', 'HOTEL-LINE': 'General'}
    category_data_dict = {'Wholesaler': 0, 'Retailer': 0, 'General': 0}
    if category_results:
        for row in category_results:
            cat_name = category_map.get(row['CUSTOMER_TYPE'])
            if cat_name in category_data_dict:
                category_data_dict[cat_name] = row['count']
    category_labels = list(category_data_dict.keys())
    category_data = list(category_data_dict.values())

    # 3. Order Status
    status_query = "SELECT STATUS, COUNT(BILL_ID) as count FROM BILLS GROUP BY STATUS;"
    status_results = cursor.execute(status_query).fetchall()
    status_map = {'SUCCESSFUL': 'Completed', 'PENDING': 'Pending'}
    status_data_dict = {'Completed': 0, 'Pending': 0}
    if status_results:
        for row in status_results:
            status_name = status_map.get(row['STATUS'])
            if status_name in status_data_dict:
                status_data_dict[status_name] = row['count']
    status_labels = list(status_data_dict.keys())
    status_data = list(status_data_dict.values())
    
    # 4. Balance Card Data
    today_str = date.today().isoformat()
    yesterday_str = (date.today() - timedelta(days=1)).isoformat()
    total_profit_result = cursor.execute("SELECT SUM(PROFIT_EARNED) FROM BILLS").fetchone()
    total_profit = total_profit_result[0] or 0.0
    today_sales_profit = cursor.execute("SELECT SUM(TOTAL_AMOUNT), SUM(PROFIT_EARNED) FROM BILLS WHERE PAYMENT_DATE = ?", (today_str,)).fetchone()
    today_income = today_sales_profit[0] or 0.0
    today_profit = today_sales_profit[1] or 0.0
    today_expense = today_income - today_profit
    yesterday_profit_result = cursor.execute("SELECT SUM(PROFIT_EARNED) FROM BILLS WHERE PAYMENT_DATE = ?", (yesterday_str,)).fetchone()
    yesterday_profit = yesterday_profit_result[0] or 0.0
    profit_change_percentage = 0
    if yesterday_profit > 0:
        profit_change_percentage = ((today_profit - yesterday_profit) / yesterday_profit) * 100
    elif today_profit > 0:
        profit_change_percentage = 100

    # 5. Recent Orders
    recent_orders_query = "SELECT b.BILL_ID, c.CUSTOMER_NAME, b.TOTAL_AMOUNT, b.PAYMENT_DATE, b.PAYMENT_METHOD, b.STATUS FROM BILLS b JOIN CUSTOMER c ON b.CUSTOMER_ID = c.CUSTOMER_ID ORDER BY b.BILL_ID DESC LIMIT 2;"
    recent_orders = cursor.execute(recent_orders_query).fetchall()

    # 6. Recent Dues
    recent_dues_query = "SELECT CUSTOMER_NAME, unpaid_amount, strftime('%d-%b', 'now') as due_date FROM CUSTOMER WHERE unpaid_amount > 0 ORDER BY unpaid_amount DESC LIMIT 3;"
    recent_dues = cursor.execute(recent_dues_query).fetchall()

    data = {
        'customer_count': customer_count, 'inventory_items': inventory_items, 'low_stock': low_stock,
        'sales_report': {'labels': sales_labels, 'flow_data': sales_flow_data, 'order_count_data': sales_order_count_data},
        'category_chart': {'labels': category_labels, 'data': category_data},
        'status_chart': {'labels': status_labels, 'data': status_data, 'completed_count': status_data_dict.get('Completed', 0), 'pending_count': status_data_dict.get('Pending', 0)},
        'balance_data': {'total_profit': total_profit, 'profit_change': profit_change_percentage, 'today_income': today_income, 'today_expense': today_expense},
        'recent_orders': recent_orders, 'recent_dues': recent_dues
    }
    return render_template('dashboard.html', **data)

@app.route("/about")
@login_required
def about():
    return render_template('about.html')

# --- NEW API Routes for "See All" ---

@app.route('/api/all_orders')
@login_required
def get_all_orders():
    conn = get_db()
    if conn is None: return jsonify([]), 500
    try:
        query = "SELECT b.BILL_ID, c.CUSTOMER_NAME, b.TOTAL_AMOUNT, b.PAYMENT_DATE, b.PAYMENT_METHOD, b.STATUS FROM BILLS b JOIN CUSTOMER c ON b.CUSTOMER_ID = c.CUSTOMER_ID ORDER BY b.BILL_ID DESC LIMIT 20;"
        orders = conn.execute(query).fetchall()
        return jsonify([dict(row) for row in orders])
    except sqlite3.Error as e:
        print(f"Database error in /api/all_orders: {e}")
        return jsonify({"error": "Failed to fetch orders."}), 500

@app.route('/api/all_dues')
@login_required
def get_all_dues():
    conn = get_db()
    if conn is None: return jsonify([]), 500
    try:
        query = "SELECT CUSTOMER_NAME, unpaid_amount, strftime('%d-%b', 'now') as due_date FROM CUSTOMER WHERE unpaid_amount > 0 ORDER BY unpaid_amount DESC;"
        dues = conn.execute(query).fetchall()
        return jsonify([dict(row) for row in dues])
    except sqlite3.Error as e:
        print(f"Database error in /api/all_dues: {e}")
        return jsonify({"error": "Failed to fetch dues."}), 500

@app.route('/api/all_statuses')
@login_required
def get_all_statuses():
    conn = get_db()
    if conn is None: return jsonify([]), 500
    try:
        query = "SELECT STATUS, COUNT(BILL_ID) as count FROM BILLS GROUP BY STATUS;"
        statuses = conn.execute(query).fetchall()
        status_map = {'SUCCESSFUL': 'Completed', 'PENDING': 'Pending', 'CANCELLED': 'Cancelled', 'ON-TRANSIT': 'On-transit'}
        results = {s: 0 for s in status_map.values()}
        for row in statuses:
            if row['STATUS'] in status_map:
                results[status_map[row['STATUS']]] = row['count']
        return jsonify([{'status': k, 'count': v} for k, v in results.items()])
    except sqlite3.Error as e:
        print(f"Database error in /api/all_statuses: {e}")
        return jsonify({"error": "Failed to fetch statuses."}), 500


# ====================================================================
# === BILLING MODULE ===
# ====================================================================

@app.route('/billing')
@login_required
def billing_page():
    return render_template('billing.html')


@app.route('/api/customers', methods=['GET'])
@login_required
def get_customer_suggestions():
    search_term = request.args.get('term', '').strip()
    if not search_term: return jsonify([])

    conn = get_db()
    if conn is None: return jsonify({"error": "Database connection failed."}), 500

    try:
        cursor = conn.cursor()
        query = "SELECT CUSTOMER_NAME, MOBILE_NO, CUSTOMER_TYPE FROM CUSTOMER WHERE CUSTOMER_NAME LIKE ?"
        cursor.execute(query, (f'{search_term}%',))
        rows = cursor.fetchall()
        customers = [{"name": row['CUSTOMER_NAME'].strip(), "mobile": row['MOBILE_NO'], "type": row['CUSTOMER_TYPE'].title().replace('-Line', '-Line')} for row in rows]
        return jsonify(customers)
    except sqlite3.Error as e:
        print(f"Database query error: {e}")
        return jsonify({"error": "Failed to query database."}), 500


@app.route('/api/products', methods=['GET'])
@login_required
def get_product_suggestions():
    search_term = request.args.get('term', '').strip()
    customer_type = request.args.get('customer_type', '').upper().replace('-', '')
    if not search_term or not customer_type: return jsonify([])

    price_column_map = {'WHOLESALE': 'WHOLESALE_RATE', 'RETAIL': 'RETAIL_RATE', 'HOTEL': 'HOTEL_RATE', 'WHOLESALER': 'WHOLESALE_RATE', 'RETAILER': 'RETAIL_RATE', 'HOTEL-LINE': 'HOTEL_RATE'}
    price_column = price_column_map.get(customer_type, 'RETAIL_RATE')

    conn = get_db()
    if conn is None: return jsonify({"error": "Database connection failed."}), 500

    try:
        cursor = conn.cursor()
        query = f"SELECT BRAND, PRODUCT, MRP, {price_column} as PRICE FROM INVENTORY WHERE UPPER(BRAND) LIKE ? OR UPPER(PRODUCT) LIKE ?"
        like_term = f'%{search_term.upper()}%'
        cursor.execute(query, (like_term, like_term))
        products = [{"name": f"{row['BRAND']} {row['PRODUCT']}".strip(), "price": row['PRICE'], "mrp": row['MRP']} for row in cursor.fetchall()]
        return jsonify(products)
    except sqlite3.Error as e:
        print(f"Database query error: {e}"); traceback.print_exc()
        return jsonify({"error": "Failed to query database."}), 500


@app.route('/api/bill/save', methods=['POST'])
@login_required
def process_bill_and_save():
    data = request.get_json()
    if not data: return jsonify({"error": "Invalid JSON data provided."}), 400

    customer_name = data.get('customer_name')
    customer_phone = data.get('phone')
    customer_type_input = data.get('customer_type', 'RETAIL').upper().replace('-', '')
    payment_method = data.get('payment_method')
    products_to_bill = data.get('products', [])

    if 'HOTEL' in customer_type_input: customer_type_db = 'HOTEL-LINE'
    elif 'WHOLESALE' in customer_type_input: customer_type_db = 'WHOLESALE'
    else: customer_type_db = 'RETAIL'
        
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
            cursor.execute("INSERT INTO CUSTOMER (CUSTOMER_NAME, MOBILE_NO, CUSTOMER_TYPE) VALUES (?, ?, ?)", (customer_name, customer_phone, customer_type_db))
            customer_id = cursor.lastrowid

        # 2. Per-Item Profit Calculation and Inventory Update
        total_items = 0
        profit_earned = 0.0
        bill_items_data = []
        for item in products_to_bill:
            prod_name, qty, sell_price = item['name'], item['quantity'], item['price']
            cursor.execute("SELECT ID, PURCHASE_RATE, STOCK FROM INVENTORY WHERE (BRAND || ' ' || PRODUCT) = ?", (prod_name,))
            inventory_row = cursor.fetchone()


            if not inventory_row: raise Exception(f"Product not found in inventory: {prod_name}")
            if inventory_row['STOCK'] < qty: raise Exception(f"Insufficient stock for {prod_name}. Available: {inventory_row['STOCK']}")

            purchase_rate = inventory_row['PURCHASE_RATE'] or 0.0
            unit_profit = sell_price - purchase_rate
            profit_earned += unit_profit * qty
            total_items += qty
            bill_items_data.append((prod_name, qty, sell_price, unit_profit))
            cursor.execute("UPDATE INVENTORY SET STOCK = STOCK - ? WHERE ID=?", (qty, inventory_row['ID']))

        # 3. Insert main BILLS record
        payment_date = date.today().isoformat()
        status = "PENDING" if payment_method.upper() == 'CREDIT' else "SUCCESSFUL"
        cursor.execute("INSERT INTO BILLS (CUSTOMER_ID, TOTAL_ITEMS, BILL_AMOUNT, TAX_AMOUNT, DISCOUNT_AMOUNT, TOTAL_AMOUNT, PROFIT_EARNED, PAYMENT_METHOD, PAYMENT_DATE, STATUS) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (customer_id, total_items, bill_amount, tax_amount, discount_amount, total_amount, profit_earned, payment_method.upper(), payment_date, status))
        bill_id = cursor.lastrowid

        # 4. Update Customer Dues if Credit
        if payment_method.upper() == 'CREDIT':
            cursor.execute("UPDATE CUSTOMER SET unpaid_amount = unpaid_amount + ?, bill_amount = bill_amount + ? WHERE CUSTOMER_ID = ?", (total_amount, total_amount, customer_id))

        # 5. Insert BILL_ITEMS records
        bill_items_insert_data = [(bill_id, prod, qty, price, u_profit) for prod, qty, price, u_profit in bill_items_data]
        cursor.executemany("INSERT INTO BILL_ITEMS (BILL_ID, PRODUCT_NAME, QUANTITY, PRICE, UNIT_PROFIT) VALUES (?, ?, ?, ?, ?)", bill_items_insert_data)

        conn.commit()
        return jsonify({"message": f"Bill #{bill_id} saved successfully.", "bill_id": bill_id, "total_amount": round(total_amount, 2), "profit_earned": round(profit_earned, 2)})

    except sqlite3.Error as e:
        conn.rollback(); print(f"SQLite Transaction Error: {e}"); traceback.print_exc()
        return jsonify({"error": f"Database Transaction Failed: {e}"}), 500
    except Exception as e:
        conn.rollback(); print(f"General Error: {e}"); traceback.print_exc()
        return jsonify({"error": f"General Server Error: {e}"}), 500


# ====================================================================
# === INVENTORY MODULE ===
# ====================================================================

@app.route('/inventory')
@login_required
def inventory_page():
    conn = get_db()
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

        total_products = cursor.execute(f"SELECT COUNT(*) {base_query}", params).fetchone()[0] or 0
        total_pages = (total_products + PER_PAGE_INVENTORY - 1) // PER_PAGE_INVENTORY if total_products > 0 else 1
        offset = (page - 1) * PER_PAGE_INVENTORY

        sql = f"SELECT ID, BRAND, PRODUCT, STOCK, MRP, PURCHASE_RATE, WHOLESALE_RATE, RETAIL_RATE, HOTEL_RATE, CATEGORY {base_query} ORDER BY {sort_by} {sort_order} LIMIT ? OFFSET ?"
        products = cursor.execute(sql, params + [PER_PAGE_INVENTORY, offset]).fetchall()
        low_stock_products = cursor.execute(f"SELECT PRODUCT, STOCK FROM INVENTORY WHERE STOCK < {LOW_STOCK_THRESHOLD} ORDER BY STOCK ASC LIMIT 10").fetchall()
        categories = [row['CATEGORY'] for row in cursor.execute("SELECT DISTINCT CATEGORY FROM INVENTORY WHERE CATEGORY IS NOT NULL AND CATEGORY != '' ORDER BY CATEGORY ASC").fetchall()]
        total_inventory_value = cursor.execute("SELECT SUM(STOCK * PURCHASE_RATE) FROM INVENTORY").fetchone()[0] or 0

        category_chart_sql = "SELECT CASE WHEN CATEGORY IS NULL OR CATEGORY = '' THEN 'Unknown' ELSE CATEGORY END as CATEGORY, COUNT(ID) as count FROM INVENTORY GROUP BY CATEGORY ORDER BY count DESC"
        category_results = cursor.execute(category_chart_sql).fetchall()
        category_labels = [row['CATEGORY'] for row in category_results] if category_results else ['No Data']
        category_data = [row['count'] for row in category_results] if category_results else [1]

        return render_template('inventory.html', products=products, page=page, total_pages=total_pages, low_stock_products=low_stock_products, categories=categories, search_query=search_query, sort_by=sort_by, sort_order=sort_order, total_inventory_value=total_inventory_value, category_labels=category_labels, category_data=category_data)

    except Exception as e:
        traceback.print_exc()
        flash(f"Error loading inventory: {str(e)}. Please check terminal logs.", "danger")
        return redirect(url_for('dashboard'))

@app.route('/inventory/add', methods=['POST'])
@login_required
def inventory_add():
    conn = get_db()
    if conn is None: abort(500)
    try:
        category = request.form.get('category')
        new_category = request.form.get('new_category', '').strip()
        final_category = new_category if new_category else category

        if not final_category:
            flash("Category is required.", "danger")
            return redirect(url_for('inventory_page'))
        
        sql = "INSERT INTO INVENTORY (BRAND, PRODUCT, STOCK, MRP, PURCHASE_RATE, WHOLESALE_RATE, RETAIL_RATE, HOTEL_RATE, CATEGORY) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
        conn.cursor().execute(sql, (request.form.get('brand'), request.form.get('product'), request.form.get('stock'), request.form.get('mrp'), request.form.get('purchase_rate'), request.form.get('wholesale_rate'), request.form.get('retail_rate'), request.form.get('hotel_rate'), final_category))
        conn.commit()
        flash("Product added successfully!", "success")
    except sqlite3.IntegrityError:
        flash("Error: A product with similar BRAND and PRODUCT details might already exist.", "danger")
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")
    return redirect(url_for('inventory_page'))

@app.route('/inventory/edit/<int:product_id>', methods=['POST'])
@login_required
def inventory_edit(product_id):
    conn = get_db()
    if conn is None: abort(500)
    try:
        sql = "UPDATE INVENTORY SET BRAND = ?, PRODUCT = ?, STOCK = ?, MRP = ?, PURCHASE_RATE = ?, WHOLESALE_RATE = ?, RETAIL_RATE = ?, HOTEL_RATE = ?, CATEGORY = ? WHERE ID = ?"
        conn.cursor().execute(sql, (request.form.get('brand'), request.form.get('product'), request.form.get('stock'), request.form.get('mrp'), request.form.get('purchase_rate'), request.form.get('wholesale_rate'), request.form.get('retail_rate'), request.form.get('hotel_rate'), request.form.get('category'), product_id))
        conn.commit()
        flash(f"Product ID {product_id} updated successfully!", "success")
    except Exception as e:
        flash(f"Error updating product: {e}", "danger")
    return redirect(url_for('inventory_page'))

@app.route('/api/inventory/delete', methods=['POST'])
@login_required
def inventory_delete():
    conn = get_db()
    if conn is None: return jsonify({"status": "error", "message": "Database error"}), 500
    try:
        cursor = conn.cursor()
        data = request.get_json()
        product_ids, current_page = data.get('ids'), data.get('current_page', 1)

        if not product_ids: return jsonify({"status": "error", "message": "No IDs provided"}), 400

        placeholders = ', '.join('?' for _ in product_ids)
        cursor.execute(f"DELETE FROM INVENTORY WHERE ID IN ({placeholders})", product_ids)
        conn.commit()
        flash(f"Successfully deleted {len(product_ids)} product(s).", "success")

        remaining_products = cursor.execute("SELECT COUNT(*) FROM INVENTORY").fetchone()[0] or 0
        new_total_pages = (remaining_products + PER_PAGE_INVENTORY - 1) // PER_PAGE_INVENTORY if remaining_products > 0 else 1
        redirect_page = min(current_page, new_total_pages)
        return jsonify({"status": "success", "redirect_page": redirect_page})
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/inventory/low_stock_all')
@login_required
def get_all_low_stock():
    conn = get_db()
    if conn is None: return jsonify([]), 500
    sql = f"SELECT PRODUCT, STOCK FROM INVENTORY WHERE STOCK < {LOW_STOCK_THRESHOLD} ORDER BY STOCK ASC"
    results = conn.execute(sql).fetchall()
    return jsonify([dict(row) for row in results])

@app.route('/api/inventory/<int:product_id>')
@login_required
def get_product_data(product_id):
    conn = get_db()
    if conn is None: return jsonify({"status": "error", "message": "Database error"}), 500
    result = conn.execute("SELECT * FROM INVENTORY WHERE ID = ?", (product_id,)).fetchone()
    if result:
        return jsonify({k: str(v) for k, v in dict(result).items()})
    return jsonify({"status": "error", "message": "Product not found"}), 404

@app.route('/api/categories', methods=['GET'])
@login_required
def get_categories():
    conn = get_db()
    if conn is None: return jsonify([]), 500
    categories = [row['CATEGORY'] for row in conn.execute("SELECT DISTINCT CATEGORY FROM INVENTORY WHERE CATEGORY IS NOT NULL AND CATEGORY != '' ORDER BY CATEGORY ASC").fetchall()]
    return jsonify(categories)


# --- Reports Routes ---
@app.route('/customer_report')
@login_required
def customer_report():
    conn = get_db()
    if conn is None: abort(500)
    try:
        cursor = conn.cursor()
        page = request.args.get('page', 1, type=int)
        search_query = request.args.get('search', '').strip()

        base_query, params = "FROM CUSTOMER WHERE 1=1", []
        if search_query:
            base_query += " AND (CUSTOMER_NAME LIKE ? OR CUSTOMER_ID LIKE ? OR MOBILE_NO LIKE ?)"
            params.extend([f"%{search_query}%"] * 3)

        total_customers = cursor.execute(f"SELECT COUNT(*) {base_query}", params).fetchone()[0] or 0
        total_pages = (total_customers + PER_PAGE_CUSTOMER - 1) // PER_PAGE_CUSTOMER if total_customers > 0 else 1
        offset = (page - 1) * PER_PAGE_CUSTOMER

        customers_sql = f"SELECT CUSTOMER_ID, CUSTOMER_NAME, MOBILE_NO, CUSTOMER_TYPE, unpaid_amount {base_query} ORDER BY CUSTOMER_ID ASC LIMIT ? OFFSET ?"
        customers = cursor.execute(customers_sql, params + [PER_PAGE_CUSTOMER, offset]).fetchall()

        return render_template('customer_report.html', customers=customers, page=page, total_pages=total_pages, search_query=search_query)
    except Exception as e:
        flash(f"Error loading customer report: {e}", "danger")
        return redirect(url_for('index'))

@app.route('/api/customer/<int:customer_id>', methods=['GET'])
@login_required
def get_customer_details(customer_id):
    """Fetches detailed information for a specific customer."""
    conn = get_db()
    if not conn: return jsonify({"error": "Database connection failed"}), 500
    try:
        query = "SELECT CUSTOMER_ID, CUSTOMER_NAME, MOBILE_NO, CUSTOMER_TYPE, bill_amount, paid_amount, unpaid_amount FROM CUSTOMER WHERE CUSTOMER_ID = ?"
        customer = conn.execute(query, (customer_id,)).fetchone()
        if customer:
            return jsonify(dict(customer))
        return jsonify({"error": "Customer not found"}), 404
    except sqlite3.Error as e:
        print(f"Database error in get_customer_details: {e}")
        return jsonify({"error": "Failed to fetch customer data"}), 500


@app.route('/order_history')
@login_required
def order_history():
    conn = get_db()
    if conn is None: abort(500)
    try:
        cursor = conn.cursor()
        page = request.args.get('page', 1, type=int)
        search_query = request.args.get('search', '').strip()

        base_query, params = "FROM BILLS b JOIN CUSTOMER c ON b.CUSTOMER_ID = c.CUSTOMER_ID WHERE 1=1", []
        if search_query:
            base_query += " AND (c.CUSTOMER_NAME LIKE ? OR b.BILL_ID LIKE ?)"
            params.extend([f"%{search_query}%"] * 2)

        total_orders = cursor.execute(f"SELECT COUNT(*) {base_query}", params).fetchone()[0] or 0
        total_pages = (total_orders + PER_PAGE_ORDERS - 1) // PER_PAGE_ORDERS if total_orders > 0 else 1
        offset = (page - 1) * PER_PAGE_ORDERS

        orders_sql = f"SELECT b.BILL_ID, b.PAYMENT_DATE, b.STATUS, b.TOTAL_AMOUNT, c.CUSTOMER_NAME, c.MOBILE_NO {base_query} ORDER BY b.PAYMENT_DATE DESC, b.BILL_ID DESC LIMIT ? OFFSET ?"
        orders = cursor.execute(orders_sql, params + [PER_PAGE_ORDERS, offset]).fetchall()

        return render_template('order_history.html', orders=orders, page=page, total_pages=total_pages, total_orders=total_orders, search_query=search_query)
    except Exception as e:
        flash(f"Error loading order history: {e}", "danger")
        return redirect(url_for('index'))

@app.route('/reports')
@login_required
def reports_hub():
    return render_template('reports.html')

@app.route('/stock_report')
@login_required
def stock_report():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT ID, BRAND, PRODUCT, STOCK as QUANTITY, PURCHASE_RATE, (STOCK * PURCHASE_RATE) as TOTAL_AMOUNT FROM INVENTORY")
    stock_data = cursor.fetchall()
    return render_template('stock_report.html', stock_data=stock_data)

@app.route('/credit_report')
@login_required
def credit_report():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT CUSTOMER_ID as id, CUSTOMER_NAME as customer_name, bill_amount, paid_amount, unpaid_amount FROM CUSTOMER WHERE unpaid_amount > 0")
    customers = cursor.fetchall()
    return render_template('credit_report.html', customers=customers, page=1, total_pages=1, search_query='', sort_by='id', sort_order='asc')


# --- Main Execution (Local only) ---
if __name__ == '__main__':
    print(f"Starting local server...")
    print("Access Login at http://127.0.0.1:5000/login")
    print("Access Dashboard at http://127.0.0.1:5000/dashboard")
    print("Access User Profile at http://127.0.0.1:5000/profile")
    print("Access Store Settings at http://127.0.0.1:5000/store_settings")
    
    port = int(os.environ.get('PORT', 5000))
    try:
        app.run(debug=False, host='0.0.0.0', port=port)
    except OSError as e:
        if port == 5000:
            print(f"\nERROR: Port 5000 is in use. Try running on port 5001:\n   PORT=5001 python app.py")
        else:
            print(f"ERROR: {e}")