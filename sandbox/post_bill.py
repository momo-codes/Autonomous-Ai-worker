from flask import Blueprint, render_template, request, redirect
import re


post_bill_bp = Blueprint('post_bill', __name__)

@post_bill_bp.post('/payables')
def create_bill():
    from erp_app import (
        make_page,          
        ISO_DATE,       
        bills,          
        VENDORS, 
        CURRENCIES, 
        CSRF_TOKEN, 
        stats
    )
    from new_bill import make_form
    stats["post_attempts"] += 1
       
        # TRAP 1 - First attempt always fails
       # Tests if the AI can recover from a temporary error  
    
    if(stats["post_attempts"] == 1):
        return make_page(
            "Service Unavailable",
            "<p>The ledger service is busy. Please retry in a moment.</p>",
            error="503 - Temporary server error. Please try again."
        ), 503

    f = {}
    for key in request.form:
        f[key] = request.form[key].strip()

    # VALIDATION 1 - Check CSRF token
    if f.get("csrf_token") != CSRF_TOKEN:
        return make_page(
            "Forbidden",
            "<p>Security token missing. Go back and try again.</p>",
            error="Invalid CSRF token."
        ), 403

    # VALIDATION 2 - Vendor must be selected
    if f.get("vendor_id") not in VENDORS:
        return make_page(
            "New Bill",
            make_form(f),
            error="Please select a valid vendor."
        ), 422

    # VALIDATION 3 - Invoice number required
    if not f.get("invoice_number"):
        return make_page(
            "New Bill",
            make_form(f),
            error="Invoice number is required."
        ), 422

    # VALIDATION 4 - Dates must be YYYY-MM-DD
    if not ISO_DATE.match(f.get("invoice_date", "")):
        return make_page(
            "New Bill",
            make_form(f),
            error="Invoice date must be in YYYY-MM-DD format. Example: 2026-09-21"
        ), 422

    if not ISO_DATE.match(f.get("due_date", "")):
        return make_page(
            "New Bill",
            make_form(f),
            error="Due date must be in YYYY-MM-DD format. Example: 2026-10-21"
        ), 422

    # VALIDATION 5 - Amount must be a number
    try:
        amount = float(f.get("amount", "").replace(",", ""))
        if amount <= 0:
            raise ValueError("must be positive")
    except Exception:
        return make_page(
            "New Bill",
            make_form(f),
            error="Amount must be a positive number. Example: 4820.50"
        ), 422

    # VALIDATION 6 - Currency must be valid
    if f.get("currency") not in CURRENCIES:
        return make_page(
            "New Bill",
            make_form(f),
            error="Please select a valid currency."
        ), 422

    # VALIDATION 7 - Check for duplicate invoice
    for existing in bills:
        if (existing["vendor_id"] == f["vendor_id"] and
                existing["invoice_number"] == f["invoice_number"]):
            return make_page(
                "Duplicate Bill",
                f"<p>This invoice already exists. See <a href='/payables/{existing['id']}'>"
                f"{existing['id']}</a></p>",
                error=f"Invoice {f['invoice_number']} already entered for this vendor."
            ), 409

    # ALL CHECKS PASSED - Create the bill
    new_id = f"BILL-{len(bills) + 1:04d}"
    bill = {
        "id": new_id,
        "vendor_id": f["vendor_id"],
        "vendor": VENDORS[f["vendor_id"]],
        "invoice_number": f["invoice_number"],
        "invoice_date": f["invoice_date"],
        "due_date": f["due_date"],
        "amount": f"{amount:.2f}",
        "currency": f["currency"],
        "status": "Entered"
    }
    bills.append(bill)

    # Redirect to the new bill page (like res.redirect in Express)
    return redirect(f"/payables/{new_id}?created=1", code=303)
    