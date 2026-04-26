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
from technical_analysis import detect_bullish_divergence, detect_bearish_divergence
from sentiment_analyzer import fetch_stock_news, get_overall_sentiment
from constants import PERIODS_SNAPSHOT_FILENAME
import yfinance as yf

# Load environment variables
load_dotenv()

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SUBSCRIBER_EMAILS = os.getenv("SUBSCRIBER_EMAILS", "")
PORTFOLIO_TICKERS = os.getenv("PORTFOLIO_TICKERS", "")

PREVIOUS_FILE = PERIODS_SNAPSHOT_FILENAME

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

def get_portfolio_sentiment(portfolio_str):
    if not portfolio_str:
        return []
    
    tickers = [t.strip() for t in portfolio_str.split(",") if t.strip()]
    results = []
    
    print(f"BİLGİ: {len(tickers)} adet portföy hissesi için duyarlılık analizi başlatılıyor...")
    for ticker in tickers:
        try:
            # For email, we use a smaller limit to save time/bandwidth
            news = fetch_stock_news(ticker, limit=5)
            score, summary, _ = get_overall_sentiment(news)
            results.append({
                "Kod": ticker,
                "Skor": score,
                "Özet": summary,
                "Adet": len(news)
            })
        except Exception as e:
            print(f"HATA: {ticker} sentiment analizi başarısız: {e}")
            
    return results

def get_discovery_highlights(candidates, rsi_df, div_signals):
    """
    Analyzes sentiment for stocks that triggered technical signals.
    Returns highlights where sentiment is bullish.
    """
    if not candidates:
        return []
        
    highlights = []
    print(f"BİLGİ: {len(candidates)} keşif adayı için duyarlılık analizi başlatılıyor...")
    
    for ticker in candidates:
        try:
            news = fetch_stock_news(ticker, limit=5)
            score, summary, css_class = get_overall_sentiment(news)
            
            # Only highlight if sentiment is bullish (> 60)
            if score > 60:
                # Find why it's a candidate
                reasons = []
                if any(s['Kod'] == ticker for s in div_signals):
                    reasons.append("Pozitif Uyumsuzluk")
                if not rsi_df[rsi_df['Kod'] == ticker].empty:
                    reasons.append("RSI Aşırı Satım")
                    
                highlights.append({
                    "Kod": ticker,
                    "Skor": score,
                    "Özet": summary,
                    "Neden": " + ".join(reasons) if reasons else "Yüksek Potansiyel"
                })
        except Exception:
            pass
            
    return highlights

def format_html_email(df_calc, changed_tickers, rsi_alerts_df=None, divergence_signals=None, bearish_signals=None, portfolio_sentiment=None, discovery_highlights=None):
    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333;">
    """
    
    if discovery_highlights:
        html += f"""
        <div style="background-color: #f0fdf4; border: 2px solid #22c55e; border-radius: 12px; padding: 20px; margin-bottom: 25px;">
          <h2 style="color: #166534; margin-top: 0;">🎯 Günün Keşif Sinyalleri</h2>
          <p style="color: #166534;">Hem <b>teknik göstergeleri</b> hem de <b>haber akışı (sentiment)</b> pozitif olan, günün öne çıkan fırsat adayları:</p>
          
          <table border="0" cellpadding="10" cellspacing="0" style="width: 100%; border-collapse: collapse;">
            <tr style="border-bottom: 1px solid #bbf7d0;">
              <th align="left">Hisse</th>
              <th align="left">Sinyal Nedeni</th>
              <th align="left">Duyarlılık Skoru</th>
              <th align="left">Görünüm</th>
            </tr>
        """
        for item in discovery_highlights:
            html += f"""
            <tr style="border-bottom: 1px solid #f0fdf4;">
              <td style="padding: 12px 10px;"><b>{item['Kod']}</b></td>
              <td><span style="background-color: #dcfce7; color: #166534; padding: 4px 8px; border-radius: 6px; font-size: 12px;">{item['Neden']}</span></td>
              <td style="color: #15803d; font-weight: bold;">{item['Skor']}/100</td>
              <td style="color: #15803d;">{item['Özet']}</td>
            </tr>
            """
        html += "</table></div>"
    
    # --- SORTING LOGIC ---
    if rsi_alerts_df is not None and not rsi_alerts_df.empty:
        rsi_alerts_df = rsi_alerts_df.sort_values(by='RSI (14)', ascending=True)
        
    if divergence_signals:
        # Sort by date (dd.mm.yyyy) newest first
        divergence_signals.sort(key=lambda x: datetime.strptime(x['date'], '%d.%m.%Y'), reverse=True)
        
    if bearish_signals:
        # Sort by date (dd.mm.yyyy) newest first
        bearish_signals.sort(key=lambda x: datetime.strptime(x['date'], '%d.%m.%Y'), reverse=True)
    # ---------------------
    
    if changed_tickers:
        html += f"""
        <h2>🔔 BİST Son Bilanço Dönemi Güncellenen Hisseler</h2>
        <p>Bugün itibarıyla {len(changed_tickers)} hissenin İş Yatırım'daki (KAP) <b>Son Bilanço Dönemi</b> değişti veya açıklandı.</p>
        
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
              <th>Graham Say.</th>
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
                
                graham = f"₺{row['Graham Sayısı']:.2f}" if 'Graham Sayısı' in row and pd.notna(row['Graham Sayısı']) else "-"
                
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
                  <td>{graham}</td>
                  <td>{pot_str}</td>
                  <td>{rsi_str}</td>
                  <td>{ma200_str}</td>
                </tr>
                """
        html += "</tbody></table><br>"

    if divergence_signals:
        html += f"""
        <h2>📈 Pozitif Uyumsuzluk (Divergence) Tespit Edilen Hisseler</h2>
        <p>Aşağıdaki hisselerde <b>Pozitif Uyumsuzluk</b> (Price Lower Low while RSI Higher Low) tespit edilmiştir. Bu durum teknik olarak dönüş sinyali olabilir:</p>
        
        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%; font-size: 14px;">
          <thead style="background-color: #f2f2f2;">
            <tr>
              <th>Kod</th>
              <th>Sinyal Tarihi</th>
              <th>Fiyat (G/Ö)</th>
              <th>RSI (G/Ö)</th>
              <th>F/K</th>
              <th>PD/DD</th>
              <th>MA200 %</th>
              <th>Potansiyel</th>
            </tr>
          </thead>
          <tbody>
        """
        for signal in divergence_signals:
            ticker = signal['Kod']
            ticker_data = df_calc[df_calc['Kod'] == ticker]
            pot_str = "-"
            fk_str = "-"
            pddd_str = "-"
            ma200_str = "-"
            
            if not ticker_data.empty:
                row = ticker_data.iloc[0]
                pot_val = row['Potansiyel Getiri (%)']
                pot_color = "green" if pot_val and pot_val > 0 else "red"
                pot_str = f"<b><span style='color:{pot_color}'>{pot_val:.2f}%</span></b>" if pd.notna(pot_val) else "-"
                
                fk_str = f"{row['F/K']:.2f}"
                pddd_str = f"{row['PD/DD']:.2f}"
                
                ma200_val = row['MA200 Uzaklık (%)']
                ma200_color = "red" if ma200_val and ma200_val > 0 else "green"
                ma200_str = f"<span style='color:{ma200_color}'>{ma200_val:.1f}%</span>" if pd.notna(ma200_val) else "-"

            html += f"""
            <tr>
              <td><b>{ticker}</b></td>
              <td>{signal['date']}</td>
              <td>{signal['current_price']:.2f} / {signal['prev_price']:.2f}</td>
              <td><span style="color:green">{signal['current_rsi']:.2f}</span> / {signal['prev_rsi']:.2f}</td>
              <td>{fk_str}</td>
              <td>{pddd_str}</td>
              <td>{ma200_str}</td>
              <td>{pot_str}</td>
            </tr>
            """
        html += "</tbody></table><br>"

    if bearish_signals:
        html += f"""
        <h2>📉 Negatif Uyumsuzluk (Bearish Divergence) Tespit Edilen Hisseler</h2>
        <p>Aşağıdaki hisselerde <b>Negatif Uyumsuzluk</b> (Price Higher High while RSI Lower High) tespit edilmiştir. Bu durum teknik olarak dönüş (düşüş) sinyali olabilir:</p>
        
        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%; font-size: 14px;">
          <thead style="background-color: #f2f2f2;">
            <tr>
              <th>Kod</th>
              <th>Sinyal Tarihi</th>
              <th>Fiyat (G/Ö)</th>
              <th>RSI (G/Ö)</th>
              <th>F/K</th>
              <th>PD/DD</th>
              <th>MA200 %</th>
              <th>Potansiyel</th>
            </tr>
          </thead>
          <tbody>
        """
        for signal in bearish_signals:
            ticker = signal['Kod']
            ticker_data = df_calc[df_calc['Kod'] == ticker]
            pot_str = "-"
            fk_str = "-"
            pddd_str = "-"
            ma200_str = "-"
            
            if not ticker_data.empty:
                row = ticker_data.iloc[0]
                pot_val = row['Potansiyel Getiri (%)']
                pot_color = "green" if pot_val and pot_val > 0 else "red"
                pot_str = f"<b><span style='color:{pot_color}'>{pot_val:.2f}%</span></b>" if pd.notna(pot_val) else "-"
                
                fk_str = f"{row['F/K']:.2f}"
                pddd_str = f"{row['PD/DD']:.2f}"
                
                ma200_val = row['MA200 Uzaklık (%)']
                ma200_color = "red" if ma200_val and ma200_val > 0 else "green"
                ma200_str = f"<span style='color:{ma200_color}'>{ma200_val:.1f}%</span>" if pd.notna(ma200_val) else "-"

            html += f"""
            <tr>
              <td><b>{ticker}</b></td>
              <td>{signal['date']}</td>
              <td>{signal['current_price']:.2f} / {signal['prev_price']:.2f}</td>
              <td><span style="color:red">{signal['current_rsi']:.2f}</span> / {signal['prev_rsi']:.2f}</td>
              <td>{fk_str}</td>
              <td>{pddd_str}</td>
              <td>{ma200_str}</td>
              <td>{pot_str}</td>
            </tr>
            """
        html += "</tbody></table><br>"

    if rsi_alerts_df is not None and not rsi_alerts_df.empty:
        html += f"""
        <h2>📉 RSI < 30 (Aşırı Satım) Bölgesindeki Hisseler</h2>
        <p>Aşağıdaki hisseler RSI(14) değeri 30'un altında olan ve potansiyel tepki yükselişi gerçekleştirebilecek hisselerdir:</p>
        
        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%; font-size: 14px;">
          <thead style="background-color: #f2f2f2;">
            <tr>
              <th>Kod</th>
              <th>Sektör</th>
              <th>Fiyat (TL)</th>
              <th>RSI (14)</th>
              <th>Potansiyel</th>
              <th>F/K</th>
              <th>PD/DD</th>
              <th>MA200 %</th>
            </tr>
          </thead>
          <tbody>
        """
        for _, row in rsi_alerts_df.iterrows():
            price = f"₺{row['Kapanış (TL)']:.2f}" if pd.notna(row['Kapanış (TL)']) else "-"
            rsi_val = row['RSI (14)']
            rsi_str = f"<b><span style='color:green'>{rsi_val:.2f}</span></b>"
            
            pot_val = row['Potansiyel Getiri (%)']
            pot_color = "green" if pot_val and pot_val > 0 else "red"
            pot_str = f"<b><span style='color:{pot_color}'>{pot_val:.2f}%</span></b>" if pd.notna(pot_val) else "-"
            
            pddd = f"{row['PD/DD']:.2f}" if pd.notna(row['PD/DD']) else "-"
            fk = f"{row['F/K']:.2f}" if pd.notna(row['F/K']) else "-"
            
            ma200_val = row['MA200 Uzaklık (%)']
            ma200_color = "red" if ma200_val and ma200_val > 0 else "green"
            ma200_str = f"<span style='color:{ma200_color}'>{ma200_val:.1f}%</span>" if pd.notna(ma200_val) else "-"
            
            html += f"""
            <tr>
              <td><b>{row['Kod']}</b></td>
              <td>{row['Sektör']}</td>
              <td>{price}</td>
              <td>{rsi_str}</td>
              <td>{pot_str}</td>
              <td>{fk}</td>
              <td>{pddd}</td>
              <td>{ma200_str}</td>
            </tr>
            """
        html += "</tbody></table><br>"
    
    if portfolio_sentiment:
        html += f"""
        <h2>🏢 Portföy Duyarlılık (Sentiment) Analizi</h2>
        <p>Elinizdeki hisseler için son haber akışına göre hesaplanan duyarlılık skorları:</p>
        
        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%; font-size: 14px;">
          <thead style="background-color: #f2f2f2;">
            <tr>
              <th>Kod</th>
              <th>Duyarlılık Skoru</th>
              <th>Durum</th>
              <th>Haber Sayısı</th>
            </tr>
          </thead>
          <tbody>
        """
        for item in portfolio_sentiment:
            score = item['Skor']
            score_color = "green" if score > 60 else ("red" if score < 40 else "#333")
            
            html += f"""
            <tr>
              <td><b>{item['Kod']}</b></td>
              <td style="color: {score_color}; font-weight: bold;">{score}/100</td>
              <td>{item['Özet']}</td>
              <td style="text-align: center;">{item['Adet']}</td>
            </tr>
            """
        html += "</tbody></table><br>"
    
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
        
    print(f"BİLGİ: {len(changed_tickers)} adet hissede yeni bilanço dönemi (Son Dönem) güncellemesi tespit edildi!")
    
    # 3. Calculate fair values to enrich email for changed tickers
    df_calc, _ = calculate_fair_values(df_raw)
    
    # 3.1. Identify RSI < 30 tickers
    rsi_alerts_df = df_calc[df_calc['RSI (14)'] < 30].sort_values(by='Potansiyel Getiri (%)', ascending=False)
    
    # 3.2. Identify RSI Divergence
    print("BİLGİ: Pozitif uyumsuzluk taraması başlatılıyor (RSI < 45 olan hisseler)...")
    divergence_signals = []
    # Fetch historical data only for potential candidates to be efficient
    candidates = df_calc[df_calc['RSI (14)'] < 45]['Kod'].tolist()
    
    for ticker in candidates:
        try:
            # yfinance needs .IS suffix for BIST
            yf_ticker = ticker + ".IS"
            df_hist = yf.download(yf_ticker, period='100d', interval='1d', progress=False)
            if not df_hist.empty:
                signal = detect_bullish_divergence(df_hist)
                if signal:
                    signal['Kod'] = ticker
                    divergence_signals.append(signal)
                    print(f"SİNYAL: {ticker} için pozitif uyumsuzluk tespit edildi!")
        except Exception as e:
            print(f"HATA: {ticker} için geçmiş veri çekilemedi: {e}")

    # 3.3. Identify Bearish Divergence
    print("BİLGİ: Negatif uyumsuzluk taraması başlatılıyor (RSI > 55 olan hisseler)...")
    bearish_signals = []
    bearish_candidates = df_calc[df_calc['RSI (14)'] > 55]['Kod'].tolist()
    
    for ticker in bearish_candidates:
        try:
            yf_ticker = ticker + ".IS"
            df_hist = yf.download(yf_ticker, period='100d', interval='1d', progress=False)
            if not df_hist.empty:
                signal = detect_bearish_divergence(df_hist)
                if signal:
                    signal['Kod'] = ticker
                    bearish_signals.append(signal)
                    print(f"SİNYAL: {ticker} için negatif uyumsuzluk tespit edildi!")
        except Exception as e:
            print(f"HATA: {ticker} için geçmiş veri çekilemedi: {e}")

    # 3.4. Process Portfolio Sentiment
    portfolio_sentiment = get_portfolio_sentiment(PORTFOLIO_TICKERS)
    
    # 3.5. Discovery Analysis (Signals + Sentiment)
    discovery_candidates = set()
    if not rsi_alerts_df.empty:
        discovery_candidates.update(rsi_alerts_df['Kod'].tolist())
    if divergence_signals:
        discovery_candidates.update([s['Kod'] for s in divergence_signals])
        
    discovery_highlights = get_discovery_highlights(list(discovery_candidates), rsi_alerts_df, divergence_signals)

    if not changed_tickers and rsi_alerts_df.empty and not divergence_signals and not bearish_signals and not portfolio_sentiment and not discovery_highlights:
        print("BİLGİ: Kayda değer bir değişim veya keşif bulunamadı.")
        save_current_dates(current_dates)
        return
        
    print(f"BİLGİ: {len(changed_tickers)} bilanço, {len(rsi_alerts_df)} RSI, {len(divergence_signals)} pozitif, {len(discovery_highlights)} keşif özeti tamamlandı.")
    
    # 4. Generate HTML Email Report
    html_report = format_html_email(df_calc, changed_tickers, rsi_alerts_df, divergence_signals, bearish_signals, portfolio_sentiment, discovery_highlights)
    
    date_str = datetime.now().strftime("%d.%m.%Y")
    subject = f"🔔 BİST Günlük Tarama & Teknik Alarmlar - {date_str}"
    send_email(subject, html_report)
    
    # 5. Save the snapshot for tomorrow's comparison
    save_current_dates(current_dates)
    print("=== Tarama Başarıyla Tamamlandı ===")

if __name__ == "__main__":
    main()
