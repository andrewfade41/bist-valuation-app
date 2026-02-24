import os
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from dotenv import load_dotenv

# Import our existing modules
from fetch_earnings import fetch_earnings_dates
from data_fetcher import fetch_bist_fundamentals
from calculator import calculate_fair_values

# Load environment variables
load_dotenv()

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SUBSCRIBER_EMAILS = os.getenv("SUBSCRIBER_EMAILS", "")

PREVIOUS_FILE = "is_yatirim_periods.json"

def get_previous_dates():
    if os.path.exists(PREVIOUS_FILE):
        with open(PREVIOUS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_current_dates(dates_dict):
    with open(PREVIOUS_FILE, 'w', encoding='utf-8') as f:
        json.dump(dates_dict, f, indent=4, ensure_ascii=False)

def find_changed_tickers(current_dates, previous_dates):
    changed_tickers = []
    for ticker, current_period in current_dates.items():
        previous_period = previous_dates.get(ticker, "Belirsiz")
        
        # We only care if:
        # 1. It had a previous period but it changed to a new period (e.g. 2023/9 -> 2023/12)
        # 2. It was Belirsiz and now has a valid period.
        if pd.notna(current_period) and str(current_period) != "nan" and str(current_period) != "Belirsiz" and current_period != previous_period:
            changed_tickers.append({
                "Kod": ticker,
                "Eski_Tarih": str(previous_period),
                "Yeni_Tarih": str(current_period)
            })
    return changed_tickers

def format_html_email(df_calc, changed_tickers):
    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333;">
        <h2>BİST Son Bilanço Dönemi Güncellenen Hisseler</h2>
        <p>Bugün itibarıyla {len(changed_tickers)} hissenin İş Yatırım'daki (KAP) <b>Son Bilanço Dönemi</b> değişti veya açıklandı.</p>
        <p>Aşağıda bu hisselere ait güncel adil değer, potansiyel kâr ve teknik verileri bulabilirsiniz:</p>
        
        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%; font-size: 14px;">
          <thead style="background-color: #f2f2f2;">
            <tr>
              <th>Kod</th>
              <th>Sektör</th>
              <th>Yeni Dönem</th>
              <th>(Eski Dönem)</th>
              <th>Fiyat (TL)</th>
              <th>F/K</th>
              <th>PD/DD</th>
              <th>Potansiyel Getiri</th>
              <th>RSI (14)</th>
              <th>MA200 Uzaklık</th>
            </tr>
          </thead>
          <tbody>
    """
    
    # Render table rows
    for item in changed_tickers:
        ticker = item['Kod']
        eski = item['Eski_Tarih']
        yeni = item['Yeni_Tarih']
        
        # Find data for this ticker
        ticker_data = df_calc[df_calc['Kod'] == ticker]
        if not ticker_data.empty:
            row = ticker_data.iloc[0]
            
            # Formatting variables
            price = f"₺{row['Kapanış (TL)']:.2f}" if pd.notna(row['Kapanış (TL)']) else "-"
            fk = f"{row['F/K']:.2f}" if pd.notna(row['F/K']) else "-"
            pddd = f"{row['PD/DD']:.2f}" if pd.notna(row['PD/DD']) else "-"
            
            pot_val = row['Potansiyel Getiri (%)']
            pot_color = "green" if pot_val and pot_val > 0 else "red"
            pot_str = f"<b><span style='color:{pot_color}'>{pot_val:.2f}%</span></b>" if pd.notna(pot_val) else "-"
            
            rsi_val = row['RSI (14)']
            rsi_color = "red" if rsi_val and float(rsi_val) > 70 else ("green" if rsi_val and float(rsi_val) < 30 else "black")
            rsi_str = f"<span style='color:{rsi_color}'>{float(rsi_val):.2f}</span>" if pd.notna(rsi_val) else "-"
            
            ma200_val = row['MA200 Uzaklık (%)']
            ma200_color = "green" if ma200_val and float(ma200_val) < 0 else "red"
            ma200_str = f"<span style='color:{ma200_color}'>{float(ma200_val):.2f}%</span>" if pd.notna(ma200_val) else "-"
            
            html += f"""
            <tr>
              <td><b>{ticker}</b></td>
              <td>{row['Sektör']}</td>
              <td><b>{yeni}</b></td>
              <td style="color: #888;">{eski}</td>
              <td>{price}</td>
              <td>{fk}</td>
              <td>{pddd}</td>
              <td>{pot_str}</td>
              <td>{rsi_str}</td>
              <td>{ma200_str}</td>
            </tr>
            """
    
    html += """
          </tbody>
        </table>
        <br>
        <p style="font-size: 14px; color: #333;">
          <a href="https://bistscanner.streamlit.app/" style="text-decoration: none; color: #0066cc; font-weight: bold;">
            Tüm hisselerin değerleme tablosunu ve güncel durumlarını incelemek için BIST Scanner uygulamasını ziyaret edebilirsiniz.
          </a>
        </p>
        <br>
        <p style="font-size: 12px; color: #777;">Bu e-posta otomatik olarak Bist Valuation Scanner tarafından oluşturulmuştur.</p>
      </body>
    </html>
    """
    return html

def send_email(subject, html_body):
    if not SMTP_EMAIL or not SMTP_PASSWORD or not SUBSCRIBER_EMAILS:
        print("BİLGİ: E-posta gönderimi için .env içindeki SMTP bilgileri eksik. Sadece ekrana yazdırıyorum.")
        print(f"Konu: {subject}")
        return
        
    subscribers = [e.strip() for e in SUBSCRIBER_EMAILS.split(",") if e.strip()]
    
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_EMAIL
    msg["To"] = ", ".join(subscribers)
    
    part = MIMEText(html_body, "html")
    msg.attach(part)
    
    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.sendmail(SMTP_EMAIL, subscribers, msg.as_string())
        server.quit()
        print(f"Başarılı: E-posta {len(subscribers)} kişiye gönderildi.")
    except Exception as e:
        print("E-posta gönderilirken hata oluştu:", e)

def main():
    print("=== Günlük Bilanço Dönemi Tarama & Analiz Başlıyor ===")
    
    import pandas as pd
    import builtins
    builtins.pd = pd
    
    # 1. Fetch current fundamental data from İş Yatırım
    df_raw = fetch_bist_fundamentals()
    if df_raw is None or df_raw.empty:
        print("HATA: İş Yatırım temel veri çekilemedi. İşlem iptal.")
        return
        
    # Extract Kod -> Son Dönem mapping
    current_dates = {}
    for index, row in df_raw.iterrows():
        period = row['Son Dönem']
        current_dates[row['Kod']] = period if pd.notna(period) else "Belirsiz"
        
    # 2. Compare with yesterday's snapshot
    previous_dates = get_previous_dates()
    
    if not previous_dates:
        print("BİLGİ: Daha önce kaydedilmiş bilanço dönemi yok. İlk kurulum aşaması tamamlandı, sistem yarınki değişimleri tarayacak.")
        save_current_dates(current_dates)
        return
        
    changed_tickers = find_changed_tickers(current_dates, previous_dates)
    
    if not changed_tickers:
        print("BİLGİ: İş Yatırım'da yeni açıklanan/değişen bir bilanço dönemi bulunamadı.")
        # Güncelleyip çık
        save_current_dates(current_dates)
        return
        
    print(f"BİLGİ: {len(changed_tickers)} adet hissede yeni bilanço dönemi (Son Dönem) güncellemesi tespit edildi!")
    
    # 3. Calculate fair values to enrich email for changed tickers
    df_calc, _ = calculate_fair_values(df_raw)
    
    # 4. Generate HTML Email Report
    html_report = format_html_email(df_calc, changed_tickers)
    
    date_str = datetime.now().strftime("%d.%m.%Y")
    send_email(f"🔔 BİST Bilanço Dönemi Güncellemesi - {date_str}", html_report)
    
    # 5. Save the snapshot for tomorrow's comparison
    save_current_dates(current_dates)
    print("=== Tarama Başarıyla Tamamlandı ===")

if __name__ == "__main__":
    main()
