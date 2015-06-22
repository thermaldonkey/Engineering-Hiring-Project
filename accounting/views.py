# You will probably need more methods from flask but this one is a good start.
from flask import render_template, request, flash, redirect, url_for, get_flashed_messages, jsonify, Response
from flask.ext import sqlalchemy

# Import things from Flask that we need.
from accounting import app, db

# Import our models
from models import Contact, Invoice, Policy

from tools import PolicyAccounting
from datetime import date, datetime
from re import match
import json

# Routing for the server.
@app.route("/")
def index():
    # You will need to serve something up here.
    return render_template('index.html')

@app.route('/v1/policy_search', methods=['GET', 'POST'])
def policy_search():
    """
    Responds to GET requests by rendering an HTML form, and POST requests by
    yielding to policy_details.
    """
    if request.method == 'GET':
        return render_template('policy_search.html')
    if request.method == 'POST':
        return policy_details(request.form)

@app.route('/v2/policy_search')
def knockout_search():
    """
    Renders an HTML form fit to asynchronously handle callbacks.
    """
    return render_template('knockout_search.html')

@app.route('/policy/<int:policy_id>')
def show_policy(policy_id):
    """
    Looks up a requested policy by policy_number, and renders a description
    of its account balance and invoices based on a given date. Renders an HTML
    template if matching data is found, and another one if no policy matches.

    @param policy_id (int): Database identifier of a policy to fetch details on
    """
    try:
        policy = Policy.query.filter_by(id=policy_id).one()
        date_string = request.args.get('date', datetime.now().date().strftime('%Y-%m-%d'))
        date_cursor = datetime.strptime(date_string, '%Y-%m-%d').date()
        account_balance = PolicyAccounting(policy.id).return_account_balance(date_cursor=date_cursor)
        current_invoices = filter(lambda inv: inv.bill_date <= date_cursor, policy.invoices)
        return render_template('show_policy.html', policy=policy, account_balance=account_balance, invoices=current_invoices)
    except sqlalchemy.orm.exc.NoResultFound:
        return policy_not_found()

@app.route('/find_policy', methods=['POST'])
def find_policy():
    """
    Looks up a requested policy by policy_number, and renders a description
    of its account balance and invoices based on a given date. Renders a JSON
    template.
    """
    json_params = json.loads(request.data)

    policy_number = json_params.get('policy_number')
    policy = Policy.query.filter_by(policy_number=policy_number).one()
    date_string = json_params.get('date', datetime.now().date().strftime('%Y-%m-%d'))
    date_cursor = datetime.strptime(date_string, '%Y-%m-%d').date()
    account_balance = PolicyAccounting(policy.id).return_account_balance(date_cursor=date_cursor)
    current_invoices = filter(lambda inv: inv.bill_date <= date_cursor, policy.invoices)

    response = render_template('policy.json', policy=policy, account_balance=account_balance, invoices=current_invoices)
    # We need to make sure we respond with JSON
    return Response(response, mimetype='application/json')

def policy_details(policy_search_params):
    """
    Fetches the requested policy, to render its details to the requestor.
    Redirects back to the search page if no such policy can be found.

    @param policy_search_params (werkzeug.datastructures.ImmutableMultiDict):
            policy_number to identify a Policy, and date to use to calculate
            account balance
    """
    date_scope = policy_search_params.get('date', datetime.now().date().strftime('%Y-%m-%d'))
    if match('\d{4}-\d\d-\d\d', policy_search_params['date']):
        try:
            policy = Policy.query.filter_by(
                policy_number=policy_search_params['policy_number']
            ).one()
            return redirect(url_for('show_policy', policy_id=policy.id, date=date_scope))
        except sqlalchemy.orm.exc.NoResultFound:
            flash('No policy found with given number')
            return redirect(url_for('policy_search'))
    else:
        flash('Date search must have format YYYY-MM-DD')
        return redirect(url_for('policy_search'))

def policy_not_found():
    """
    Renders to the requestor that no such policy exists.
    """
    return render_template('policy_not_found.html')

