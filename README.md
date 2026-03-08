# Inventory Management System

A comprehensive web-based inventory management system built with Flask that helps businesses manage their inventory, customers, billing, and generate insightful reports.

## Features

### 📦 Inventory Management
- Add, edit, and delete products with multiple pricing tiers
- Track stock levels with low-stock alerts (threshold: 50 units)
- Categorize products by brand, category, and type
- Support for multiple rate types: MRP, Purchase, Wholesale, Retail, and Hotel rates
- Pagination support for large inventories

### 👥 Customer Management
- Manage customer database with contact information
- Customer type classification (Wholesale, Retail, Hotel-line)
- Track customer credit and payment history
- Monitor unpaid amounts and payment status

### 💰 Billing System
- Generate bills with automatic tax calculation (5% tax rate)
- Apply discounts to bills
- Multiple payment methods: UPI, Cash, Credit, and Card
- Automatic profit calculation
- Payment status tracking (Successful/Pending)
- Bill history and order tracking

### 📊 Reports & Analytics
- **Dashboard**: Real-time overview of business metrics
  - Total sales and profit analysis
  - Low stock alerts
  - Recent orders and pending payments
  - Revenue trends
- **Stock Reports**: Inventory status and availability
- **Customer Reports**: Customer purchase history and credit status
- **Credit Reports**: Outstanding payments and dues tracking
- **Order History**: Complete transaction history

### 👤 User Profile Management
- Store owner profile management
- Store information and settings
- GST number and license management
- Logo and avatar upload
- Contact and social media information

## Technology Stack

- **Backend**: Flask 3.1.2 (Python)
- **Database**: SQLite3
- **Frontend**: HTML, CSS, JavaScript
- **Image Processing**: Pillow 12.0.0
- **CORS Support**: Flask-CORS 6.0.2
- **Additional Libraries**: 
  - Werkzeug for utilities
  - Jinja2 for templating
  - Requests for HTTP operations

## Installation

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Setup Instructions

1. **Clone the repository**
   ```bash
   git clone https://github.com/prajwaldhage/Inventory-Project.git
   cd Inventory-Project
   ```

2. **Create a virtual environment**
   ```bash
   python3 -m venv env
   ```

3. **Activate the virtual environment**
   - On Linux/Mac:
     ```bash
     source env/bin/activate
     ```
   - On Windows:
     ```bash
     env\Scripts\activate
     ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

5. **Initialize the database**
   ```bash
   python init_db.py
   ```
   Or simply run the main application (it will auto-initialize):
   ```bash
   python app.py
   ```

6. **Access the application**
   Open your web browser and navigate to:
   ```
   http://localhost:5000
   ```

## Project Structure

```
Inventory-Final-master/
├── app.py                  # Main application file
├── inv.py                  # Alternative entry point
├── init_db.py              # Database initialization script
├── requirements.txt        # Python dependencies
├── inventory.db            # SQLite database (auto-generated)
├── logic/                  # Business logic modules
│   ├── __init__.py
│   ├── dashboardlogic.py   # Dashboard calculations
│   └── inventorylogic.py   # Inventory operations
├── templates/              # HTML templates
│   ├── index.html          # Home page
│   ├── dashboard.html      # Dashboard view
│   ├── inventory.html      # Inventory management
│   ├── billing.html        # Billing interface
│   ├── reports.html        # Reports page
│   ├── customer_report.html
│   ├── credit_report.html
│   ├── stock_report.html
│   ├── order_history.html
│   ├── user_profile.html
│   └── about.html
├── static/                 # Static assets
│   ├── dashboard.css
│   └── dashboard.js
└── uploads/                # User uploaded files
    ├── default-avatar.png
    └── default-logo.png
```

## Database Schema

### INVENTORY Table
- Stores product information with multiple pricing tiers
- Fields: ID, BRAND, PRODUCT, CATEGORY, STOCK, MRP, PURCHASE_RATE, WHOLESALE_RATE, RETAIL_RATE, HOTEL_RATE

### CUSTOMER Table
- Manages customer information and credit tracking
- Fields: CUSTOMER_ID, CUSTOMER_NAME, MOBILE_NO, CUSTOMER_TYPE, bill_amount, paid_amount, unpaid_amount

### BILLS Table
- Records all billing transactions
- Fields: BILL_ID, CUSTOMER_ID, TOTAL_ITEMS, BILL_AMOUNT, TAX_AMOUNT, DISCOUNT_AMOUNT, TOTAL_AMOUNT, PROFIT_EARNED, PAYMENT_METHOD, PAYMENT_DATE, STATUS

### BILL_ITEMS Table
- Stores individual items in each bill
- Fields: ITEM_ID, BILL_ID, PRODUCT_NAME, QUANTITY, PRICE, UNIT_PROFIT

### SETTINGS Table
- User and store configuration
- Fields: USER_ID, FULL_NAME, EMAIL, PHONE_NUMBER, SOCIAL_MEDIA, PHOTO_URL, STORE_ID, STORE_NAME, STORE_NO, ADDRESS, GST_NUMBER, LICENSE_URL, LOGO_URL

## API Endpoints

### Dashboard
- `GET /` - Home page
- `GET /dashboard` - Dashboard view
- `GET /api/all_orders` - Fetch all orders
- `GET /api/all_dues` - Get all pending dues
- `GET /api/all_statuses` - Get payment statuses

### Billing
- `GET /billing` - Billing interface
- `GET /api/customers` - List all customers
- `GET /api/products` - List all products
- `POST /api/bill/save` - Save a new bill

### Inventory
- `GET /inventory` - Inventory management page
- `POST /inventory/add` - Add new product
- `POST /inventory/edit/<id>` - Edit existing product
- `POST /api/inventory/delete` - Delete product
- `GET /api/inventory/low_stock_all` - Get low stock items
- `GET /api/inventory/<id>` - Get product details
- `GET /api/categories` - List all categories

### User Profile
- `GET /user_profile` - User profile page
- `GET /api/settings` - Get settings
- `POST /api/settings` - Update settings
- `POST /api/upload-file` - Upload files (avatar/logo)

## Configuration

Key configurations in `app.py`:

```python
LOW_STOCK_THRESHOLD = 50        # Alert threshold for low stock
PER_PAGE_INVENTORY = 10         # Items per page in inventory
PER_PAGE_CUSTOMER = 15          # Customers per page
PER_PAGE_ORDERS = 10            # Orders per page
TAX_RATE = 0.05                 # 5% tax rate
```

## Usage

### Adding Products
1. Navigate to the Inventory page
2. Click "Add Product"
3. Fill in product details (brand, name, category, stock, pricing)
4. Submit to add to inventory

### Creating Bills
1. Go to the Billing page
2. Select customer or add new customer
3. Add products to the cart
4. Apply discounts if needed
5. Choose payment method
6. Generate and save bill

### Viewing Reports
1. Access the Reports section from navigation
2. Choose report type:
   - Stock Report: Current inventory status
   - Customer Report: Customer purchase history
   - Credit Report: Outstanding payments
   - Order History: All transactions

## Security Notes

⚠️ **Important**: This application uses a hardcoded secret key. For production use:
- Change the secret key in `app.py` to a strong, random value
- Use environment variables for sensitive configuration
- Implement proper authentication and authorization
- Enable HTTPS
- Add input validation and sanitization

## Troubleshooting

### Database Connection Issues
If you encounter database errors:
```bash
rm inventory.db
python init_db.py
```

### Port Already in Use
If port 5000 is occupied, modify the port in `app.py`:
```python
if __name__ == '__main__':
    app.run(debug=True, port=5001)  # Change port number
```

### Missing Uploads Directory
The application will auto-create the uploads directory, but if needed:
```bash
mkdir uploads
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is available for educational and commercial use.

## Support

For issues, questions, or contributions, please open an issue in the repository.

---

**Note**: This system includes sample data for testing purposes. Initialize the database to populate with dummy inventory, customers, and transactions.
