from flask import Blueprint, render_template, request

bill_details_bp = Blueprint('bill_details', __name__)

@bill_details_bp.get('/payables/<bill_id>')
def bill_details(bill_id):
    from erp_app import make_page, bills, VENDORS, CURRENCIES
    bill = None
    for b in bills:
        if b["id"] == bill_id:
            bill = b
            break
    if not bill:
       return make_page(
            "Not Found",
            "<p>No bill with that ID exists.</p>",
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

    body = f"""
    <table class="bill-table">
        {rows}
    </table>
    <br>
    <a href="/payables">← Back to all bills</a>
    """

    # Show success message if just created
    notice = None
    if request.args.get("created"):
        notice = f"✅ Bill {bill['id']} created successfully!"

    return make_page(f"Bill {bill['id']}", body, notice=notice)