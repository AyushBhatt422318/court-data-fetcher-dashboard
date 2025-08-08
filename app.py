# ==============================================================================
#  1. IMPORTS & INITIALIZATION
# ==============================================================================

import os
import time
import json
import uuid
import datetime
from flask import Flask, render_template, request, session
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
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///delhi_high_court.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize the database using SQLAlchemy
db = SQLAlchemy(app)

# Define the path for the local ChromeDriver
CHROME_DRIVER_PATH = os.path.join(os.getcwd(), 'drivers', 'chromedriver.exe')

# Configure the Google Gemini API with a secret key
GEMINI_API_KEY = 'PASTE_YOUR_GEMINI_API_KEY' # IMPRORTANT
genai.configure(api_key=GEMINI_API_KEY)

# A global dictionary to store active Selenium browser sessions between requests
active_drivers = {}

# ==============================================================================
#  3. DATABASE MODEL
# ==============================================================================

# Defines the structure for the 'query_log' table in the database.
# Each search performed by a user will be stored as a record here.
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
# This route handles the main search page. It starts a Selenium browser in the
# background to scrape dynamic data (CAPTCHA, case types) and keeps the
# browser session alive for the user's search submission.
# ------------------------------------------------------------------------------
@app.route('/')
def index():
    # Generate a unique session ID for this user's visit
    session_id = str(uuid.uuid4())
    session['id'] = session_id
    
    # Configure Selenium to run in headless mode (no visible browser window)
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    service = Service(executable_path=CHROME_DRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)

    captcha_text = "Error"
    case_type_options = []
    
    try:
        # Navigate to the court website
        url = "https://delhihighcourt.nic.in/app/get-case-type-status"
        driver.get(url)
        wait = WebDriverWait(driver, 10)

        # Scrape the CAPTCHA text directly from the page
        captcha_element = wait.until(EC.presence_of_element_located((By.ID, "captcha-code")))
        captcha_text = captcha_element.text
        
        # Parse the page to scrape the options from the "Case Type" dropdown menu
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        case_type_select = soup.find('select', {'name': 'case_type'})
        if case_type_select:
            for option in case_type_select.find_all('option'):
                option_text = option.text.strip()
                if option_text and option_text.lower() != 'select':
                    case_type_options.append(option_text)
        
        # Store the live browser instance in the global dictionary, ready for the search
        active_drivers[session_id] = driver
        print(f"Browser session {session_id} started. CAPTCHA: {captcha_text}")

    except Exception as e:
        print(f"An error occurred while fetching CAPTCHA: {e}")
        if driver: driver.quit()

    # Generate a list of years from the current year down to 1951 for the dropdown
    current_year = datetime.datetime.now().year
    year_options = list(range(current_year, 1950, -1))

    # Render the homepage template, passing all the dynamic data to the front-end
    return render_template('index.html', 
                           captcha_text=captcha_text, 
                           session_id=session_id,
                           case_types=case_type_options,
                           years=year_options)

# ------------------------------------------------------------------------------
# ROUTE: /search (Handles form submission)
# ------------------------------------------------------------------------------
# This is the main workhorse function. It receives the user's form data,
# validates the CAPTCHA, logs the query, and then uses the live Selenium
# browser to submit the search and scrape the results in a multi-step process.
# ------------------------------------------------------------------------------
@app.route('/search', methods=['POST'])
def search():
    # Retrieve the user's session ID and the corresponding live browser
    session_id = request.form.get('session_id')
    driver = active_drivers.pop(session_id, None)

    # Handle cases where the session has expired
    if driver is None:
        return render_template('error.html',
                               error_title="Session Expired",
                               error_message="Your session has timed out. Please go back and start a new search.")
    
    try:
        # Retrieve all data from the submitted form
        case_type = request.form.get('case_type')
        case_number = request.form.get('case_number')
        filing_year = request.form.get('filing_year')
        captcha_input = request.form.get('captcha')
        original_captcha = request.form.get('original_captcha')

        # --- Pre-submission Validation ---
        # Compare the user's input with the original CAPTCHA before submitting
        if captcha_input != original_captcha:
            if driver: driver.quit() 
            return render_template('error.html',
                                   error_title="Invalid CAPTCHA",
                                   error_message="The CAPTCHA code you entered did not match the one displayed. Please try again.")
        
        # --- Database Logging ---
        db.session.add(QueryLog(case_type=case_type, case_number=case_number, case_year=filing_year))
        db.session.commit()
        
        # --- Selenium Form Submission ---
        # Use the live browser to fill in each field on the court website
        Select(driver.find_element(By.NAME, "case_type")).select_by_visible_text(case_type)
        driver.find_element(By.NAME, "case_number").send_keys(case_number)
        Select(driver.find_element(By.NAME, "case_year")).select_by_visible_text(filing_year)
        driver.find_element(By.ID, "captchaInput").send_keys(captcha_input)
        
        # Use a JavaScript click for robustness against overlapping elements
        submit_button = driver.find_element(By.ID, "search")
        driver.execute_script("arguments[0].click();", submit_button)
        
        # --- Result Validation ---
        # Wait for the results table to load via AJAX, then check for failure messages
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#caseTable tbody tr")))
        time.sleep(1) # A brief pause to ensure content has rendered
        page_source = driver.page_source
        
        if "No data available in table" in page_source:
            return render_template('error.html',
                                   error_title="Search Failed",
                                   error_message="Your search was submitted successfully, but no records were found for the given case details.")

        # --- Step 1: Parse Main Case Details ---
        soup = BeautifulSoup(page_source, 'html.parser')
        main_table = soup.find('table', id='caseTable')
        first_row_cells = main_table.find('tbody').find('tr').find_all('td')
        
        # All key info is in the second cell of the results table
        second_cell = first_row_cells[1]
        all_links_in_cell = second_cell.find_all('a')
        
        # Find the specific link that leads to the orders page
        order_page_url = None
        for link in all_links_in_cell:
            if 'Orders' in link.text and link.has_attr('href'):
                order_page_url = link['href']
                break

        # Store the scraped case metadata
        case_data = {
            'diary_no': second_cell.text.strip().split('\n')[0],
            'parties': first_row_cells[2].text.strip(),
            'order_page_link': order_page_url
        }

        # --- Step 2: Parse Detailed Order PDFs ---
        # If an "Orders" link was found, navigate to that page to find the PDFs
        order_links = []
        if case_data['order_page_link']:
            driver.get(case_data['order_page_link'])
            time.sleep(2)
            
            order_soup = BeautifulSoup(driver.page_source, 'html.parser')
            all_tables = order_soup.find_all('table')
            
            # Search all tables on the new page to find the one containing PDF links
            for table in all_tables:
                if table.find('tbody'):
                    rows = table.find('tbody').find_all('tr')
                    for row in rows:
                        cells = row.find_all('td')
                        # Identify the correct rows by their structure and link content
                        if len(cells) > 2 and cells[1].find('a') and 'showlogo' in cells[1].find('a')['href']:
                            pdf_link_element = cells[1].find('a')
                            order_date = cells[2].text.strip()
                            order_links.append({
                                'text': pdf_link_element.text.strip(),
                                'url': pdf_link_element['href'],
                                'date': order_date
                            })
        
        # --- Render Success Page ---
        return render_template('results.html', case_data=case_data, order_links=order_links)

    except Exception as e:
        print(f"An error occurred during form submission: {e}")
        return f"<h1>An Error Occurred</h1><p>Could not process the request. Error: {e}</p>"
    finally:
        # Ensure the browser session is always closed to prevent memory leaks
        if driver:
            driver.quit()
            print(f"Browser session {session_id} closed.")

# ------------------------------------------------------------------------------
# ROUTE: /summarize (Handles AI summary generation)
# ------------------------------------------------------------------------------
# This background route is called by JavaScript. It downloads a PDF from a URL,
# extracts its text, and sends it to the Gemini API for summarization.
# ------------------------------------------------------------------------------
@app.route('/summarize', methods=['POST'])
def summarize():
    pdf_url = request.form.get('pdf_url')
    if not pdf_url:
        return "Error: No PDF URL provided.", 400

    try:
        # Download the PDF file's content into memory
        response = requests.get(pdf_url, timeout=15)
        response.raise_for_status()

        # Extract text from the in-memory PDF
        pdf_file = BytesIO(response.content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        pdf_text = ""
        for page in pdf_reader.pages:
            pdf_text += page.extract_text() or ""

        if not pdf_text.strip():
            return "Could not extract text from the PDF.", 500

        # Send the extracted text to the Gemini API with a specific prompt
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"Summarize the key points of the following court judgment in simple terms. Focus on the main argument and the final decision:\n\n{pdf_text}"
        summary_response = model.generate_content(prompt)
        
        # Return the AI's generated summary as plain text
        return summary_response.text

    except requests.exceptions.RequestException as e:
        return f"Error downloading PDF: {e}", 500
    except Exception as e:
        print(f"An error occurred during summarization: {e}")
        return f"An unknown error occurred: {e}", 500

# ==============================================================================
#  5. MAIN EXECUTION BLOCK
# ==============================================================================

# This block runs when the script is executed directly (e.g., `python app.py`)
if __name__ == '__main__':
    # Ensure the database and its tables are created before the app starts
    with app.app_context():
        db.create_all()
    # Run the Flask development server
    # use_reloader=False is important for the single-browser session model to work
    app.run(debug=True, use_reloader=False)