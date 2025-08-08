# Court Data Fetcher & Mini-Dashboard

![Python Version](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python)
![Framework](https://img.shields.io/badge/Framework-Flask-black?logo=flask)

A sophisticated web application built with Python and Flask that fetches case metadata and the latest orders from the Delhi High Court. The application features a modern UI, a powerful AI summarization tool, and two distinct versions: a user-assisted model and a fully automated model that handles the CAPTCHA seamlessly.

---

### You can watch the full demo video here.
https://youtu.be/1duWCNFGJcQ

---

### Key Features

*   **🤖 AI-Powered Summaries:** Utilizes the Google Gemini API to download and read the latest judgment PDF, providing a concise and easy-to-understand summary of its key points.
*   **⚙️ Dual Automation Modes:**
    *   **User-Assisted (`app.py`):** A robust version where the user manually enters the CAPTCHA, ensuring high reliability.
    *   **Fully Automated (`app2.py`):** A streamlined version that automatically reads and solves the text-based CAPTCHA on the user's behalf.
*   **🌐 Dynamic UI:** The interface automatically scrapes and populates the "Case Type" dropdown with all available options from the court website and generates a list of years from 1951 to the present, minimizing user error.
*   **📄 Two-Step Scraping:** Intelligently navigates from the main case results page to the detailed "Orders" page to find and list all associated PDF links and their dates.
*   **🗄️ Database Logging:** Logs every user search query to a persistent SQLite database for tracking and analytics.

---

### Tech Stack

*   **Backend:** Python, Flask
*   **Database:** SQLite with SQLAlchemy
*   **Web Scraping:** Selenium, BeautifulSoup4
*   **AI:** Google Gemini API
*   **PDF Handling:** PyPDF2, Requests
*   **Frontend:** HTML5, CSS3, JavaScript

---

### Court Chosen & CAPTCHA Strategy

#### Court Chosen
*   **Delhi High Court** (`delhihighcourt.nic.in`) was selected for this project. Its modern web structure and text-based CAPTCHA provided an excellent opportunity to implement and demonstrate both a user-assisted and a fully automated scraping solution.

#### CAPTCHA Strategy
This project successfully implements two distinct and robust strategies for handling the website's CAPTCHA:

1.  **Method 1: User-Assisted (`app.py`)**
    This version focuses on reliability and transparency. The backend Selenium process starts a browser, reads the text of the CAPTCHA, and displays it on the application's UI. The user is then required to manually type this code into the form. This approach is highly resilient to changes and mimics a collaborative user-bot interaction.

2.  **Method 2: Fully Automated (`app2.py`)**
    This version provides a seamless, "zero-touch" user experience. Upon form submission, the backend script initiates its own browser session, navigates to the court website, programmatically reads the CAPTCHA text, and automatically fills it into the submission form along with the user's case details. This entire process is invisible to the user, who simply clicks "Search" and receives the results.

---

### Setup and Installation

Follow these steps to run the project locally.

#### 1. Clone the Repository
```bash
git clone https://github.com/your-username/your-repository-name.git
cd your-repository-name
```

#### 2. Create and Activate a Virtual Environment
```bash
# For Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# For macOS/Linux
python3 -m venv .venv
source .venv/bin/activate
```

#### 3. Install Required Packages
All dependencies are listed in `requirements.txt`. Install them with:
```bash
pip install -r requirements.txt
```

#### 4. Download the ChromeDriver
*   Check your Google Chrome browser version (go to `chrome://settings/help`).
*   Download the matching `chromedriver.exe` from the **[Chrome for Testing availability dashboard](https://googlechromelabs.github.io/chrome-for-testing/)**.
*   Place the downloaded `chromedriver.exe` file inside the `drivers` folder in the project directory.

#### 5. Set Up the API Key
*   Open `app.py` or `app2.py`.
*   Find the line `GEMINI_API_KEY = 'PASTE_YOUR_GEMINI_API_KEY'`
*   Replace `PASTE_YOUR_GEMINI_API_KEY` with your actual API key from Google AI Studio.

---

### How to Run the Application

You can run either of the two application versions.

**To run the User-Assisted version:**
```bash
python app.py
```

**To run the Fully Automated version:**
```bash
python app2.py
```

After running the command, open your web browser and navigate to **`http://127.0.0.1:5000`**.


