import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from google import genai
from playwright.sync_api import sync_playwright

# Lista wyszukiwań (Otomoto do 15 000 PLN + AutoScout24 do 3500 EUR)
SEARCH_URLS = {
    "Otomoto - Toyota (Yaris, Auris, Corolla)": "https://www.otomoto.pl/osobowe/toyota?search%5Bfilter_enum_model%5D%5B0%5D=yaris&search%5Bfilter_enum_model%5D%5B1%5D=auris&search%5Bfilter_enum_model%5D%5B2%5D=corolla&search%5Bfilter_float_price%3Ato%5D=15000&search%5Bfilter_enum_fuel_type%5D=petrol&search%5Bfilter_enum_gearbox%5D=automatic&search%5Bfilter_float_door_count%3Afrom%5D=4&search%5Border%5D=created_at_first%3Adesc",
    "Otomoto - Seat (Altea, Ibiza, Toledo)": "https://www.otomoto.pl/osobowe/seat?search%5Bfilter_enum_model%5D%5B0%5D=altea&search%5Bfilter_enum_model%5D%5B1%5D=ibiza&search%5Bfilter_enum_model%5D%5B2%5D=toledo&search%5Bfilter_float_price%3Ato%5D=15000&search%5Bfilter_enum_fuel_type%5D=petrol&search%5Bfilter_enum_gearbox%5D=automatic&search%5Bfilter_float_door_count%3Afrom%5D=4&search%5Border%5D=created_at_first%3Adesc",
    "Otomoto - Audi A3": "https://www.otomoto.pl/osobowe/audi/a3?search%5Bfilter_float_price%3Ato%5D=15000&search%5Bfilter_enum_fuel_type%5D=petrol&search%5Bfilter_enum_gearbox%5D=automatic&search%5Bfilter_float_door_count%3Afrom%5D=4&search%5Border%5D=created_at_first%3Adesc",
    "Otomoto - Honda Jazz": "https://www.otomoto.pl/osobowe/honda/jazz?search%5Bfilter_float_price%3Ato%5D=15000&search%5Bfilter_enum_fuel_type%5D=petrol&search%5Bfilter_enum_gearbox%5D=automatic&search%5Bfilter_float_door_count%3Afrom%5D=4&search%5Border%5D=created_at_first%3Adesc",
    "AutoScout24 (UE do 3500 EUR)": "https://www.autoscout24.pl/lst?atype=C&cy=D%2CA%2CB%2CNL&damaged_listing=exclude&desc=1&doorfrom=4&fuel=B&gear=A&priceto=3500&sort=age&ustate=N%2CU"
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

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    today = datetime.now().strftime("%d.%m.%Y")
    subject = f"🚗 Raport Aut (Automat / Benzyna / Klima) - {today}"
    send_email(subject, response.text.strip())

    # Zapisz nowe linki jako sprawdzone
    seen_urls.update(new_links)
    save_seen_urls(seen_urls)
    print("Raport wysłany pomyślnie.")

if __name__ == "__main__":
    main()
