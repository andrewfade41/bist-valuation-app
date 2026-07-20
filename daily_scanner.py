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
from constants import PERIODS_SNAPSHOT_FILENAME, VOLUME_FILTER_MULTIPLIER
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
    # 1. Load Portfolio Costs and Calculate Status for Email Header
    costs_file = "portfolio_costs.json"
    costs = {}
    if os.path.exists(costs_file):
        try:
            with open(costs_file, 'r', encoding='utf-8') as f:
                costs = json.load(f)
        except Exception:
            pass

    # Load Consensus Target Data
    consensus_file = "consensus_targets.json"
    consensus_data = {}
    if os.path.exists(consensus_file):
        try:
            with open(consensus_file, 'r', encoding='utf-8') as f:
                consensus_data = json.load(f)
        except Exception:
            pass

    portfolio_html = ""
    if costs:
        portfolio_rows_html = ""
        total_inv = 0.0
        total_cur = 0.0
        alert_count = 0
        
        for ticker, buy_price in costs.items():
            if not buy_price or buy_price <= 0.0:
                continue
            
            ticker_data = df_calc[df_calc['Kod'] == ticker]
            if ticker_data.empty:
                continue
                
            row = ticker_data.iloc[0]
            current_price = float(row['Kapanış (TL)'])
            ma50 = float(row['MA50']) if pd.notna(row['MA50']) else np.nan
            rsi = float(row['RSI (14)']) if pd.notna(row['RSI (14)']) else np.nan
            
            gain_pct = ((current_price - buy_price) / buy_price) * 100
            
            # Consensus values
            cons_info = consensus_data.get(ticker, {})
            avg_target = float(cons_info.get("avg_target", 0.0))
            count = int(cons_info.get("count", 0))
            
            cons_pot_str = "-"
            if avg_target > 0:
                cons_pot = ((avg_target - current_price) / current_price) * 100
                cons_pot_str = f"{cons_pot:+.1f}%"
            
            total_inv += buy_price
            total_cur += current_price
            
            tp1 = buy_price * 1.10
            tp2 = buy_price * 1.20
            tp3 = buy_price * 1.30
            
            # Matrix Rules
            op_score = row.get('Operasyonel Skor', 0)
            pot_return = row.get('Potansiyel Getiri (%)', 0)
            net_debt = row.get('Net Borç', 0)
            de_ratio = row.get('Borç/Özkaynak', 0)
            sector = row.get('Sektör', '')
            
            # Banks/Financials do not have industrial margins (EBITDA / Gross Margin) and hold customer deposits (positive Net Debt)
            is_bank_or_financial = (sector == 'Bankacılık') or (pd.isna(row.get('FAVÖK Marjı (%)')) and pd.isna(row.get('Brüt Marj (%)')))
            
            # Check conditions
            if is_bank_or_financial:
                graham_score = row.get('Graham Skoru', 0)
                is_avg_down_candidate = (pot_return > 40.0) and (graham_score >= 6)
                is_strict_stop_candidate = (pot_return < 15.0)
            else:
                is_avg_down_candidate = (op_score >= 6) and (pot_return > 40.0) and (pd.notna(net_debt) and net_debt < 0)
                is_strict_stop_candidate = (op_score < 4) or (pd.notna(de_ratio) and de_ratio > 1.5) or (pot_return < 15.0)
            
            status = "Sakin / Bekle"
            status_color = "#777"
            rec = "Trendi izleyin."
            
            if gain_pct <= -5.0:
                if is_strict_stop_candidate:
                    status = "🚨 ZORUNLU STOP"
                    status_color = "#E43263"
                    rec = f"Zayıf rasyolar / Düşük potansiyel sebebiyle kesinlikle maliyet düşürmeyin. Disiplinli çıkış yapın (%{gain_pct:.1f})."
                    alert_count += 1
                elif is_avg_down_candidate:
                    if gain_pct <= -10.0:
                        status = "🔄 MALİYET DÜŞÜR"
                        status_color = "#2196F3"
                        rec = f"Güçlü şirket (%{gain_pct:.1f}). %10-15 düşüşte veya MA200 desteğinde kademeli ek alım yapabilirsiniz."
                        alert_count += 1
                    else:
                        status = "💪 GÜÇLÜ TUT"
                        status_color = "#2E7D32"
                        rec = f"Hisse kârlı ve nakit zengini (%{gain_pct:.1f}). Panik yapmadan tutabilirsiniz."
                else:
                    status = "🚨 STOP LOSS"
                    status_color = "#E43263"
                    rec = f"Zarar durdur seviyesi aşıldı (%{gain_pct:.1f}). Çıkış düşünülebilir."
                    alert_count += 1
            elif gain_pct >= 30.0:
                status = "🎯 TP3 HEDEFİ"
                status_color = "#2E7D32"
                rec = "Kâr Al 3 bölgesi (+%30). 5'te 1 satabilirsiniz."
                alert_count += 1
            elif gain_pct >= 20.0:
                status = "🎯 TP2 HEDEFİ"
                status_color = "#2E7D32"
                rec = "Kâr Al 2 bölgesi (+%20). 5'te 1 satarak kâr kilitleyin."
                alert_count += 1
            elif gain_pct >= 10.0:
                status = "🎯 TP1 HEDEFİ"
                status_color = "#2E7D32"
                rec = "Kâr Al 1 bölgesi (+%10). 5'te 1 satarak nakit yaratın."
                alert_count += 1
            elif gain_pct >= 15.0:
                status = "🛡️ BAŞABAŞ"
                status_color = "#F09E3F"
                rec = f"Stopu maliyet olan ₺{buy_price:.2f}'ye çekin."
                alert_count += 1
                
            if gain_pct < 10.0 and gain_pct > -3.0:
                if pd.notna(ma50) and abs((current_price - ma50) / ma50 * 100) <= 3.0:
                    status = "🔄 DESTEKTE"
                    rec = f"SMA50 (₺{ma50:.2f}) desteğinde. Geri alım yapabilirsiniz."
                    status_color = "#2196F3"
                    alert_count += 1
                elif abs((current_price - buy_price) / buy_price * 100) <= 3.0:
                    status = "🔄 MALİYETTE"
                    rec = "Maliyet seviyesine geri çekildi. Swing eklemesi yapılabilir."
                    status_color = "#2196F3"
                    alert_count += 1

            portfolio_rows_html += f"""
            <tr style="border-bottom: 1px solid #ddd; font-size: 13px;">
              <td style="padding: 10px;"><b>{ticker}</b></td>
              <td style="padding: 10px;">₺{buy_price:.2f}</td>
              <td style="padding: 10px;">₺{current_price:.2f}</td>
              <td style="padding: 10px; color: {'green' if gain_pct >= 0 else 'red'}; font-weight: bold;">{gain_pct:+.2f}%</td>
              <td style="padding: 10px; color: {status_color}; font-weight: bold;">{status}</td>
              <td style="padding: 10px;">{f'₺{avg_target:.2f}' if avg_target > 0 else '-'}</td>
              <td style="padding: 10px; color: {'green' if (avg_target > current_price) else 'red'}; font-weight: bold;">{cons_pot_str}</td>
              <td style="padding: 10px; font-size: 12px; color: #555;">{rec}</td>
              <td style="padding: 10px; color: #555;">{f'{rsi:.1f}' if pd.notna(rsi) else '-'}</td>
              <td style="padding: 10px; color: #555; text-align: center;">{f'{count}' if count > 0 else '-'}</td>
            </tr>
            """
            
        port_gain_str = "-"
        if total_inv > 0:
            port_gain = ((total_cur - total_inv) / total_inv) * 100
            port_gain_str = f"{port_gain:+.2f}%"

        # Helper to find weak reasons for low operational score
        def get_weak_ratios(row):
            reasons = []
            favok_grow = row.get('FAVÖK Yıllık Büyüme (%)')
            net_profit_grow = row.get('Net Kar Yıllık Büyüme (%)')
            brut_marj = row.get('Brüt Marj (%)')
            favok_marj = row.get('FAVÖK Marjı (%)')
            net_marj = row.get('Net Kar Marjı (%)')
            net_debt = row.get('Net Borç')
            cari_oran = row.get('Cari Oran')
            de_ratio = row.get('Borç/Özkaynak')
            
            if pd.isna(favok_grow) or float(favok_grow) <= 0:
                reasons.append("Negatif FAVÖK Büyümesi")
            if pd.isna(net_profit_grow) or float(net_profit_grow) <= 0:
                reasons.append("Negatif Net Kâr Büyümesi")
            if pd.isna(brut_marj) or float(brut_marj) <= 0:
                reasons.append("Düşük Brüt Marj")
            if pd.isna(favok_marj) or float(favok_marj) <= 0:
                reasons.append("Düşük FAVÖK Marjı")
            if pd.isna(net_marj) or float(net_marj) <= 0:
                reasons.append("Düşük Net Kâr Marjı")
            if pd.notna(net_debt) and float(net_debt) > 0:
                reasons.append("Yüksek Net Borç")
            if pd.isna(cari_oran) or float(cari_oran) < 1.5:
                reasons.append("Düşük Cari Oran")
            if pd.notna(de_ratio) and float(de_ratio) > 1.5:
                reasons.append("Yüksek Borç/Özkaynak")
            return reasons

        # Determine switch suggestions
        sell_candidates = []
        for ticker, buy_price in costs.items():
            if not buy_price or buy_price <= 0.0:
                continue
            ticker_data = df_calc[df_calc['Kod'] == ticker]
            if ticker_data.empty:
                continue
            row = ticker_data.iloc[0]
            current_price = float(row['Kapanış (TL)'])
            gain_pct = ((current_price - buy_price) / buy_price) * 100
            pot_return = float(row.get('Potansiyel Getiri (%)', 0.0))
            op_score = int(row.get('Operasyonel Skor', 0))
            
            reasons = []
            sector = row.get('Sektör', '')
            is_bank_or_financial = (sector == 'Bankacılık') or (pd.isna(row.get('FAVÖK Marjı (%)')) and pd.isna(row.get('Brüt Marj (%)')))
            
            if gain_pct >= 25.0:
                reasons.append(f"Yüksek Kâr (+%{gain_pct:.1f})")
            if pot_return < 15.0:
                reasons.append(f"Kalan Potansiyel Düşük (+%{pot_return:.1f})")
            if op_score < 4 and not is_bank_or_financial:
                weak_list = get_weak_ratios(row)
                weak_str = f" ({', '.join(weak_list[:3])})" if weak_list else ""
                reasons.append(f"Zayıf Rasyolar (Skor: {op_score}/10{weak_str})")
                
            if reasons:
                sell_candidates.append({
                    "Hisse": ticker,
                    "Potansiyel (%)": pot_return,
                    "Neden": " ve ".join(reasons)
                })
                
        outside_df = df_calc[~df_calc['Kod'].isin(list(costs.keys()))]
        buy_candidates = []
        if not outside_df.empty:
            strong_outside = outside_df[
                (outside_df['Operasyonel Skor'] >= 6) & 
                (outside_df['Potansiyel Getiri (%)'] >= 40.0)
            ].copy()
            if not strong_outside.empty:
                strong_outside = strong_outside.sort_values(by='Potansiyel Getiri (%)', ascending=False)
                seen_sectors = set()
                for _, row in strong_outside.iterrows():
                    sector = row.get('Sektör', 'Bilinmeyen')
                    if sector in seen_sectors:
                        continue
                    seen_sectors.add(sector)
                    buy_candidates.append({
                        "Hisse": row['Kod'],
                        "Potansiyel (%)": float(row['Potansiyel Getiri (%)']),
                        "Skor": int(row['Operasyonel Skor']),
                        "Sektör": sector
                    })
                    if len(buy_candidates) >= 5:
                        break
                    
        switch_html = ""
        if sell_candidates and buy_candidates:
            switch_rows_html = ""
            for idx, s in enumerate(sell_candidates):
                match = buy_candidates[idx % len(buy_candidates)]
                switch_rows_html += f"""
                <tr style="border-bottom: 1px solid #eee; font-size: 13px;">
                  <td style="padding: 10px; color: #E43263;"><b>{s['Hisse']} Sat</b> ({s['Neden']})</td>
                  <td style="padding: 10px; text-align: center; color: #F09E3F; font-weight: bold;">➡️</td>
                  <td style="padding: 10px; color: #2E7D32;"><b>{match['Hisse']} Al</b> (Pot.: +{match['Potansiyel (%)']:.1f}% | Skor: {match['Skor']}/10 | {match['Sektör']})</td>
                </tr>
                """
            
            switch_html = f"""
            <div style="margin-top: 20px; border-top: 1px solid #ddd; padding-top: 15px;">
              <h4 style="color: #5A1F8A; margin-top: 0;">🔄 Portföy Takas (Switch) Önerileri</h4>
              <p style="font-size: 12px; color: #666; margin-bottom: 10px;">
                Portföyünüzde hedefine yaklaşan veya rasyoları bozulan hisseleri satıp, piyasadaki daha kârlı alternatiflere geçiş yapmayı düşünebilirsiniz:
              </p>
              <table border="0" cellpadding="0" cellspacing="0" style="width: 100%; border-collapse: collapse;">
                <tbody>
                  {switch_rows_html}
                </tbody>
              </table>
            </div>
            """

        portfolio_html = f"""
        <div style="background-color: #f7f9fc; border: 2px solid #5A1F8A; border-radius: 12px; padding: 20px; margin-bottom: 25px; font-family: Arial, sans-serif;">
          <h2 style="color: #5A1F8A; margin-top: 0; display: flex; align-items: center; gap: 8px;">
            🔄 Portföy Satış & Swing Asistanı Raporu
          </h2>
          <p style="font-size: 14px; margin-bottom: 15px;">
            Toplam Getiri: <b>{port_gain_str}</b> | Aktif Uyarılı Hisse: <b>{alert_count}</b>
          </p>
          
          <table border="0" cellpadding="0" cellspacing="0" style="width: 100%; border-collapse: collapse; text-align: left;">
            <thead>
              <tr style="border-bottom: 2px solid #5A1F8A; font-size: 13px; color: #5A1F8A;">
                <th style="padding: 8px 10px;">Hisse</th>
                <th style="padding: 8px 10px;">Maliyet</th>
                <th style="padding: 8px 10px;">Son Fiyat</th>
                <th style="padding: 8px 10px;">Getiri (%)</th>
                <th style="padding: 8px 10px;">Durum</th>
                <th style="padding: 8px 10px;">Konsensüs Ort.</th>
                <th style="padding: 8px 10px;">Kalan Pot.</th>
                <th style="padding: 8px 10px;">Öneri / Aksiyon</th>
                <th style="padding: 8px 10px;">RSI</th>
                <th style="padding: 8px 10px;">Kurum</th>
              </tr>
            </thead>
            <tbody>
              {portfolio_rows_html}
            </tbody>
          </table>
          {switch_html}
        </div>
        """

    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333;">
        {portfolio_html}
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
        # Sort by date (dd.mm.yyyy) newest first, handle invalid/empty dates robustly
        def parse_div_date(x):
            try:
                return datetime.strptime(x.get('date', ''), '%d.%m.%Y')
            except (ValueError, TypeError):
                return datetime.min
        divergence_signals.sort(key=parse_div_date, reverse=True)
        
    if bearish_signals:
        # Sort by date (dd.mm.yyyy) newest first, handle invalid/empty dates robustly
        def parse_bear_date(x):
            try:
                return datetime.strptime(x.get('date', ''), '%d.%m.%Y')
            except (ValueError, TypeError):
                return datetime.min
        bearish_signals.sort(key=parse_bear_date, reverse=True)
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
    
    # 3.0. Apply volume filter for technical analysis alerts (RSI, divergence, discovery)
    # We only include stocks whose volume is above 60-day average volume by the multiplier (e.g. 3x)
    # Portfolio stocks and earnings announcements remain unfiltered so user gets updates for them regardless of volume.
    if 'volume' in df_calc.columns and 'average_volume_60d_calc' in df_calc.columns:
        df_tech = df_calc.dropna(subset=['volume', 'average_volume_60d_calc'])
        df_tech = df_tech[df_tech['volume'] > df_tech['average_volume_60d_calc'] * VOLUME_FILTER_MULTIPLIER]
        print(f"BİLGİ: Teknik analiz alarmları için hacim filtresi uygulandı. {len(df_calc)} hisseden {len(df_tech)} tanesi kriterleri sağlıyor.")
    else:
        df_tech = df_calc
        print("UYARI: Hacim verileri bulunamadı, teknik analiz alarmları filtrelenmeden çalışacak.")
    
    # 3.1. Identify RSI < 30 tickers
    rsi_alerts_df = df_tech[df_tech['RSI (14)'] < 30].sort_values(by='Potansiyel Getiri (%)', ascending=False)
    
    # 3.2. Identify RSI Divergence
    print("BİLGİ: Pozitif uyumsuzluk taraması başlatılıyor (RSI < 45 olan hisseler)...")
    divergence_signals = []
    # Fetch historical data only for potential candidates to be efficient
    candidates = df_tech[df_tech['RSI (14)'] < 45]['Kod'].tolist()
    
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
    bearish_candidates = df_tech[df_tech['RSI (14)'] > 55]['Kod'].tolist()
    
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
