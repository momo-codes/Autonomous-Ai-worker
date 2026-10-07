from flask import Blueprint, render_template
home_bp = Blueprint('home',__name__)

@home_bp.get('/')
def home():
    from erp_app import make_page
    body = "<p>Welcone to Acme ERP</p><p><a href='/payables'>Go to Accounts Payable</a></p>"
    return make_page("Home", body)
