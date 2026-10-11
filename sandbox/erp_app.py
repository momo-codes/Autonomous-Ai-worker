from flask import Flask, request, redirect
import secrets
import re


# ── These stay outside create_app (they never change) ──

VENDORS = {
    "V-100": "Northwind Traders Pvt Ltd",
    "V-200": "Globex Logistics Ltd",
    "V-300": "Initech Services",
}

CURRENCIES = ["USD", "EUR", "INR"]
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def make_page(title, body, error=None, notice=None):
    error_html = f'<div class="err">{error}</div>' if error else ""
    notice_html = f'<div class="ok">{notice}</div>' if notice else ""
    return f"""<!doctype html>
<html>
<head>
    <title>{title} - Acme ERP</title>
    <style>
        body{{font-family:system-ui;max-width:900px;margin:30px auto;padding:0 20px;color:#1b2430}}
        nav{{background:#1b2430;padding:12px 20px;border-radius:6px;margin-bottom:24px}}
        nav a{{color:white;text-decoration:none;margin-right:20px;font-size:14px}}
        table{{border-collapse:collapse;width:100%}}
        td,th{{border:1px solid #d5dbe3;padding:10px 14px;text-align:left}}
        th{{background:#f4f6f8;font-weight:600}}
        tr:hover{{background:#f9fafb}}
        .err{{background:#fde8e8;border:1px solid #e49a9a;padding:12px 16px;margin:12px 0;border-radius:6px;color:#c0392b}}
        .ok{{background:#e6f6ea;border:1px solid #8fcf9e;padding:12px 16px;margin:12px 0;border-radius:6px;color:#1e7e34}}
        label{{display:block;margin:14px 0 4px;font-weight:600}}
        input,select{{padding:8px 12px;width:340px;border:1px solid #ccc;border-radius:4px;font-size:14px}}
        button{{margin-top:20px;padding:10px 24px;background:#0066cc;color:white;border:none;border-radius:4px;cursor:pointer;font-size:15px}}
        a{{color:#0066cc}}
    </style>
</head>
<body>
    <nav>
        <a href="/">Home</a>
        <a href="/payables">Accounts Payable</a>
        <a href="/payables/new">New Bill</a>
    </nav>
    <h1>{title}</h1>
    {error_html}
    {notice_html}
    {body}
</body>
</html>"""


def make_form(values, csrf_token):
    """Builds the new bill form HTML"""
    vendor_options = "<option value=''>-- select vendor --</option>"
    for vid, vname in VENDORS.items():
        selected = "selected" if values.get("vendor_id") == vid else ""
        vendor_options += (
            f"<option value='{vid}' {selected}>{vname}</option>"
        )

    currency_options = ""
    for c in CURRENCIES:
        selected = "selected" if values.get("currency", "INR") == c else ""
        currency_options += f"<option value='{c}' {selected}>{c}</option>"

    return f"""
    <form method="POST" action="/payables">
        <input type="hidden" name="csrf_token" value="{csrf_token}">

        <label>Vendor</label>
        <select name="vendor_id" required>
            {vendor_options}
        </select>

        <label>Invoice Number</label>
        <input type="text" name="invoice_number"
               value="{values.get('invoice_number', '')}"
               placeholder="e.g. INV-2057" required>

        <label>Invoice Date (YYYY-MM-DD)</label>
        <input type="text" name="invoice_date"
               value="{values.get('invoice_date', '')}"
               placeholder="e.g. 2026-09-21" required>

        <label>Due Date (YYYY-MM-DD)</label>
        <input type="text" name="due_date"
               value="{values.get('due_date', '')}"
               placeholder="e.g. 2026-10-21" required>

        <label>Total Amount (including tax)</label>
        <input type="text" name="amount"
               value="{values.get('amount', '')}"
               placeholder="e.g. 4820.50" required>

        <label>Currency</label>
        <select name="currency">
            {currency_options}
        </select>

        <br>
        <button type="submit">Create Bill</button>
    </form>"""


# ── create_app wraps everything ──

def create_app(flaky=True):
    """
    Creates and returns the Flask ERP app.

    flaky=True  → first POST attempt returns 503
                  tests if agent can recover from errors
    flaky=False → no injected failures
    """
    app = Flask(__name__)

    # Each app instance gets its own CSRF token
    csrf_token = secrets.token_hex(8)

    # State dict (mutable inside nested functions)
    state = {
        "post_attempts": 0,
        "bills": []
    }

    def seed():
        """Reset to initial state with 2 pre-existing bills"""
        state["bills"] = [
            {
                "id": "BILL-0001",
                "vendor_id": "V-100",
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
                "invoice_number": "INV-2044",
                "invoice_date": "2026-08-14",
                "due_date": "2026-09-13",
                "amount": "3450.75",
                "currency": "INR",
                "status": "Entered"
            }
        ]
        state["post_attempts"] = 0

    seed()

    # ── Routes ──

    @app.get("/")
    def home():
        body = """
        <p>Welcome to <strong>Acme Corp ERP</strong></p>
        <br>
        <a href="/payables" style="
            display:inline-block;padding:12px 24px;
            background:#0066cc;color:white;
            border-radius:6px;text-decoration:none">
            Go to Accounts Payable →
        </a>"""
        return make_page("Acme ERP", body)

    @app.get("/payables")
    def payables():
        rows = ""
        for b in state["bills"]:
            vendor_name = VENDORS.get(b["vendor_id"], "Unknown")
            rows += (
                f"<tr>"
                f"<td><a href='/payables/{b['id']}'>{b['id']}</a></td>"
                f"<td>{vendor_name}</td>"
                f"<td>{b['invoice_number']}</td>"
                f"<td>{b['amount']} {b['currency']}</td>"
                f"<td>{b['due_date']}</td>"
                f"<td>{b['status']}</td>"
                f"</tr>"
            )
        body = f"""
        <table>
            <tr>
                <th>Bill ID</th><th>Vendor</th><th>Invoice #</th>
                <th>Amount</th><th>Due Date</th><th>Status</th>
            </tr>
            {rows}
        </table>
        <br><a href="/payables/new">+ Create New Bill</a>"""
        return make_page("Accounts Payable", body)

    @app.get("/payables/new")
    def new_bill():
        return make_page(
            "New Bill",
            make_form({}, csrf_token)
        )

    @app.post("/payables")
    def create_bill():
        state["post_attempts"] += 1

        # Injected failure — tests agent recovery
        if flaky and state["post_attempts"] == 1:
            return make_page(
                "Service Unavailable",
                "<p>Ledger service busy. Please retry.</p>",
                error="503 Temporary error. Please retry."
            ), 503

        f = {k: v.strip() for k, v in request.form.items()}

        # Validation 1 — CSRF token
        if f.get("csrf_token") != csrf_token:
            return make_page(
                "Forbidden", "",
                error="Invalid CSRF token."
            ), 403

        # Validation 2 — Vendor
        if f.get("vendor_id") not in VENDORS:
            return make_page(
                "New Bill",
                make_form(f, csrf_token),
                error="Please select a valid vendor."
            ), 422

        # Validation 3 — Invoice number
        if not f.get("invoice_number"):
            return make_page(
                "New Bill",
                make_form(f, csrf_token),
                error="Invoice number is required."
            ), 422

        # Validation 4 — Invoice date format
        if not ISO_DATE.match(f.get("invoice_date", "")):
            return make_page(
                "New Bill",
                make_form(f, csrf_token),
                error="Invoice date must be YYYY-MM-DD. Example: 2026-09-21"
            ), 422

        # Validation 5 — Due date format
        if not ISO_DATE.match(f.get("due_date", "")):
            return make_page(
                "New Bill",
                make_form(f, csrf_token),
                error="Due date must be YYYY-MM-DD. Example: 2026-10-21"
            ), 422

        # Validation 6 — Amount
        try:
            amount = float(f.get("amount", "").replace(",", ""))
            assert amount > 0
        except Exception:
            return make_page(
                "New Bill",
                make_form(f, csrf_token),
                error="Amount must be a positive number. Example: 4820.50"
            ), 422

        # Validation 7 — Currency
        if f.get("currency") not in CURRENCIES:
            return make_page(
                "New Bill",
                make_form(f, csrf_token),
                error="Please select a valid currency."
            ), 422

        # Validation 8 — Duplicate check
        for existing in state["bills"]:
            if (existing["vendor_id"] == f["vendor_id"] and
                    existing["invoice_number"] == f["invoice_number"]):
                return make_page(
                    "Duplicate Bill",
                    f"<p>Already exists: "
                    f"<a href='/payables/{existing['id']}'>"
                    f"{existing['id']}</a></p>",
                    error=f"Invoice {f['invoice_number']} already entered."
                ), 409

        # All good — create the bill
        new_id = f"BILL-{len(state['bills']) + 1:04d}"
        bill = {
            "id": new_id,
            "vendor_id": f["vendor_id"],
            "invoice_number": f["invoice_number"],
            "invoice_date": f["invoice_date"],
            "due_date": f["due_date"],
            "amount": f"{amount:.2f}",
            "currency": f["currency"],
            "status": "Entered"
        }
        state["bills"].append(bill)
        return redirect(f"/payables/{new_id}?created=1", code=303)

    @app.get("/payables/<bill_id>")
    def bill_detail(bill_id):
        bill = next(
            (b for b in state["bills"] if b["id"] == bill_id),
            None
        )
        if not bill:
            return make_page(
                "Not Found", "",
                error="Bill not found."
            ), 404

        vendor_name = VENDORS.get(bill["vendor_id"], "Unknown")
        rows = (
            f"<tr><th>Bill ID</th><td>{bill['id']}</td></tr>"
            f"<tr><th>Vendor</th><td>{vendor_name}</td></tr>"
            f"<tr><th>Invoice Number</th><td>{bill['invoice_number']}</td></tr>"
            f"<tr><th>Invoice Date</th><td>{bill['invoice_date']}</td></tr>"
            f"<tr><th>Due Date</th><td>{bill['due_date']}</td></tr>"
            f"<tr><th>Amount</th><td>{bill['amount']} {bill['currency']}</td></tr>"
            f"<tr><th>Status</th><td>{bill['status']}</td></tr>"
        )
        body = (
            f"<table>{rows}</table>"
            f"<br><a href='/payables'>← Back to all bills</a>"
        )
        notice = (
            f"✅ Bill {bill['id']} created successfully!"
            if request.args.get("created") else None
        )
        return make_page(f"Bill {bill['id']}", body, notice=notice)

    @app.post("/__reset")
    def reset():
        """Resets database — used by tests"""
        seed()
        return "reset ok"

    # Expose state so tests can inspect bills
    app.state = state

    return app


if __name__ == "__main__":
    create_app(flaky=True).run(port=5055, debug=True)