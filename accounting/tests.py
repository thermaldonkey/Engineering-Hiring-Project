#!/user/bin/env python2.7

import unittest
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

from accounting import app, db
from models import Contact, Invoice, Payment, Policy
from tools import PolicyAccounting

from flask import url_for

"""
#######################################################
Test Suite for PolicyAccounting
#######################################################
"""

class TestBillingSchedules(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_agent = Contact('Test Agent', 'Agent')
        cls.test_insured = Contact('Test Insured', 'Named Insured')
        db.session.add(cls.test_agent)
        db.session.add(cls.test_insured)
        db.session.commit()

        cls.policy = Policy('Test Policy', date(2015, 1, 1), 1200)
        db.session.add(cls.policy)
        cls.policy.named_insured = cls.test_insured.id
        cls.policy.agent = cls.test_agent.id
        db.session.commit()

    @classmethod
    def tearDownClass(cls):
        db.session.delete(cls.test_insured)
        db.session.delete(cls.test_agent)
        db.session.delete(cls.policy)
        db.session.commit()

    def setUp(self):
        pass

    def tearDown(self):
        for invoice in self.policy.invoices:
            db.session.delete(invoice)
        db.session.commit()

    def test_annual_billing_schedule(self):
        self.policy.billing_schedule = "Annual"
        #No invoices currently exist
        self.assertFalse(self.policy.invoices)
        #Invoices should be made when the class is initiated
        pa = PolicyAccounting(self.policy.id)
        self.assertEquals(len(self.policy.invoices), 1)
        self.assertEquals(self.policy.invoices[0].amount_due, self.policy.annual_premium)

    def test_monthly_billing_schedule(self):
        self.policy.billing_schedule = "Monthly"
        # We shouldn't have any invoices
        self.assertFalse(self.policy.invoices)

        pa = PolicyAccounting(self.policy.id)
        # Invoices should now exist
        number_of_billings = len(self.policy.invoices)
        self.assertEquals(number_of_billings, 12)
        amounts_due = [invoice.amount_due for invoice in self.policy.invoices]
        for amount in amounts_due:
            self.assertEquals(amount, self.policy.annual_premium/number_of_billings)


class TestEvaluateCancellationPendingDueToNonPay(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_insured = Contact('Test Insured', 'Named Insured')
        cls.test_agent = Contact('Test Agent', 'Agent')
        db.session.add(cls.test_insured)
        db.session.add(cls.test_agent)
        db.session.commit()

        cls.policy = Policy('Test Policy', date(2015,1,1), 400)
        cls.policy.named_insured = cls.test_insured.id
        cls.policy.agent = cls.test_agent.id
        db.session.add(cls.policy)
        db.session.commit()

    @classmethod
    def tearDownClass(cls):
        db.session.delete(cls.test_insured)
        db.session.delete(cls.test_agent)
        db.session.delete(cls.policy)
        db.session.commit()

    def tearDown(self):
        self.policy.billing_schedule = 'Annual'
        for payment in Payment.query.filter_by(policy_id=self.policy.id).all():
            db.session.delete(payment)
        for invoice in self.policy.invoices:
            db.session.delete(invoice)
        db.session.commit()

    def test_false_when_paid_in_full(self):
        pa = PolicyAccounting(self.policy.id)
        limbo_date = self.policy.invoices[0].due_date + relativedelta(days=1)
        for invoice in self.policy.invoices:
            pa.make_payment(date_cursor=invoice.due_date,amount=invoice.amount_due)

        self.assertEquals(pa.return_account_balance(date_cursor=limbo_date), 0)
        self.assertFalse(pa.evaluate_cancellation_pending_due_to_non_pay(date_cursor=limbo_date))

    def test_false_when_policy_cancelled(self):
        pa = PolicyAccounting(self.policy.id)
        already_cancelled_date = self.policy.invoices[0].cancel_date + relativedelta(days=1)

        self.assertNotEquals(pa.return_account_balance(date_cursor=already_cancelled_date), 0)
        self.assertFalse(pa.evaluate_cancellation_pending_due_to_non_pay(date_cursor=already_cancelled_date))

    def test_true_when_one_invoice_not_paid(self):
        pa = PolicyAccounting(self.policy.id)
        limbo_date = self.policy.invoices[0].due_date + relativedelta(days=1)

        self.assertNotEquals(pa.return_account_balance(date_cursor=limbo_date), 0)
        self.assertTrue(pa.evaluate_cancellation_pending_due_to_non_pay(date_cursor=limbo_date))

    def test_true_when_many_invoices_not_paid(self):
        self.policy.billing_schedule = 'Quarterly'
        pa = PolicyAccounting(self.policy.id)
        limbo_date = self.policy.invoices[0].due_date + relativedelta(days=1)

        self.assertNotEquals(pa.return_account_balance(date_cursor=limbo_date), 0)
        self.assertTrue(pa.evaluate_cancellation_pending_due_to_non_pay(date_cursor=limbo_date))

class TestEvaluateCancel(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_agent = Contact('Test Agent', 'Agent')
        cls.test_insured = Contact('Test Insured', 'Named Insured')
        db.session.add(cls.test_agent)
        db.session.add(cls.test_insured)
        db.session.commit()

        cls.policy = Policy('Test Policy', date(2015, 1, 1), 1200)
        cls.policy.named_insured = cls.test_insured.id
        cls.policy.agent = cls.test_agent.id
        db.session.add(cls.policy)
        db.session.commit()

    @classmethod
    def tearDownClass(cls):
        db.session.delete(cls.test_insured)
        db.session.delete(cls.test_agent)
        db.session.delete(cls.policy)
        db.session.commit()

    def setUp(self):
        self.pa = PolicyAccounting(self.policy.id)

    def tearDown(self):
        self.policy.cancel_date = None
        self.policy.cancel_reason = None
        for invoice in self.policy.invoices:
            db.session.delete(invoice)
        db.session.commit()

    def test_changes_policy_status(self):
        cancellation_date = self.policy.invoices[-1].cancel_date

        self.assertEquals(self.policy.status, 'Active')
        self.pa.evaluate_cancel(date_cursor=cancellation_date)
        self.assertEquals(self.policy.status, 'Canceled')

    def test_stores_cancel_date(self):
        cancellation_date = self.policy.invoices[-1].cancel_date

        self.assertIsNone(self.policy.cancel_date)
        self.pa.evaluate_cancel(date_cursor=cancellation_date)
        self.assertEquals(self.policy.cancel_date, datetime.now().date())

    def test_stores_cancel_reason(self):
        cancellation_date = self.policy.invoices[-1].cancel_date
        cancellation_reason = 'Because I said so'

        self.assertIsNone(self.policy.cancel_reason)
        self.pa.evaluate_cancel(date_cursor=cancellation_date, reason=cancellation_reason)
        self.assertEquals(self.policy.cancel_reason, cancellation_reason)

class TestChangeBillingSchedule(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_agent = Contact('Test Agent', 'Agent')
        cls.test_insured = Contact('Test Insured', 'Named Insured')
        db.session.add(cls.test_agent)
        db.session.add(cls.test_insured)
        db.session.commit()

        cls.policy = Policy('Test Policy', date(2015, 1, 1), 1200)
        cls.policy.named_insured = cls.test_insured.id
        cls.policy.agent = cls.test_agent.id
        db.session.add(cls.policy)
        db.session.commit()

    @classmethod
    def tearDownClass(cls):
        db.session.delete(cls.test_insured)
        db.session.delete(cls.test_agent)
        db.session.delete(cls.policy)
        db.session.commit()

    def tearDown(self):
        for payment in Payment.query.filter_by(policy_id=self.policy.id).all():
            db.session.delete(payment)
        for invoice in self.policy.invoices:
            db.session.delete(invoice)
        db.session.commit()

    def test_quarterly_to_monthly(self):
        self.policy.billing_schedule = 'Quarterly'
        pa = PolicyAccounting(self.policy.id)

        # Ensure quarterly billing sets up as expected
        self.assertEquals(len(self.policy.invoices), 4)
        final_due_date = self.policy.invoices[-1].due_date
        self.assertEquals(pa.return_account_balance(date_cursor=final_due_date), self.policy.annual_premium)

        # Make a payment
        first_due_date = self.policy.invoices[0].due_date
        first_amount_due = self.policy.invoices[0].amount_due
        payment = pa.make_payment(date_cursor=first_due_date,amount=first_amount_due)

        pa.change_billing_schedule('Monthly')

        # There should now be 16 invoices; 4 deleted, 12 not deleted
        self.assertEquals(len(self.policy.invoices), 16)
        for i in xrange(len(self.policy.invoices)):
            if i < 4:
                self.assertTrue(self.policy.invoices[i].deleted)
            else:
                self.assertFalse(self.policy.invoices[i].deleted)

        final_due_date = self.policy.invoices[-1].due_date
        self.assertEquals(pa.return_account_balance(date_cursor=final_due_date), self.policy.annual_premium - payment.amount_paid)

    def test_annual_to_quarterly(self):
        self.policy.billing_schedule = 'Annual'
        pa = PolicyAccounting(self.policy.id)

        # Ensure annual billing sets up as expected
        self.assertEquals(len(self.policy.invoices), 1)
        final_due_date = self.policy.invoices[-1].due_date
        self.assertEquals(pa.return_account_balance(date_cursor=final_due_date), self.policy.annual_premium)

        # Make a payment
        first_due_date = self.policy.invoices[0].due_date
        first_amount_due = self.policy.invoices[0].amount_due
        payment = pa.make_payment(date_cursor=first_due_date,amount=first_amount_due/2)

        pa.change_billing_schedule('Quarterly')

        # There should now be 5 invoices; 1 deleted, 4 not deleted
        self.assertEquals(len(self.policy.invoices), 5)
        for i in xrange(len(self.policy.invoices)):
            if i < 1:
                self.assertTrue(self.policy.invoices[i].deleted)
            else:
                self.assertFalse(self.policy.invoices[i].deleted)

        final_due_date = self.policy.invoices[-1].due_date
        self.assertEquals(pa.return_account_balance(date_cursor=final_due_date), self.policy.annual_premium - payment.amount_paid)

class TestReturnAccountBalance(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_agent = Contact('Test Agent', 'Agent')
        cls.test_insured = Contact('Test Insured', 'Named Insured')
        db.session.add(cls.test_agent)
        db.session.add(cls.test_insured)
        db.session.commit()

        cls.policy = Policy('Test Policy', date(2015, 1, 1), 1200)
        cls.policy.named_insured = cls.test_insured.id
        cls.policy.agent = cls.test_agent.id
        db.session.add(cls.policy)
        db.session.commit()

    @classmethod
    def tearDownClass(cls):
        db.session.delete(cls.test_insured)
        db.session.delete(cls.test_agent)
        db.session.delete(cls.policy)
        db.session.commit()

    def setUp(self):
        self.payments = []

    def tearDown(self):
        for invoice in self.policy.invoices:
            db.session.delete(invoice)
        for payment in self.payments:
            db.session.delete(payment)
        db.session.commit()

    def test_annual_on_eff_date(self):
        self.policy.billing_schedule = "Annual"
        pa = PolicyAccounting(self.policy.id)
        self.assertEquals(pa.return_account_balance(date_cursor=self.policy.effective_date), 1200)

    def test_quarterly_on_eff_date(self):
        self.policy.billing_schedule = "Quarterly"
        pa = PolicyAccounting(self.policy.id)
        self.assertEquals(pa.return_account_balance(date_cursor=self.policy.effective_date), 300)

    def test_quarterly_on_last_installment_bill_date(self):
        self.policy.billing_schedule = "Quarterly"
        pa = PolicyAccounting(self.policy.id)
        invoices = Invoice.query.filter_by(policy_id=self.policy.id)\
                                .order_by(Invoice.bill_date).all()
        self.assertEquals(pa.return_account_balance(date_cursor=invoices[3].bill_date), 1200)

    def test_quarterly_on_second_installment_bill_date_with_full_payment(self):
        self.policy.billing_schedule = "Quarterly"
        pa = PolicyAccounting(self.policy.id)
        invoices = Invoice.query.filter_by(policy_id=self.policy.id)\
                                .order_by(Invoice.bill_date).all()
        self.payments.append(pa.make_payment(contact_id=self.policy.named_insured,
                                             date_cursor=invoices[1].bill_date, amount=600))
        self.assertEquals(pa.return_account_balance(date_cursor=invoices[1].bill_date), 0)

    def test_quarterly_on_last_installment_bill_date_with_deleted_invoice(self):
        self.policy.billing_schedule = "Quarterly"
        pa = PolicyAccounting(self.policy.id)
        invoices = Invoice.query.filter_by(policy_id=self.policy.id)\
                                .order_by(Invoice.bill_date).all()

        # Mark first invoice for deletion
        invoice = invoices[0]
        invoice.deleted = True
        db.session.add(invoice)
        db.session.commit()

        self.assertEquals(pa.return_account_balance(date_cursor=invoices[3].bill_date), 900)

class BriceCorTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = app.test_client()
        cls.test_insured = Contact('Test Insured', 'Named Insured')
        db.session.add(cls.test_insured)
        db.session.commit()

        cls.policy = Policy('Test Policy', date(2015, 1, 1), 1200)
        cls.policy.named_insured = cls.test_insured.id
        db.session.add(cls.policy)
        db.session.commit()

    @classmethod
    def tearDownClass(cls):
        db.session.delete(cls.policy)
        db.session.delete(cls.test_insured)
        db.session.commit()

    def setUp(self):
        """
        No idea why, but in some of the tests in this suite, every call to
        `self.policy` referenced a detached instance. Any calls to
        `Policy#invoices` after that threw a DetachedInstanceError. If anyone
        can see what I'm doing to cause that, I would love to hear it.
        """
        self.policy = Policy.query.get(self.policy.id)
        self.original_effective_date = self.policy.effective_date

    def tearDown(self):
        for payment in Payment.query.filter_by(policy_id=self.policy.id).all():
            db.session.delete(payment)
        for invoice in Invoice.query.filter_by(policy_id=self.policy.id).all():
            db.session.delete(invoice)
        self.policy = self.original_effective_date
        db.session.commit()

    def test_home_page_links_to_search(self):
        response = self.app.get('/')
        self.assertRegexpMatches(response.data, 'href="/policy_search"')

    def test_search_contains_form(self):
        response = self.app.get('/policy_search')
        self.assertRegexpMatches(response.data, 'form action="/policy_search" method="POST"')
        self.assertRegexpMatches(response.data, 'input type="\w*" name="policy_number"')
        self.assertRegexpMatches(response.data, 'input type="\w*" name="date"')

    def test_searching_redirects_to_policy(self):
        response = self.app.post('/policy_search', data={'policy_number': self.policy.policy_number, 'date': '2015-01-01'})
        self.assertEquals(response.status_code, 302)
        self.assertRegexpMatches(response.location, '/policy/' + str(self.policy.id))

    def test_searching_allows_scoping_policy_account_balance(self):
        self.policy.billing_schedule = 'Quarterly'
        pa = PolicyAccounting(self.policy.id)
        second_invoice = self.policy.invoices[1]
        balance_as_of_second_invoice = pa.return_account_balance(date_cursor=second_invoice.due_date)

        response = self.app.post('/policy_search', data={'policy_number': self.policy.policy_number, 'date': str(second_invoice.due_date)}, follow_redirects=True)
        self.assertRegexpMatches(response.data, 'Account balance: \$' + str(balance_as_of_second_invoice))

    def test_bad_date_scope_gives_user_feedback(self):
        response = self.app.post('/policy_search', data={'policy_number': self.policy.policy_number, 'date': ''}, follow_redirects=True)
        self.assertRegexpMatches(response.data, 'Date search must have format YYYY-MM-DD')

    def test_bad_policy_number_gives_user_feedback(self):
        not_policy_number = self.policy.policy_number + 'foo'
        response = self.app.post('/policy_search', data={'policy_number': not_policy_number, 'date': '2015-01-01'}, follow_redirects=True)
        self.assertRegexpMatches(response.data, 'No policy found with given number')

    def test_bad_search_redirects_back_to_search(self):
        not_policy_number = self.policy.policy_number + 'foo'
        response = self.app.post('/policy_search', data={'policy_number': not_policy_number, 'date': '2015-01-01'})
        self.assertEquals(response.status_code, 302)
        self.assertRegexpMatches(response.location, '/policy_search')

    def test_viewing_missing_policy_gives_user_a_way_home(self):
        not_policy_id = self.policy.id + 1
        response = self.app.get('/policy/' + str(not_policy_id))
        self.assertRegexpMatches(response.data, 'href="/"')

    def test_viewing_policy_shows_all_current_and_outstanding_invoices(self):
        self.policy.billing_schedule = 'Quarterly'
        # With this effective date, current date will consider only the first
        # two invoices as current or outsanding.
        self.policy.effective_date = datetime.now().date() - relativedelta(months=3)
        pa = PolicyAccounting(self.policy.id)
        first_invoice = self.policy.invoices[0]
        pa.make_payment(date_cursor=first_invoice.due_date, amount=300)
        current_invoices = filter(lambda inv: inv.bill_date <= datetime.now().date(), self.policy.invoices)

        response = self.app.get('/policy/' + str(self.policy.id))
        self.assertRegexpMatches(response.data, 'Invoices')
        for invoice in current_invoices:
            self.assertRegexpMatches(response.data, str(invoice.bill_date))
            self.assertRegexpMatches(response.data, str(invoice.cancel_date))
            self.assertRegexpMatches(response.data, str(invoice.due_date))
            self.assertRegexpMatches(response.data, str(invoice.amount_due))
            self.assertRegexpMatches(response.data, str(invoice.deleted))

    def test_viewing_policy_displays_current_account_balance(self):
        pa = PolicyAccounting(self.policy.id)
        current_account_balance = pa.return_account_balance()
        response = self.app.get('/policy/' + str(self.policy.id))
        self.assertRegexpMatches(response.data, 'Account balance: \$' + str(current_account_balance))

