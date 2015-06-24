# You will probably need more methods from flask but this one is a good start.
from flask import render_template, request, flash, redirect, url_for, get_flashed_messages, jsonify, Response
import sqlalchemy as realSQLAlchemy
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
    policy = find_policy_by(id=policy_id)
    if policy:
        return render_policy_details(policy, request.args.get('date'), 'show_policy.html')
    else:
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

    policy = find_policy_by(policy_number=policy_number)

    if policy:
        response = render_policy_details(policy, json_params.get('date'), 'policy.json')
        # We need to make sure we respond with JSON
        return Response(response, mimetype='application/json')
    else:
        return policy_not_found()

@app.route('/change_billing_schedule', methods=['POST'])
def change_billing_schedule():
    """
    Changes the billing schedule of the referenced policy and renders it in
    response, as JSON.
    """
    json_params = json.loads(request.data)

    pa = PolicyAccounting(json_params.get('id'))
    pa.change_billing_schedule(json_params.get('billing_schedule'))

    # Typically, we'd be concerned if this returned None, but nobody changes
    # this value, so we're good.
    policy = find_policy_by(id=json_params.get('id'))

    # This will reset the date scope in HTML views to the current date. This
    # made sense as changing billing schedule no longer pertains to a date
    # range. A form already exists to scope invoices and account balance after
    # the fact.
    response = render_policy_details(policy, None, 'policy.json')
    return Response(response, mimetype='application/json')

@app.route('/make_payment', methods=['POST'])
def make_payment():
    """
    Applies a new payment to the given policy, filed under the current date
    and the policy's named insured. Details on the policy are then
    recomputed and rendered to the requestor as JSON.

    If no named insured exists for the policy, a 422 status is rendered.
    """
    json_params = json.loads(request.data)
    policy_id = json_params.get('chosenPolicyData').get('id')
    amount = int(json_params.get('paymentAmount'))

    pa = PolicyAccounting(policy_id)
    try:
        pa.make_payment(amount=amount)
    except realSQLAlchemy.exc.IntegrityError:
        db.session.rollback()
        return "", 422

    # Typically, we'd be concerned if this returned None, but nobody changes
    # this value, so we're good.
    policy = find_policy_by(id=policy_id)

    # This will reset the date scope in HTML views to the current date. This
    # made sense as making a payment is only considered for the current day.
    # A form already exists to scope invoices and account balance after the
    # fact.
    response = render_policy_details(policy, None, 'policy.json')
    return Response(response, mimetype='application/json')

# Helper methods

def find_policy_by(**kwargs):
    """
    Attempts to fetch a single Policy record from the database matching the
    given filter(s).

    @param kwargs (dict): mapping of Policy filters to gather a single record
            from the database. Expected keys are: id, policy_number
    @return (Policy,NoneType): Policy object if one is found to match the
            given criteria. None otherwise.
    """
    try:
        return Policy.query.filter_by(**kwargs).one()
    except sqlalchemy.orm.exc.NoResultFound:
        return None

def render_policy_details(policy, date_param, template):
    """
    Accumulates the account balance and any invoices of interest to the given
    policy, and renders the data under the given template.

    If no date string is given, the date string of the current day will be used
    for scoping results.

    @param policy (Policy): Policy to be rendered
    @param date_param (str): Date in format YYYY-MM-DD to scope policy
            association lookups
    @param template (str): Name of a template, by which the given policy
            should be rendered
    @return (str): Content ready to be built into a werkzeug.wrappers.Response
    """
    date_string = date_param or datetime.now().date().strftime('%Y-%m-%d')
    date_cursor = datetime.strptime(date_string, '%Y-%m-%d').date()
    account_balance = PolicyAccounting(policy.id).return_account_balance(date_cursor=date_cursor)
    current_invoices = filter(lambda inv: inv.bill_date <= date_cursor, policy.invoices)
    return render_template(template, policy=policy, account_balance=account_balance, invoices=current_invoices)

def policy_details(policy_search_params):
    """
    Fetches the requested policy, to render its details to the requestor.
    Redirects back to the search page if no such policy can be found.

    @param policy_search_params (werkzeug.datastructures.ImmutableMultiDict):
            policy_number to identify a Policy, and date to use to calculate
            account balance
    @return (str): werkzeug.wrappers.Response for a redirection
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

    @return (str): Content of the "policy not found" template
    @return (int): 404, status code for response
    """
    return render_template('policy_not_found.html'), 404

