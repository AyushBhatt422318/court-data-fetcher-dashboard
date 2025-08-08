# ==============================================================================
#  app2.py - Fully Automated Captcha Handling
# ==============================================================================

# ==============================================================================
#  1. IMPORTS & INITIALIZATION
# ==============================================================================

import os
import time
import json
import uuid
import datetime
from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import google.generativeai as genai
import requests
import PyPDF2
from io import BytesIO

# ==============================================================================
#  2. FLASK APP & DATABASE CONFIGURATION
# ==============================================================================

# Initialize the Flask application
app = Flask(__name__)

# Configure application settings
app.config['SECRET_KEY'] = 'a_very_secret_key_that_should_be_changed'
# Use a separate database file for this automated version of the app
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///delhi_high_court_v2.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize the database using SQLAlchemy
db = SQLAlchemy(app)

# Define the path for the local ChromeDriver
CHROME_DRIVER_PATH = os.path.join(os.getcwd(), 'drivers', 'chromedriver.exe')

# Configure the Google Gemini API with a secret key
GEMINI_API_KEY = 'PASTE_YOUR_GEMINI_API_KEY' #IMORTANT
genai.configure(api_key=GEMINI_API_KEY)

# ==============================================================================
#  3. DATABASE MODEL
# ==============================================================================

# Defines the structure for the 'query_log' table in the database.
class QueryLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    case_type = db.Column(db.String(50), nullable=False)
    case_number = db.Column(db.String(50), nullable=False)
    case_year = db.Column(db.String(10), nullable=False)
    timestamp = db.Column(db.DateTime, server_default=db.func.now())

# ==============================================================================
#  4. FLASK ROUTES
# ==============================================================================

# ------------------------------------------------------------------------------
# ROUTE: / (Homepage)
# ------------------------------------------------------------------------------
# This route prepares the main search page. It's simplified for this version,
# as it only needs to scrape the available Case Types for the dropdown menu.
# ------------------------------------------------------------------------------
@app.route('/')
def index():
    # Configure and start a temporary headless browser
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    service = Service(executable_path=CHROME_DRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)
    
    case_type_options = []
    try:
        # Scrape the "Case Type" options from the court website
        url = "https://delhihighcourt.nic.in/app/get-case-type-status"
        driver.get(url)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        case_type_select = soup.find('select', {'name': 'case_type'})
        if case_type_select:
            for option in case_type_select.find_all('option'):
                option_text = option.text.strip()
                if option_text and option_text.lower() != 'select':
                    case_type_options.append(option_text)
    except Exception as e:
        print(f"An error occurred while fetching case types: {e}")
    finally:
        # The temporary browser is no longer needed
        if driver: driver.quit()

    # Generate the list of years for the year dropdown
    current_year = datetime.datetime.now().year
    year_options = list(range(current_year, 1950, -1))
    
    # Render the simplified v2 homepage
    return render_template('index_v2.html', 
                           case_types=case_type_options,
                           years=year_options)

# ------------------------------------------------------------------------------
# ROUTE: /search (Handles form submission)
# ------------------------------------------------------------------------------
# This is the fully automated core of the application. It receives the user's
# search query, then starts its own browser session to read the CAPTCHA,
# fill it in, and perform the entire multi-step scraping process.
# ------------------------------------------------------------------------------
@app.route('/search', methods=['POST'])
def search():
    # Retrieve user's search criteria from the form
    case_type = request.form.get('case_type')
    case_number = request.form.get('case_number')
    filing_year = request.form.get('filing_year')

    # Start a new headless browser for this entire automated operation
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    service = Service(executable_path=CHROME_DRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)

    try:
        # Log the user's search query to the database
        db.session.add(QueryLog(case_type=case_type, case_number=case_number, case_year=filing_year))
        db.session.commit()
        
        # --- Step 1: Auto-Read the CAPTCHA ---
        url = "https://delhihighcourt.nic.in/app/get-case-type-status"
        driver.get(url)
        wait = WebDriverWait(driver, 10)
        captcha_element = wait.until(EC.presence_of_element_located((By.ID, "captcha-code")))
        captcha_solution = captcha_element.text
        print(f"Auto-solved CAPTCHA: {captcha_solution}")

        # --- Step 2: Auto-Fill the Form ---
        # The script fills in all fields, including the CAPTCHA it just read
        Select(driver.find_element(By.NAME, "case_type")).select_by_visible_text(case_type)
        driver.find_element(By.NAME, "case_number").send_keys(case_number)
        Select(driver.find_element(By.NAME, "case_year")).select_by_visible_text(filing_year)
        driver.find_element(By.ID, "captchaInput").send_keys(captcha_solution)
        submit_button = driver.find_element(By.ID, "search")
        driver.execute_script("arguments[0].click();", submit_button)
        
        # --- Step 3: Validate the Result ---
        # Wait for the results table to load and check for the "no data" message
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#caseTable tbody tr")))
        time.sleep(1)
        page_source = driver.page_source
        if "No data available in table" in page_source:
            return render_template('error.html',
                                   error_title="Search Failed",
                                   error_message="Your search was submitted successfully, but no records were found for the given case details.")

        # --- Step 4: Parse the Results (Multi-step) ---
        soup = BeautifulSoup(page_source, 'html.parser')
        main_table = soup.find('table', id='caseTable')
        first_row_cells = main_table.find('tbody').find('tr').find_all('td')
        second_cell = first_row_cells[1]
        all_links_in_cell = second_cell.find_all('a')
        order_page_url = None
        for link in all_links_in_cell:
            if 'Orders' in link.text and link.has_attr('href'):
                order_page_url = link['href']
                break
        case_data = {
            'diary_no': second_cell.text.strip().split('\n')[0],
            'parties': first_row_cells[2].text.strip(),
            'order_page_link': order_page_url
        }
        
        # If an orders page exists, navigate to it and scrape the PDF links
        order_links = []
        if case_data['order_page_link']:
            driver.get(case_data['order_page_link'])
            time.sleep(2)
            order_soup = BeautifulSoup(driver.page_source, 'html.parser')
            all_tables = order_soup.find_all('table')
            for table in all_tables:
                if table.find('tbody'):
                    rows = table.find('tbody').find_all('tr')
                    for row in rows:
                        cells = row.find_all('td')
                        if len(cells) > 2 and cells[1].find('a') and 'showlogo' in cells[1].find('a')['href']:
                            pdf_link_element = cells[1].find('a')
                            order_date = cells[2].text.strip()
                            order_links.append({'text': pdf_link_element.text.strip(),'url': pdf_link_element['href'],'date': order_date})
        
        # Render the final results page with all scraped data
        return render_template('results.html', case_data=case_data, order_links=order_links)

    except Exception as e:
        print(f"An error occurred during form submission: {e}")
        return render_template('error.html',
                               error_title="An Application Error Occurred",
                               error_message=f"Could not process the request. Error: {e}")
    finally:
        # Ensure the browser is always closed after the operation
        if driver:
            driver.quit()

# ------------------------------------------------------------------------------
# ROUTE: /summarize (Handles AI summary generation)
# ------------------------------------------------------------------------------
# This background route is called by JavaScript from the results page.
# ------------------------------------------------------------------------------
@app.route('/summarize', methods=['POST'])
def summarize():
    pdf_url = request.form.get('pdf_url')
    if not pdf_url: return "Error: No PDF URL provided.", 400
    try:
        response = requests.get(pdf_url, timeout=15)
        response.raise_for_status()
        pdf_file = BytesIO(response.content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        pdf_text = "".join(page.extract_text() or "" for page in pdf_reader.pages)
        if not pdf_text.strip(): return "Could not extract text from the PDF.", 500
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"Summarize the key points of the following court judgment in simple terms. Focus on the main argument and the final decision:\n\n{pdf_text}"
        summary_response = model.generate_content(prompt)
        return summary_response.text
    except Exception as e:
        print(f"An error occurred during summarization: {e}")
        return f"An unknown error occurred: {e}", 500

# ==============================================================================
#  5. MAIN EXECUTION BLOCK
# ==============================================================================

if __name__ == '__main__':
    # Ensure the database and its tables are created before the app starts
    with app.app_context():
        db.create_all()
    # Run the Flask development server
    app.run(debug=True, use_reloader=False)