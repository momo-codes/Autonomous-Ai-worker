from flask import Blueprint, render_template

bills_bp = Blueprint('bills', __name__)

@bills_bp.get('/payables')
def payables():
    from erp_app import make_page, bills
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