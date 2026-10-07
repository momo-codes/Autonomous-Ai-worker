from flask import Flask, request, redirect

app = Flask(__name__)

bills = [
    {
        "id": "BILL-0001",
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
        "vendor": "Northwind Traders Pvt Ltd",
        "invoice_number": "INV-2044",
        "invoice_date": "2026-08-14",
        "due_date": "2026-09-13",
        "amount": "3450.75",
        "currency": "INR",
        "status": "Entered"
    }
]


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
@app.get('/')
def home():
    body = "<p>Welcone to Acme ERP</p><p><a href='/payables'>Go to Accounts Payable</a></p>"
    return make_page("Home", body)


## route 2-- listing all bills 

@app.get('/payables')
def payables():
    rows = ""
    for b in bills:
        rows+= f"""
        <tr>
            <td><a href="/payables/{b['id']}">{b['id']}</a></td>
            <td>{b['vendor']}</td>
            <td>{b['invoice_number']}</td>
            <td>{b['amount']} {b['currency']}</td>
            <td>{b['due_date']}</td>
            <td>{b['status']}</td>
        </tr>    
        """
    body=f"""
    <table>
            <tr>
                <th>Bill ID</th>
                <th>Vendor</th>
                <th>Invoice #</th>
                <th>Amount</th>
                <th>Due Date</th>
                <th>Status</th>
            </tr>
            {rows}
        </table>
        <br>
        <a href="/payables/new">Create New Bill</a>
        """
    return make_page("Accounts Payable", body)

if __name__ == '__main__':
    app.run(port=5055, debug=True)
