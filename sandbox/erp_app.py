from flask import Flask, request, redirect
import secrets
import re

from home import home_bp
from bill_list import bills_bp
from new_bill import new_bill_bp
from post_bill import post_bill_bp
from bill_details import bill_details_bp

app = Flask(__name__)


CSRF_TOKEN = secrets.token_hex(8)

VENDORS = {
    "V-100": "Northwind Traders Pvt Ltd",
    "V-200": "Globex Logistics Ltd",
    "V-300": "Initech Services",
}

CURRENCIES = ["USD", "EUR", "INR"]

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

bills = [
    {
        "id": "BILL-0001",
        "vendor_id": "V-100",
        "vendor": "Northwind Traders Pvt Ltd",
        "invoice_number": "INV-2031",
        "invoice_date": "2026-07-02",
        "due_date": "2026-08-01",
        "amount": "1200.00",
        "currency": "INR",
        "status": "Paid"
    },
    {
        "id": "BILL-0002",
        "vendor_id": "V-100",
        "vendor": "Northwind Traders Pvt Ltd",
        "invoice_number": "INV-2044",
        "invoice_date": "2026-08-14",
        "due_date": "2026-09-13",
        "amount": "3450.75",
        "currency": "INR",
        "status": "Entered"
    }
]


stats = {
    "post_attempts": 0
}


##Helper function 

def make_page(title,body,error=None,notice=None):
    error_html = f'<div class="err">{error}</div>' if error else ''
    notice_html = f'<div class="notice">{notice}</div>' if notice else ''
    return f"""
    <!doctype html>
    <html>
    <head>
        <title>{title} - Acme ERP</title>
        <style>
            body {{
                font-family: system-ui, sans-serif;
                max-width: 860px;
                margin: 30px auto;
                padding: 0 16px;
                color: #1b2430;
            }}
            nav a {{ margin-right: 14px; text-decoration: none; color: #0066cc; }}
            table {{ border-collapse: collapse; width: 100%; }}
            td, th {{ border: 1px solid #d5dbe3; padding: 8px 12px; text-align: left; }}
            th {{ background: #f4f6f8; }}
            .err {{
                background: #fde8e8;
                border: 1px solid #e49a9a;
                padding: 8px 12px;
                margin: 10px 0;
                border-radius: 4px;
            }}
            .ok {{
                background: #e6f6ea;
                border: 1px solid #8fcf9e;
                padding: 8px 12px;
                margin: 10px 0;
                border-radius: 4px;
            }}
            label {{ display: block; margin: 12px 0 4px; font-weight: 600; }}
            input, select {{ padding: 8px; width: 320px; border: 1px solid #ccc; border-radius: 4px; }}
            button {{
                margin-top: 16px;
                padding: 10px 20px;
                background: #0066cc;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
            }}
            a {{ color: #0066cc; }}
        </style>
    </head>
    <body>
        <nav>
            <a href = "/">Home</a>
            <a href = "/payables">Accounts Payble</a>
            <a href = "/payables/new">New Bill</a>
        </nav>
        <hr>
        <h1>{title}</h1>
        {error_html}
        {notice_html}
        {body}
    </body>
    </html>
    """


## route 1 -home page
app.register_blueprint(home_bp)


## route 2-- listing all bills 

app.register_blueprint(bills_bp)

## route 3-- creating new bill
app.register_blueprint(new_bill_bp)

## route 4-- posting new bill
app.register_blueprint(post_bill_bp)

## route 5-- bill details
app.register_blueprint(bill_details_bp)

if __name__ == '__main__':
    app.run(port=5055, debug=True)
