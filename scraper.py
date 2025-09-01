import gspread
from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import re
import time

# -----------------------------
# تنظیمات Google Sheets
# -----------------------------
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
client = gspread.authorize(creds)

# اسم شیت رو تغییر بده
sheet = client.open("Product Scraper").sheet1

# -----------------------------
# تابع Scraper
# -----------------------------
def scrape_with_selenium(url, retries=3, wait_time=2):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

    for attempt in range(retries):
        try:
            with webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options) as driver:
                driver.get(url)

                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

                WebDriverWait(driver, 5).until(
                    EC.presence_of_all_elements_located((By.XPATH, "//*[contains(text(),'تومان') or contains(text(),'ریال') or contains(text(),'$') or contains(text(),'€')]"))
                )

                return driver.page_source
        except Exception as e:
            print(f"❌ تلاش {attempt+1} برای {url} شکست خورد: {e}")
            if attempt == retries - 1:
                return None
            time.sleep(wait_time)

# -----------------------------
# استخراج قیمت
# -----------------------------
def extract_prices(html_content):
    if not html_content:
        return []
    soup = BeautifulSoup(html_content, "html.parser")
    price_elements = soup.find_all(string=re.compile(r"\d[\d,]*\s*(تومان|ریال|€|\$)?"))
    return [p.strip() for p in price_elements if p.strip()]

# -----------------------------
# اجرای برنامه
# -----------------------------
def main():
    urls = sheet.col_values(1)[1:]  # لینک‌ها از ستون A
    for i, url in enumerate(urls, start=2):
        html = scrape_with_selenium(url)
        prices = extract_prices(html)

        product_name = "نام پیدا نشد"
        if html:
            soup = BeautifulSoup(html, "html.parser")
            title_tag = soup.find("h1") or soup.find("title")
            if title_tag:
                product_name = title_tag.get_text(strip=True)

        sheet.update_cell(i, 2, product_name)  # ستون B
        sheet.update_cell(i, 3, prices[0] if prices else "❌ پیدا نشد")  # ستون C
        print(f"✅ ردیف {i}: {product_name} - {prices}")

if __name__ == "__main__":
    main()
