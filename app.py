from flask import Flask, render_template, redirect, url_for, request
from flask_caching import Cache
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from dotenv import load_dotenv
# from scrapegraphai.graphs import SmartScraperGraph
# from scrapegraphai.utils import prettify_exec_info
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from datetime import datetime
import os
import json
from pydantic import BaseModel

import requests
from bs4 import BeautifulSoup
from openai import OpenAI

import pymongo 

# Load environment variables
load_dotenv()  

# Initialize Flask app
app = Flask(__name__)
cache = Cache(config={'CACHE_TYPE': 'simple'})
cache.init_app(app)

# Connect to MongoDB
client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client["mydatabase"]
collection = db["bills"]

# Configure the SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///subscriptions.db'
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
    id = db.Column(db.Integer, primary_key=True)
    # Uncomment this line to make email unique
    # email = db.Column(db.String(120), unique=True, nullable=False)
    email = db.Column(db.String(120), nullable=False)

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

# Initialize fetched bills as global variable 
bills = None

# Fetch bills from the TechPolicy Press website
# @cache.cached(timeout=3600)
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
            # Path to your LOCAL WebDriver executable 
            # CHROMEDRIVER_PATH = "/Users/lsat/.cursor-tutor/projects/feedfounder/feedfounders/bin/chromedriver" 
            # GOOGLE_CHROME_BIN = "/Users/lsat/.cursor-tutor/projects/feedfounder/feedfounders/bin/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
            # service = Service(CHROMEDRIVER_PATH)
            # options = Options()
            # options.headless = True
            # driver = webdriver.Chrome(service=service, options=options)

            # # Uncomment to use Heroku
            # CHROMEDRIVER_PATH = "/app/.chrome-for-testing/chromedriver-linux64/chromedriver" 
            # GOOGLE_CHROME_BIN = "/app/.chrome-for-testing/chrome-linux64/chrome"
            
            # chrome_options.add_argument("--headless") 
            # Adjust window-size to match the size of the screen
            # chrome_options.add_argument("--window-size=1189,813")
            # chrome_options.add_argument('--disable-gpu')
            # chrome_options.add_argument('--no-sandbox')
            # chrome_options.binary_location = GOOGLE_CHROME_BIN
        
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
            # print("Clicking first filter element...")
            click('//*[@id="topics-button"]') 
            # print("First filter element clicked.")
            
            # Debug screenshot if first button is clicked as expected
            driver.get_screenshot_as_file("screenshot1.png")

            # Click the second button - "aritificial intelligence"
            # print("Clicking second filter element...")
            click('//*[@id="topics-menu"]/div[3]/ul/li[3]')  
            # print("Second filter element clicked.")

            # Debug screenshot if second button is clicked as expected
            driver.get_screenshot_as_file("screenshot2.png")

            # Iterate and store a column of urls
            results = []   
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
                    client = OpenAI(
                        api_key=os.environ.get("OPENAI_API_KEY")
                    )

                    completion = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": "You are an expert at summarizing, and identifying key points in text."},
                            {"role": "user", "content": "Summarize this text: ''' {} ''', making sure to capture only the key points and using only 3 sentences.".format(content)}
                        ]
                    )

                    # smart_scraper_graph = SmartScraperGraph(
                    # prompt="Tell me the name, status, last updated, and summary of the bill.",
                    # source=button_url,
                    # config=graph_config
                    # )

                    # print(f"Extracted URL: {button_url}")
                    # results.append(smart_scraper_graph.run())
                    results.append({"name": name, "summary": completion.choices[0].message.content.strip()})

                except TimeoutException:
                    print("Button URL not found. Printing page source for debugging.")
                    print(driver.page_source)
                    driver.quit()
                    raise

            # for url in urls:
            #     print(url)
            # Use ScrapeGraphAI to scrape data from individual urls    
            # results = []   
            # for url in urls:
            #     # print(url)    
            #     smart_scraper_graph = SmartScraperGraph(
            #         prompt="Tell me the name, status, last updated, and summary of the bill.",
            #         source=url,
            #         config=graph_config
            #     )
            #     # print("Running smartscrapergraph")
            #     results.append(smart_scraper_graph.run())

                # execution info
                # graph_exec_info = smart_scraper_graph.get_execution_info()
                # print(prettify_exec_info(graph_exec_info))

                # Debugging: Print the entire response
                # print(json.dumps(result, indent=4))

                # Check if the result contains the expected data
                # if 'name' not in result or 'status' not in result or 'last_updated' not in result or 'summary' not in result:
                #     raise KeyError("One of the expected keys ('name', 'status', 'last_updated', 'summary') was not found in the response.")    
            
                # results.append({
                #     "name": result['name'],
                #     "status": result['status'],
                #     "last_updated": result['last_updated'],
                #     "summary": result['summary']
                # })

        finally:
            # Close the WebDriver
            if driver is not None:
                driver.quit() 
        
        # Process and return the most recent policies
        return results

def store_bills():
    bills = fetch_bills()   
    collection.insert_many(bills)

def send_email(email, bills, current_year):
    with app.app_context():
        newsletter_content = render_template('index.html', bills=bills, current_year=current_year)

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
        if collection.count() == 0:
            store_bills()

        retrieved_bills = list(collection.find())

        current_year = datetime.now().year
        return render_template('index.html', bills=retrieved_bills, current_year=current_year)

# Subscribe to the newsletter
@app.route('/subscribe', methods=['POST'])
def subscribe():
    email = request.form.get('email')
    retrieved_bills = list(collection.find())

    if email: 
        # Save the email to the database
        new_subscription = Subscription(email=email)
        db.session.add(new_subscription)
        db.session.commit()
        print(f"Received subscription request from: {email}")

        # Send email with newsletter content
        current_year = datetime.now().year
        send_email(email, retrieved_bills, current_year)

        # redirect to a thank you page
        return redirect(url_for('thank_you'))
    return "Subscription failed", 400

@app.route('/thank-you')
def thank_you():
    return render_template('thank_you.html')

if __name__ == '__main__':
    # Create the database  
    with app.app_context():
        db.create_all()
    app.run(debug=True)
