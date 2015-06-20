#!/user/bin/env python2.7

from datetime import date, datetime
from dateutil.relativedelta import relativedelta

from accounting import db
from models import Contact, Invoice, Payment, Policy

"""
#######################################################
This is the base code for the intern project.

If you have any questions, please contact Amanda at:
    amanda@britecore.com
#######################################################
"""

class PolicyAccounting(object):
    """
     Each policy has its own instance of accounting.
    """
    def __init__(self, policy_id):
        """
        Initializes accounting for the given policy. Builds out invoices for
        the policy if none already exist.

        @param policy_id (int): ID of the policy whose accounting should be
                built
        """
        self.policy = Policy.query.filter_by(id=policy_id).one()

        if not self.policy.invoices:
            self.make_invoices()

    def return_account_balance(self, date_cursor=None):
        """
        Returns outstanding balance suggested by contextual policy's invoices
        whose billing date is less than or equal to the date scope, minus all
        payments recorded within that same timeframe.

        Date scope defaults to the current date if no value is given.

        @param date_cursor (datetime.date,NoneType): Date to use when scoping
                which invoices' amounts due should be expected, and which
                payments' amounts paid should be credited to the return

        @return (int): Amount currently due on the policy in context
        """
        if not date_cursor:
            date_cursor = datetime.now().date()

        # All of the policy's non-deleted invoices that have been billed and
        # should be expecting payment.
        invoices = Invoice.query.filter_by(policy_id=self.policy.id)\
                                .filter(Invoice.bill_date <= date_cursor)\
                                .filter(Invoice.deleted == False)\
                                .order_by(Invoice.bill_date)\
                                .all()
        due_now = 0
        for invoice in invoices:
            due_now += invoice.amount_due

        # All of the policy's payments that should be applied to invoices'
        # outstanding balances.
        payments = Payment.query.filter_by(policy_id=self.policy.id)\
                                .filter(Payment.transaction_date <= date_cursor)\
                                .all()
        for payment in payments:
            due_now -= payment.amount_paid

        return due_now

    def make_payment(self, contact_id=None, date_cursor=None, amount=0):
        """
        Records a new payment for the contextual policy, to be processed
        on a specified date, and returns that payment.

        Payment is associated with the policy's named insured if no Contact
        reference is given.

        Transaction date defaults to the current date.

        @param contact_id (int,NoneType): ID of the Contact with which to
                associate the new payment
        @param date_cursor (datetime.date,NoneType): Date to use for the new
                payment's transaction_date
        @param amount (int): Amount to credit the contextual policy with the
                new payment

        @return (payment): New payment, associated with the policy in context
        """
        if not date_cursor:
            date_cursor = datetime.now().date()

        if not contact_id:
            try:
                contact_id = self.policy.named_insured
            except:
                pass

        payment = Payment(self.policy.id,
                          contact_id,
                          amount,
                          date_cursor)
        db.session.add(payment)
        db.session.commit()

        return payment

    def evaluate_cancellation_pending_due_to_non_pay(self, date_cursor=None):
        """
         If this function returns true, an invoice
         on a policy has passed the due date without
         being paid in full. However, it has not necessarily
         made it to the cancel_date yet.

        @param date_cursor (datetime.date,NoneType): Date by which to scope
                invoices for the policy in context such that they are due, but
                not yet cancellable.

        @return (bool): True if policy has any overdue invoices, False if paid
                in full.
        """
        if not date_cursor:
            date_cursor = datetime.now().date()

        # All of the policy's invoices that are due to be paid, but not yet
        # ready to be cancelled.
        invoices = Invoice.query.filter_by(policy_id=self.policy.id)\
                                .filter(Invoice.cancel_date > date_cursor)\
                                .filter(Invoice.due_date <= date_cursor)\
                                .order_by(Invoice.bill_date)\
                                .all()

        for invoice in invoices:
            if not self.return_account_balance(date_cursor):
                return False
            else:
                return True

    def evaluate_cancel(self, date_cursor=None, reason=None):
        """
        Checks all the contextual policy's invoices, whose cancel date occurs
        before or on the given date, to ensure their account balances are paid
        in full prior to or on their cancel date.

        If any invoices are not paid in time, the policy is cancelled. This
        modifies the policy's status, updates its cancel_date, and assigns
        its cancel_reason, should a reason be provided.

        If no invoices have reached their cancel date, the policy is suggested
        to not be cancelled.

        If no date is given, date scope defaults to the current date.

        @param date_cursor (datetime.date,NoneType): Date by which to scope
                which invoices could potentially be cancelled
        @param reason (str,NoneType): Reason policy is to be cancelled, should
                it qualify
        """
        if not date_cursor:
            date_cursor = datetime.now().date()

        # All of the policies invoices that are due to be cancelled, should
        # their amounts due not be paid in full.
        invoices = Invoice.query.filter_by(policy_id=self.policy.id)\
                                .filter(Invoice.cancel_date <= date_cursor)\
                                .order_by(Invoice.bill_date)\
                                .all()

        for invoice in invoices:
            if not self.return_account_balance(invoice.cancel_date):
                continue
            else:
                print "THIS POLICY SHOULD HAVE CANCELED"
                self.policy.status = 'Canceled'
                self.policy.cancel_date = datetime.now().date()
                self.policy.cancel_reason = reason
                break
        else:
            print "THIS POLICY SHOULD NOT CANCEL"


    def make_invoices(self):
        """
        Deletes all invoices associated with the contextual policy, and
        rebuilds as many as are appropriate for the policy's billing schedule.

        Bill dates, due dates, and cancel dates for all invoices are dispersed
        over a year to evenly distribute portions of the policy's annual
        premium.

        If the policy's billing schedule is not recognized, a warning is
        displayed, and only a single invoice, requesting the full annual
        premium, is persisted.
        """
        for invoice in self.policy.invoices:
            invoice.delete()

        billing_schedules = {'Annual': None, 'Semi-Annual': 3, 'Quarterly': 4, 'Monthly': 12}

        invoices = []
        first_invoice = Invoice(self.policy.id,
                                self.policy.effective_date, #bill_date
                                self.policy.effective_date + relativedelta(months=1), #due
                                self.policy.effective_date + relativedelta(months=1, days=14), #cancel
                                self.policy.annual_premium)
        invoices.append(first_invoice)

        if self.policy.billing_schedule == "Annual":
            pass
        elif self.policy.billing_schedule == "Two-Pay":
            first_invoice.amount_due = first_invoice.amount_due / billing_schedules.get(self.policy.billing_schedule)
            for i in range(1, billing_schedules.get(self.policy.billing_schedule)):
                months_after_eff_date = i*6
                bill_date = self.policy.effective_date + relativedelta(months=months_after_eff_date)
                invoice = Invoice(self.policy.id,
                                  bill_date,
                                  bill_date + relativedelta(months=1),
                                  bill_date + relativedelta(months=1, days=14),
                                  self.policy.annual_premium / billing_schedules.get(self.policy.billing_schedule))
                invoices.append(invoice)
        elif self.policy.billing_schedule == "Quarterly":
            first_invoice.amount_due = first_invoice.amount_due / billing_schedules.get(self.policy.billing_schedule)
            for i in range(1, billing_schedules.get(self.policy.billing_schedule)):
                months_after_eff_date = i*3
                bill_date = self.policy.effective_date + relativedelta(months=months_after_eff_date)
                invoice = Invoice(self.policy.id,
                                  bill_date,
                                  bill_date + relativedelta(months=1),
                                  bill_date + relativedelta(months=1, days=14),
                                  self.policy.annual_premium / billing_schedules.get(self.policy.billing_schedule))
                invoices.append(invoice)
        elif self.policy.billing_schedule == "Monthly":
            first_invoice.amount_due = first_invoice.amount_due / billing_schedules.get(self.policy.billing_schedule)
            for i in range(1, billing_schedules.get(self.policy.billing_schedule)):
                months_after_eff_date = i*1
                bill_date = self.policy.effective_date + relativedelta(months=months_after_eff_date)
                invoice = Invoice(self.policy.id,
                                  bill_date,
                                  bill_date + relativedelta(months=1),
                                  bill_date + relativedelta(months=1, days=14),
                                  self.policy.annual_premium / billing_schedules.get(self.policy.billing_schedule))
                invoices.append(invoice)
        else:
            print "You have chosen a bad billing schedule."

        for invoice in invoices:
            db.session.add(invoice)
        db.session.commit()

    def change_billing_schedule(self, new_schedule):
        """
        Reassigns the contextual policy's billing schedule and rebuilds
        invoices.

        Marks all existing invoices as deleted, but does not remove them from
        the database.

        Maintains all applied payments to the policy.

        @param new_schedule (str): New billing schedule to apply to existing
                policy. Must be a valid Policy.billing_schedule.
        """
        self.policy.billing_schedule = new_schedule
        self.make_invoices()

################################
# The functions below are for the db and 
# shouldn't need to be edited.
################################
def build_or_refresh_db():
    db.drop_all()
    db.create_all()
    insert_data()
    print "DB Ready!"

def insert_data():
    #Contacts
    contacts = []
    john_doe_agent = Contact('John Doe', 'Agent')
    contacts.append(john_doe_agent)
    john_doe_insured = Contact('John Doe', 'Named Insured')
    contacts.append(john_doe_insured)
    bob_smith = Contact('Bob Smith', 'Agent')
    contacts.append(bob_smith)
    anna_white = Contact('Anna White', 'Named Insured')
    contacts.append(anna_white)
    joe_lee = Contact('Joe Lee', 'Agent')
    contacts.append(joe_lee)
    ryan_bucket = Contact('Ryan Bucket', 'Named Insured')
    contacts.append(ryan_bucket)

    for contact in contacts:
        db.session.add(contact)
    db.session.commit()

    policies = []
    p1 = Policy('Policy One', date(2015, 1, 1), 365)
    p1.billing_schedule = 'Annual'
    p1.agent = bob_smith.id
    policies.append(p1)

    p2 = Policy('Policy Two', date(2015, 2, 1), 1600)
    p2.billing_schedule = 'Quarterly'
    p2.named_insured = anna_white.id
    p2.agent = joe_lee.id
    policies.append(p2)

    p3 = Policy('Policy Three', date(2015, 1, 1), 1200)
    p3.billing_schedule = 'Monthly'
    p3.named_insured = ryan_bucket.id
    p3.agent = john_doe_agent.id
    policies.append(p3)

    for policy in policies:
        db.session.add(policy)
    db.session.commit()

    for policy in policies:
        PolicyAccounting(policy.id)

    payment_for_p2 = Payment(p2.id, anna_white.id, 400, date(2015, 2, 1))
    db.session.add(payment_for_p2)
    db.session.commit()

