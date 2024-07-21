from flask import Flask, render_template, redirect, url_for, request, jsonify
from flask_caching import Cache
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from dotenv import load_dotenv

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from datetime import datetime
import os
import json
import requests
from bs4 import BeautifulSoup
from openai import OpenAI

# Load environment variables
load_dotenv()  

# Initialize Flask app
app = Flask(__name__)
cache = Cache(config={'CACHE_TYPE': 'simple'})
cache.init_app(app)

# Configure the SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///subscriptions.db'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bills.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configure Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

# Initialize the database
db = SQLAlchemy(app)
mail = Mail(app)

# Define a model for storing email addresses
class Subscription(db.Model):
    __tablename__ = 'subscriptions'
    id = db.Column(db.Integer, primary_key=True)
    # Uncomment this line to make email unique
    email = db.Column(db.String(120), unique=True, nullable=False)
    

class Bill(db.Model):
    __tablename__ = 'bills'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    summary = db.Column(db.Text, nullable=False)

    def __repr__(self):
        return f"Bill(id={self.id}, name={self.name}, summary={self.summary})"

# OpenAI key for ScrapeGraphAI
openai_key = os.getenv("OPENAI_APIKEY")

graph_config = {
   "llm": {
      "api_key": openai_key,
      "model": "gpt-3.5-turbo",
   },
    "verbose": True,
    "headless": True,
}

def generate_answer(query, mode):
    client = OpenAI(
        api_key=os.environ.get("OPENAI_API_KEY")
    )

    if mode == "summarize":
        completion = client.chat.completions.create(
            model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are an expert at summarizing, and identifying key points in text."},
            {"role": "user", "content": "Summarize this text: ''' {} ''', making sure to capture only the key points and using only 3 sentences.".format(query)}
        ]
    )
    
    else: 
        retrieved_bills = Bill.query.limit(5).all()
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You have a JD degrree from Yale law school and a PhD in Computer Science from MIT, and you are tasked with answering a question about the following bills: {}. What is the question? Answer the question based on the bill summaries.".format(retrieved_bills)},
                {"role": "user", "content": "Answer the question based on the bill summaries: {}".format(query)}
            ]
        )

    return completion.choices[0].message.content.strip()

# Fetch bills from the TechPolicy Press website
def fetch_bills():
    with app.app_context():
        driver = None
        try:
            chrome_options = webdriver.ChromeOptions()
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1189,813")
            driver = webdriver.Chrome(options=chrome_options)
        
            # Open the URL
            url = "https://techpolicy.press/tracker/"
            driver.get(url)

            # Function to click an element with retry on StaleElementReferenceException
            def click(xpath):
                try:
                    element = WebDriverWait(driver, 2).until(
                        EC.element_to_be_clickable((By.XPATH, xpath))  
                    ) 
                    driver.execute_script("arguments[0].scrollIntoView(true);", element)
                    element.click()
                    return element
                except StaleElementReferenceException:
                    print(f"StaleElementReferenceException: {xpath}")
                except TimeoutException:
                    print(f"TimeoutException: {xpath}")
                    print(driver.page_source)
                    driver.quit()
                    raise
                
            # Click the first button - "topics" 
            click('//*[@id="topics-button"]') 
            
            # Debug screenshot if first button is clicked as expected
            # driver.get_screenshot_as_file("screenshot1.png")

            # Click the second button - "aritificial intelligence"
            # print("Clicking second filter element...")
            click('//*[@id="topics-menu"]/div[3]/ul/li[3]')  
            # print("Second filter element clicked.")

            # Debug screenshot if second button is clicked as expected
            # driver.get_screenshot_as_file("screenshot2.png")

            # Iterate and store a column of urls
            # results = []   
            for i in range(1,6):
                # print(f"Storing the URLs: iteration {i}...")
                # Extract the URL from the button

                try:
                    button_element = WebDriverWait(driver, 2).until(
                        EC.presence_of_element_located((By.XPATH, f'//*[@id="main"]/div/div/section/div[3]/div[1]/table/tbody/tr[{i}]/td[1]/div/a'))
                    )
                    button_url = button_element.get_attribute('href') 

                    #  Use BeautifulSoup
                    response = requests.get(button_url)
                    soup = BeautifulSoup(response.text, 'html.parser')
                    content = soup.get_text().replace("\n", "")
                    fullname = soup.title.string
                    name = fullname.split("|")[0].strip()
                
                    # Summarize
                    summary = generate_answer(content, "summarize")

                    bill = Bill(name=name, summary=summary)
                    db.session.add(bill)
                    
                except TimeoutException:
                    print("Button URL not found. Printing page source for debugging.")
                    print(driver.page_source)
                    driver.quit()
                    raise

        finally:
            # Close the WebDriver
            if driver is not None:
                driver.quit() 
        
        # Process and return the most recent policies
        db.session.commit()


def send_email(email, current_year):
    with app.app_context():
        # Get the bills from the database
        retrieved_bills = Bill.query.limit(5).all()
        newsletter_content = render_template('index.html', bills=retrieved_bills, current_year=current_year)

    # Create the email message
    msg = Message('Thank you for subscribing!', 
                    recipients=[email],
                    sender=app.config['MAIL_DEFAULT_SENDER'])
    msg.html = newsletter_content

    # Send the email
    mail.send(msg)

###############FLASK##############
# Homepage displays the newsletter
@app.route('/')
def index():
    with app.app_context():
        retrieved_bills = Bill.query.limit(5).all()

        current_year = datetime.now().year
        return render_template('index.html', bills=retrieved_bills, current_year=current_year)

# Subscribe to the newsletter
@app.route('/subscribe', methods=['POST'])
def subscribe():
    email = request.form.get('email')

    if email: 
        # Save the email to the database
        new_subscription = Subscription(email=email)
        db.session.add(new_subscription)
        db.session.commit()
        print(f"Received subscription request from: {email}")

        # Send email with newsletter content
        current_year = datetime.now().year
        send_email(email, current_year)

        # redirect to interact page
        return redirect(url_for('interact'))
    return "Subscription failed", 400

@app.route('/interact_json', methods=['POST'])
def interact_json():
    data = request.get_json()
    user_message = data['message']
    print(user_message)
    bot_answer = generate_answer(user_message, "answer")
    print(bot_answer)
    
    return jsonify(bot_answer)

@app.route('/interact', methods=['GET'])
def interact():
    with app.app_context():
        retrieved_bills = Bill.query.limit(5).all()

        return render_template('interact.html', bills=retrieved_bills)


if __name__ == '__main__':
    # Create the database  
    with app.app_context():
        count = Bill.query.count()
        if count == 0:
            fetch_bills()
    
    app.run(debug=True)
