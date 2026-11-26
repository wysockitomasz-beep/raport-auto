import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from google import genai
from playwright.sync_api import sync_playwright

# Lista wyszukiwań (Otomoto do 15 000 PLN + AutoScout24 do 3500 EUR)
SEARCH_URLS = {
    "Otomoto - Toyota": "https://www.otomoto.pl/osobowe/toyota/auris--corolla--yaris?search%5Bfilter_enum_damaged%5D=0&search%5Bfilter_enum_fuel_type%5D%5B0%5D=petrol&search%5Bfilter_enum_fuel_type%5D%5B1%5D=petrol-lpg&search%5Bfilter_enum_gearbox%5D=automatic&search%5Bfilter_float_engine_capacity%3Ato%5D=1600&search%5Bfilter_float_price%3Ato%5D=15000&search%5Bmake_model_generation%5D%5B0%5D=toyota%7Cauris&search%5Bmake_model_generation%5D%5B1%5D=toyota%7Ccorolla&search%5Bmake_model_generation%5D%5B2%5D=toyota%7Cyaris&search%5Badvanced_search_expanded%5D=true",
    "Otomoto - Seat": "https://www.otomoto.pl/osobowe/audi/a3-sportback?search%5Bfilter_enum_damaged%5D=0&search%5Bfilter_enum_fuel_type%5D%5B0%5D=petrol&search%5Bfilter_enum_fuel_type%5D%5B1%5D=petrol-lpg&search%5Bfilter_enum_gearbox%5D=automatic&search%5Bfilter_float_engine_capacity%3Afrom%5D=1500&search%5Bfilter_float_engine_capacity%3Ato%5D=1600&search%5Bfilter_float_price%3Ato%5D=15000&search%5Badvanced_search_expanded%5D=true",
    "Otomoto - Audi A3": "https://www.otomoto.pl/osobowe/audi/a3-sportback?search%5Bfilter_enum_damaged%5D=0&search%5Bfilter_enum_fuel_type%5D%5B0%5D=petrol&search%5Bfilter_enum_fuel_type%5D%5B1%5D=petrol-lpg&search%5Bfilter_enum_gearbox%5D=automatic&search%5Bfilter_float_engine_capacity%3Afrom%5D=1500&search%5Bfilter_float_engine_capacity%3Ato%5D=1600&search%5Bfilter_float_price%3Ato%5D=15000&search%5Badvanced_search_expanded%5D=true",
    "Otomoto - Honda Jazz": "https://www.otomoto.pl/osobowe/audi/a3-sportback?search%5Bfilter_enum_damaged%5D=0&search%5Bfilter_enum_fuel_type%5D%5B0%5D=petrol&search%5Bfilter_enum_fuel_type%5D%5B1%5D=petrol-lpg&search%5Bfilter_enum_gearbox%5D=automatic&search%5Bfilter_float_engine_capacity%3Afrom%5D=1500&search%5Bfilter_float_engine_capacity%3Ato%5D=1600&search%5Bfilter_float_price%3Ato%5D=15000&search%5Badvanced_search_expanded%5D=true",
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
                
                # Wyciąganie linków do ofert
                links = page.eval_on_selector_all(
                    "a[href*='/oferta/'], a[href*='/oferty/']",
                    "els => els.map(e => e.href.split('#')[0])"
                )
                all_found_links.update(links)
                
                text = page.inner_text("main")
                collected_data.append(f"=== ŹRÓDŁO: {source_name} ===\nLINKI:\n" + "\n".join(set(links[:15])) + f"\nTREŚĆ STRONY:\n{text[:7000]}")
            except Exception as e:
                print(f"Błąd pobierania {source_name}: {e}")

        browser.close()
    return all_found_links, "\n\n".join(collected_data)

def main():
    seen_urls = get_seen_urls()
    found_links, raw_content = scrape_listings()
    
    new_links = [link for link in found_links if link not in seen_urls]
    
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    prompt = f"""
    Jesteś doradcą motoryzacyjnym. Przygotuj przejrzysty, codzienny raport w formacie HTML (bez znaczników ```html, sam czysty kod HTML do wklejenia w treść maila).
    
    KRYTERIA UŻYTKOWNIKA:
    - Budżet: max 15 000 PLN lub 3500 EUR
    - Skrzynia: WYŁĄCZNIE automatyczna
    - Paliwo: Benzyna (lub benzyna+LPG)
    - Nadwozie: 4 lub 5 drzwi, OBOWIĄZKOWO klimatyzacja
    - Dopuszczalne modele: Toyota (Yaris, Auris, Corolla), Seat (Altea, Ibiza, Toledo), Audi A3, Honda Jazz.

    ZADANIE:
    1. Przeanalizuj zebrane ogłoszenia. Skup się szczególnie na nowych linkach: {list(new_links)[:20]}.
    2. Odrzuć auta uszkodzone, bez klimatyzacji, 3-drzwiowe, diesle oraz inne modele niż wymienione.
    3. Dla każdego sensownego ogłoszenia wypisz:
       - Model, rocznik, silnik, przebieg i cenę
       - Krótką ocenę techniczną (uwaga: ostrzeż jeśli w Toyocie to zautomatyzowana skrzynia MMT zamiast klasycznego automatu, w Hondzie Jazz sprawdź czy to CVT, a w Audi/Seacie zwróć uwagę na stan skrzyni Tiptronic/DSG)
       - Klikalny link <a href="...">Zobacz ogłoszenie</a>
    4. Jeśli w nowych linkach nie ma nic ciekawego, napisz krótko, że dzisiaj brak nowych perełek spełniających wszystkie kryteria, i podsumuj 2-3 najciekawsze aktywne oferty z listy.

    DANE Z PORTALI:
    {raw_content[:28000]}
    """

import time
from google.genai import errors

# 1. Pobierz listę modeli dostępnych dla Twojego klucza API
available_models = []
try:
    for m in client.models.list():
        name = m.name.replace("models/", "")
        if "flash" in name and "embedding" not in name and "image" not in name and "tts" not in name:
            available_models.append(name)
except Exception as e:
    print(f"Nie udało się pobrać listy modeli: {e}")

# Preferowane modele na początku (z fallbackiem na resztę znalezionych flash)
candidate_models = []
for preferred in ["gemini-3.8-flash", "gemini-2.5-flash", "gemini-2.0-flash"]:
    if preferred in available_models:
        candidate_models.append(preferred)
for m in available_models:
    if m not in candidate_models:
        candidate_models.append(m)

if not candidate_models:
    candidate_models = ["gemini-3.8-flash"]

print("Kandydaci modeli:", candidate_models[:5])

# 2. Próbuj po kolei aż do uzyskania odpowiedzi
response = None
for model_name in candidate_models[:5]:
    for attempt in range(2):
        try:
            print(f"Próbuję modelu: {model_name} (próba {attempt + 1})...")
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            break
        except errors.ClientError as e:
            print(f"Błąd klienta dla {model_name}: {e}")
            break
        except errors.ServerError as e:
            print(f"Błąd serwera (503) dla {model_name}: {e}")
            if attempt == 0:
                time.sleep(10)
    if response is not None:
        break

if response is None:
    raise RuntimeError("Żaden z dostępnych modeli nie odpowiedział poprawnie.")

    today = datetime.now().strftime("%d.%m.%Y")
    subject = f"🚗 Raport Aut (Automat / Benzyna / Klima) - {today}"
    send_email(subject, response.text.strip())

    # Zapisz nowe linki jako sprawdzone
    seen_urls.update(new_links)
    save_seen_urls(seen_urls)
    print("Raport wysłany pomyślnie.")

if __name__ == "__main__":
    main()
