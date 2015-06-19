"""
Fetches Contact records for John Doe and Ryan Bucket, to be associated with a
new Policy record.

You're welcome, Mary Sue Client.
"""
john_doe_agent = Contact.query.filter_by(name='John Doe',role='Agent').one()
ryan_bucket_insured = Contact.query.filter_by(name='Ryan Bucket').one()

p4 = Policy('Policy Four', date(2015,2,1), 500)
p4.billing_schedule = 'Two-Pay'
p4.agent = john_doe_agent.id
p4.named_insured = ryan_bucket_insured.id

db.session.add(p4)
db.session.commit()

