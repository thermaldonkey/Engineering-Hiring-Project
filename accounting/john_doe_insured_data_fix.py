"""
Associates John Doe (named insured)'s Contact record with the Policy on which he
is meant to be able to make payments.
"""
john_doe_insured = Contact.query.filter_by(name='John Doe',role='Named Insured').one()
p1 = Policy.query.filter_by(policy_number='Policy One').one()

p1.named_insured = john_doe_insured.id

db.session.add(p1)
db.session.commit()

# And if John Doe would like us to add his payment for him...
pa = PolicyAccounting(p1.id)
pa.make_payment(date_cursor=date(2015,6,18),amount=365)

