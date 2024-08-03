# Standard Library Imports
import os
from datetime import datetime

# Third-Party Imports
from flask import Flask, render_template, redirect, url_for, request, jsonify
from flask_caching import Cache
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from dotenv import load_dotenv

# Local Imports
from models import Bill, Subscription, UserQuery
from utils import generate_answer, fetch_bills, send_email

# Load environment variables
load_dotenv()  

# Initialize Flask app
app = Flask(__name__)
cache = Cache(config={'CACHE_TYPE': 'simple'})
cache.init_app(app)

# Configure the SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///subscriptions.db'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bills.db'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///user_queries.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configure Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')
mail = Mail(app) 

# Initialize the database
db = SQLAlchemy(app)
with app.app_context():
    db.create_all()

# OpenAI key
openai_key = os.getenv("OPENAI_APIKEY")

graph_config = {
   "llm": {
      "api_key": openai_key,
      "model": "gpt-3.5-turbo",
   },
    "verbose": True,
    "headless": True,
}

# Flask Routes
@app.route('/')
def index():
    # Homepage displays the newsletter
    with app.app_context():
        retrieved_bills = Bill.query.limit(5).all()
        current_year = datetime.now().year
        return render_template('index.html', bills=retrieved_bills, current_year=current_year)

@app.route('/subscribe', methods=['POST'])
def subscribe():
    # Subscribe to the newsletter
    email = request.form.get('email')
    if email: 
        # Save the email to the database
        new_subscription = Subscription(email=email)
        db.session.add(new_subscription)
        db.session.commit()

        # Send email with newsletter content
        current_year = datetime.now().year
        send_email(email, current_year)

        # redirect to interact page
        return redirect(url_for('interact'))
    return "Subscription failed", 400

@app.route('/interact_json', methods=['POST'])
def interact_json():
    # Handle JSON interactions
    data = request.get_json()
    user_message = data['message']
    new_query = UserQuery(query_text=user_message)
    db.session.add(new_query)
    db.session.commit()
    print(user_message)
    bot_answer = generate_answer(user_message, "answer")
    print(bot_answer)
    return jsonify(bot_answer)

@app.route('/interact', methods=['GET'])
def interact():
    # Interact route
    with app.app_context():
        retrieved_bills = Bill.query.limit(5).all()
        return render_template('interact.html', bills=retrieved_bills)

if __name__ == '__main__':
    # Initialize database  
    with app.app_context():
        count = Bill.query.count()
        if count == 0:
            fetch_bills()
    
    app.run(debug=True)
