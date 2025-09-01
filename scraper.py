import os
import json
import re
import time
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# --------------------------------------
# Google Sheets Setup
# --------------------------------------
GSHEET_ID = os.getenv("GSHEET_ID")

def get_gspread_client():
    creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(credentials)

def get_ws():
    gc = get_gspread_client()
    sh = gc.open_by_key(GSHEET_ID)
    return sh.sheet1  # اگر چند شیت داری، اینجا تغییر بده

# --------------------------------------
# Selenium Driver Setup
# --------------------------------------
def build_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-gpu")
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )
    return driver

# --------------------------------------
# HTML Fetch + Extraction
# --------------------------------------
def fetch_html(driver, url, retries=2):
    for attempt in range(1, retries + 1):
        try:
            driver.get(url)
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.0)
            return driver.page_source
        except Exception as e:
            if attempt == retries:
                return None
            time.sleep(1.5)

def clean_number(text):
    return re.sub(r"[^\d]", "", text or "")

def extract_title(soup):
    for tag in ["h1", "h2"]:
        el = soup.find(tag)
        if el and el.get_text(strip=True):
            return el.get_text(strip=True)
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        return og["content"].strip()
    tw = soup.find("meta", attrs={"name": "twitter:title"})
    if tw and tw.get("content"):
        return tw["content"].strip()
    return soup.title.get_text(strip=True) if soup.title else "نام پیدا نشد"

def extract_prices_all(soup):
    texts = soup.find_all(string=re.compile(r"\d[\d,\.\s]*"))
    nums = []
    for t in texts:
        s = clean_number(str(t))
        if s and len(s) >= 4:
            nums.append(int(s))
    return sorted(set(nums))

def extract_original_price(soup):
    candidates = []
    selectors = ["del", ".old-price", ".price--original", ".price-original", "[class*='old']", "[class*='strike']"]
    for sel in selectors:
        for el in soup.select(sel):
            val = clean_number(el.get_text())
            if val:
                candidates.append(int(val))
    if candidates:
        return str(max(candidates))
    prices = extract_prices_all(soup)
    return str(max(prices)) if prices else ""

def extract_info(html):
    if not html:
        return ("نام پیدا نشد", "")
    soup = BeautifulSoup(html, "lxml")
    title = extract_title(soup)
    original_price = extract_original_price(soup)
    return (title, original_price)

# --------------------------------------
# Main
# --------------------------------------
def main():
    ws = get_ws()
    rows = ws.get_all_values()
    if not rows:
        return
    urls = [r[0] for r in rows[1:] if len(r) >= 1 and r[0].strip()]
    start_row = 2
    if not urls:
        print("هیچ URLی در ستون A نیست.")
        return
    driver = build_driver()
    batch_values = []
    for url in urls:
        html = fetch_html(driver, url)
        title, price = extract_info(html)
        batch_values.append([title, price])
    driver.quit()
    end_row = start_row + len(batch_values) - 1
    rng = f"B{start_row}:C{end_row}"
    ws.update(rng, batch_values, value_input_option="USER_ENTERED")
    print(f"✅ به‌روزرسانی شد: {rng}")

if __name__ == "__main__":
    main()
