from models import Bill, Subscription, UserQuery
# generate_answer
from openai import OpenAI
import os 

# fetch_bills 
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
import requests
from bs4 import BeautifulSoup

# send_email
from flask import render_template


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

def fetch_bills(db):
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
            
        click('//*[@id="topics-button"]') 
        click('//*[@id="topics-menu"]/div[3]/ul/li[3]')  
    
        for i in range(1,6):
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
            
                # Summarize using GPT-4o
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

def get_bills():
    return Bill.query.limit(5).all()

def count_bills():
    return Bill.query.count()

def save_email(email, db):
    new_subscription = Subscription(email=email)
    db.session.add(new_subscription)
    db.session.commit()

def generate_email(current_year):
    # Get the bills from the database
    retrieved_bills = Bill.query.limit(5).all()
    content = render_template('email.html', bills=retrieved_bills, current_year=current_year)

    return content

def save_usermsg(user_message, db):
    new_query = UserQuery(query_text=user_message)
    db.session.add(new_query)
    db.session.commit()

