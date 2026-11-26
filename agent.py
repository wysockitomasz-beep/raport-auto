import os
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from google import genai
from google.genai import errors
from playwright.sync_api import sync_playwright

# Lista wyszukiwań (Otomoto do 15 000 PLN + Autoplac + AutoScout24)
SEARCH_URLS = {
    "Otomoto - Toyota": "https://www.otomoto.pl/osobowe/toyota/auris--corolla--yaris?search%5Bfilter_enum_damaged%5D=0&search%5Bfilter_enum_fuel_type%5D%5B0%5D=petrol&search%5Bfilter_enum_fuel_type%5D%5B1%5D=petrol-lpg&search%5Bfilter_enum_gearbox%5D=automatic&search%5Bfilter_float_engine_capacity%3Ato%5D=1600&search%5Bfilter_float_price%3Ato%5D=15000&search%5Bmake_model_generation%5D%5B0%5D=toyota%7Cauris&search%5Bmake_model_generation%5D%5B1%5D=toyota%7Ccorolla&search%5Bmake_model_generation%5D%5B2%5D=toyota%7Cyaris&search%5Badvanced_search_expanded%5D=true",
    "Otomoto - Seat": "https://www.otomoto.pl/osobowe/seat/altea--ibiza--leon--toledo?search%5Bfilter_enum_damaged%5D=0&search%5Bfilter_enum_fuel_type%5D%5B0%5D=petrol&search%5Bfilter_enum_fuel_type%5D%5B1%5D=petrol-lpg&search%5Bfilter_enum_gearbox%5D=automatic&search%5Bfilter_float_engine_capacity%3Afrom%5D=1500&search%5Bfilter_float_engine_capacity%3Ato%5D=1600&search%5Bfilter_float_price%3Ato%5D=15000&search%5Bmake_model_generation%5D%5B0%5D=seat%7Caltea&search%5Bmake_model_generation%5D%5B1%5D=seat%7Cibiza&search%5Bmake_model_generation%5D%5B2%5D=seat%7Cleon&search%5Bmake_model_generation%5D%5B3%5D=seat%7Ctoledo&search%5Badvanced_search_expanded%5D=true",
    "Otomoto - Audi A3": "https://www.otomoto.pl/osobowe/audi/a3-sportback?search%5Bfilter_enum_damaged%5D=0&search%5Bfilter_enum_fuel_type%5D%5B0%5D=petrol&search%5Bfilter_enum_fuel_type%5D%5B1%5D=petrol-lpg&search%5Bfilter_enum_gearbox%5D=automatic&search%5Bfilter_float_engine_capacity%3Afrom%5D=1500&search%5Bfilter_float_engine_capacity%3Ato%5D=1600&search%5Bfilter_float_price%3Ato%5D=15000&search%5Badvanced_search_expanded%5D=true",
    "Otomoto - Honda Jazz": "https://www.otomoto.pl/osobowe/dacia--honda/jogger--sandero--sandero-stepway--jazz?search%5Bfilter_enum_damaged%5D=0&search%5Bfilter_enum_fuel_type%5D%5B0%5D=petrol&search%5Bfilter_enum_fuel_type%5D%5B1%5D=petrol-lpg&search%5Bfilter_enum_gearbox%5D=automatic&search%5Bfilter_float_engine_capacity%3Afrom%5D=1500&search%5Bfilter_float_engine_capacity%3Ato%5D=1600&search%5Bfilter_float_price%3Ato%5D=15000&search%5Bmake_model_generation%5D%5B0%5D=dacia%7Cjogger&search%5Bmake_model_generation%5D%5B1%5D=dacia%7Csandero&search%5Bmake_model_generation%5D%5B2%5D=dacia%7Csandero-stepway&search%5Bmake_model_generation%5D%5B3%5D=honda%7Cjazz&search%5Badvanced_search_expanded%5D=true",
    "Autoplac - rózne": "https://autoplac.pl/oferty/samochody-osobowe/audi/a3/cena-do-15-tysiecy/benzynowe?brandModelIds=45_322,247_2803,501_4929,501_4937,501_4938,501_4942,560&fuelTypes=GASOLINE,LPG&mileageTo=200000&transmissionTypes=AUTOMATIC&doors=5,4&vehicleEquipment=80",
    "Autoplac - 2 seria": "https://autoplac.pl/oferty/samochody-osobowe/honda/jazz/cena-do-15-tysiecy/benzynowe?brandModelIds=247_2803,501_4929,501_4937,501_4938,501_4942,560_5333,560_5339&fuelTypes=GASOLINE,LPG&mileageTo=200000&transmissionTypes=AUTOMATIC&doors=5,4&vehicleEquipment=80",
    "AutoScout24 - Europa": "https://www.autoscout24.pl/lst/ft_benzyna/tr_automatyczna/pr_4000?cat=ma9mo1624%2Cma31mo16490%2Cma64mo18427%2Cma64mo2006%2Cma64mo15869%2Cma64mo2010%2Cma70mo18992%2Cma70mo2052%2Cma70mo15663&eq=30%2C5&cy=D%2CA%2CB%2CE%2CF%2CI%2CL%2CNL&damaged_listing=exclude&desc=0&kmto=200000&powertype=kw&sort=standard&ustate=N%2CU&atype=C&search_id=1r3vijjjkzo&source=detailsearch",
}

SEEN_FILE = "seen.txt"


def get_seen_urls():
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def save_seen_urls(urls):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        for url in urls:
            f.write(url + "\n")


def send_email(subject, html_body):
    sender = os.environ["EMAIL_SENDER"]
    password = os.environ["EMAIL_PASSWORD"]
    receiver = os.environ["EMAIL_RECEIVER"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Agent Samochodowy AI <{sender}>"
    msg["To"] = receiver

    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, receiver, msg.as_string())


def scrape_listings():
    collected_data = []
    all_found_links = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
            locale="pl-PL"
        )
        page = context.new_page()

        for source_name, url in SEARCH_URLS.items():
            try:
                page.goto(url, timeout=45000)
                page.wait_for_timeout(3500)
                page.mouse.wheel(0, 1500)
                page.wait_for_timeout(1500)
