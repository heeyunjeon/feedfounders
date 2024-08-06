# Standard Library Imports
import os
from datetime import datetime

# Third-Party Imports
from flask import Flask, render_template, redirect, url_for, request, jsonify
from flask_mail import Mail, Message
from dotenv import load_dotenv

# Local Imports
from utils import *
from models import db, init_app

# Load environment variables
load_dotenv()  

# Initialize Flask app
app = Flask(__name__)

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

init_app(app)

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
        retrieved_bills = get_bills()
        current_year = datetime.now().year
        return render_template('index.html', bills=retrieved_bills, current_year=current_year)

@app.route('/subscribe', methods=['POST'])
def subscribe():
    # Subscribe to the newsletter
    email = request.form.get('email')
    if email: 
        save_email(email, db)
        # Send email with newsletter content
        current_year = datetime.now().year
        with app.app_context():
            content = generate_email(current_year)

            msg = Message('Thank you for subscribing! Here are the latest ai regulations:', 
                            recipients=[email],
                            sender=app.config['MAIL_DEFAULT_SENDER'])
            msg.html = content

            # Send the email
            mail.send(msg)

        # redirect to interact page
        return redirect(url_for('interact'))
    return "Subscription failed", 400

@app.route('/interact_json', methods=['POST'])
def interact_json():
    # Handle JSON interactions
    data = request.get_json()
    user_message = data['message']

    # add to user_query 
    save_usermsg(user_message, db)

    # generate answer
    bot_answer = generate_answer(user_message, "answer")

    return jsonify(bot_answer)

@app.route('/interact', methods=['GET'])
def interact():
    # Interact route
    with app.app_context():
        retrieved_bills = get_bills()
        return render_template('interact.html', bills=retrieved_bills)

if __name__ == '__main__':
    # Initialize database  
    with app.app_context():
        count = count_bills()
        if count == 0:
            fetch_bills(db)
    
    app.run(debug=True)
