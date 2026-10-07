from flask import Blueprint, render_template
new_bill_bp = Blueprint('new_bill', __name__)

@new_bill_bp.get('/payables/new')
def new_bill():
    from erp_app import make_page
    body = make_form({})
    return make_page("Create New Bill", body)



def make_form(values):
    from erp_app import VENDORS, CURRENCIES, CSRF_TOKEN
    # Build vendor dropdown options
    vendor_options = "<option value=''>-- select vendor --</option>"
    for vid, vname in VENDORS.items():
        selected = "selected" if values.get("vendor_id") == vid else ""
        vendor_options += f"<option value='{vid}' {selected}>{vname}</option>"

    # Build currency dropdown options
    currency_options = ""
    for c in CURRENCIES:
        selected = "selected" if values.get("currency", "INR") == c else ""
        currency_options += f"<option value='{c}' {selected}>{c}</option>"

    return f"""
    <form method="POST" action="/payables">

        <!-- Hidden security token - AI must find and submit this -->
        <input type="hidden" name="csrf_token" value="{CSRF_TOKEN}">

        <label>Vendor</label>
        <select name="vendor_id" required>
            {vendor_options}
        </select>

        <label>Invoice Number</label>
        <input
            type="text"
            name="invoice_number"
            value="{values.get('invoice_number', '')}"
            placeholder="e.g. INV-2057"
            required
        >

        <label>Invoice Date (YYYY-MM-DD)</label>
        <input
            type="text"
            name="invoice_date"
            value="{values.get('invoice_date', '')}"
            placeholder="e.g. 2026-09-21"
            required
        >

        <label>Due Date (YYYY-MM-DD)</label>
        <input
            type="text"
            name="due_date"
            value="{values.get('due_date', '')}"
            placeholder="e.g. 2026-10-21"
            required
        >

        <label>Total Amount (including tax)</label>
        <input
            type="text"
            name="amount"
            value="{values.get('amount', '')}"
            placeholder="e.g. 4820.50"
            required
        >

        <label>Currency</label>
        <select name="currency">
            {currency_options}
        </select>

        <br>
        <button type="submit">Create Bill</button>
    </form>
    """