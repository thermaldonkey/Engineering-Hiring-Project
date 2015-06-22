#You will need to pip install flask and the sqlalchemy extension for flask.
from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy

from jinja_filters import format_date

# Initialize the application.
app = Flask(__name__)
app.secret_key = '\x8a\xe4\xb2*\xb2\x07k.\xf1\xec\xc6m\xcf\xc5\x02Q\x02_S\xf4\x88\x94\x80\r?\x0c\xe6\xb9\xbe\xaei\xed\xfa\xf21\x89\xafx\xd8\xad\x8b\xdf\xac)\xa5\xc5\xe7\xc6\xc8\x97'
app.config.from_pyfile('config.py')
db = SQLAlchemy(app)

app.jinja_env.filters['date'] = format_date

# Import the views file for routing.
import views
