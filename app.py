import streamlit as st
import pandas as pd
import numpy as np
import os
import yfinance as yf
import json
import math
from datetime import datetime
from dotenv import load_dotenv
from data_fetcher import fetch_bist_fundamentals
from calculator import calculate_fair_values
from portfolio_opt import optimize_portfolio
from sentiment_analyzer import fetch_stock_news, get_overall_sentiment
from constants import (
    FRESHNESS_CURRENT_COLOR, FRESHNESS_PREVIOUS_COLOR, FRESHNESS_STALE_COLOR,
    RSI_OVERSOLD, RSI_OVERBOUGHT, HALKA_ACIKLIK_LOW, HALKA_ACIKLIK_IDEAL_MAX,
    HALKA_ACIKLIK_HIGH, TAKAS_CHANGE_STRONG, OP_SCORE_EXCELLENT, OP_SCORE_GOOD,
    OP_SCORE_POOR, GRAHAM_SCORE_EXCELLENT, GRAHAM_SCORE_GOOD, GRAHAM_SCORE_POOR,
    GROWTH_STRONG_COLOR_THRESHOLD, GRID_MAX_TICKERS, GRID_COLUMNS,
    CHART_HISTORY_PERIOD, MAX_WATCHLISTS, PORTFOLIO_MIN_TICKERS,
    PORTFOLIO_MAX_TICKERS,
)
import streamlit.components.v1 as components

# Load environment variables
load_dotenv()

def load_env_watchlists():
    watchlists = {}
    for i in range(1, MAX_WATCHLISTS + 1):
        try:
            name = st.secrets.get(f"WATCHLIST_{i}_NAME", os.getenv(f"WATCHLIST_{i}_NAME", ""))
            tickers = st.secrets.get(f"WATCHLIST_{i}_TICKERS", os.getenv(f"WATCHLIST_{i}_TICKERS", ""))
        except Exception:
            name = os.getenv(f"WATCHLIST_{i}_NAME", "")
            tickers = os.getenv(f"WATCHLIST_{i}_TICKERS", "")
            
        if name and tickers.strip():
            watchlists[str(i)] = {"name": name, "tickers": tickers}
    return watchlists

def render_lightweight_chart(ticker, data_json, container_id):
    """Generates the HTML for a TradingView Lightweight Chart using provided OHLC data."""
    return f"""
    <div id="{container_id}" style="height:400px;width:100%;background-color:#131722;margin:0;padding:0;overflow:hidden;"></div>
    <script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
    <script type="text/javascript">
    (function() {{
        // Give it a small delay to ensure the iframe container has dimensions
        setTimeout(() => {{
            const container = document.getElementById('{container_id}');
            if (!container) return;
            
            const chart = LightweightCharts.createChart(container, {{
                width: window.innerWidth,
                height: 400,
                layout: {{
                    background: {{ type: 'solid', color: '#131722' }},
                    textColor: '#d1d4dc',
                }},
                grid: {{
                    vertLines: {{ color: 'rgba(42, 46, 57, 0.6)' }},
                    horzLines: {{ color: 'rgba(42, 46, 57, 0.6)' }},
                }},
                crosshair: {{ mode: LightweightCharts.CrosshairMode.Normal }},
                priceScale: {{ borderColor: 'rgba(197, 203, 206, 0.8)' }},
                timeScale: {{ 
                    borderColor: 'rgba(197, 203, 206, 0.8)',
                    timeVisible: true,
                    secondsVisible: false
                }},
            }});

            const candleSeries = chart.addCandlestickSeries({{
                upColor: '#26a69a', downColor: '#ef5350', borderVisible: false,
                wickUpColor: '#26a69a', wickDownColor: '#ef5350',
            }});

            const data = {data_json};
            if (data && data.length > 0) {{
                candleSeries.setData(data);
                chart.timeScale().fitContent();
            }}
            
            window.addEventListener('resize', () => {{
                chart.applyOptions({{ width: window.innerWidth }});
            }});
        }}, 50);
    }})();
    </script>
    <style>body {{ margin: 0; padding: 0; background-color: #131722; }}</style>
    """

def _generate_radar_chart_svg(labels, stock_values, sector_values, stock_name, sector_name):
    """
    Generates an interactive SVG radar chart comparing stock vs sector metrics.
    Values should be 0-100 normalized.
    """
    n = len(labels)
    if n < 3:
        return "<p>Yeterli veri yok</p>"
    
    # Chart dimensions
    cx, cy = 240, 240
    max_r = 180
    rings = 5  # concentric rings (20, 40, 60, 80, 100)
    
    # Brand colors
    stock_color = "#E43263"    # Secondary Pink
    sector_color = "#5A1F8A"   # Primary Purple
    grid_color = "rgba(255,255,255,0.15)"
    label_color = "#d1d4dc"
    bg_color = "#131722"
    
    # Calculate angles
    angles = [2 * math.pi * i / n - math.pi / 2 for i in range(n)]
    
    def polar_to_xy(angle, value):
        r = (value / 100) * max_r
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        return x, y
    
    svg_parts = []
    svg_parts.append(f'''<div style="display:flex;justify-content:center;background:{bg_color};padding:20px;border-radius:16px;border:1px solid rgba(255,255,255,0.1);">
    <svg width="500" height="500" viewBox="0 0 500 500" xmlns="http://www.w3.org/2000/svg">
    <rect width="500" height="500" fill="{bg_color}" rx="16"/>''')
    
    # Draw concentric ring grid
    for ring_i in range(1, rings + 1):
        ring_val = ring_i * (100 / rings)
        points = []
        for angle in angles:
            x, y = polar_to_xy(angle, ring_val)
            points.append(f"{x:.1f},{y:.1f}")
        svg_parts.append(f'<polygon points="{" ".join(points)}" fill="none" stroke="{grid_color}" stroke-width="1"/>')
    
    # Draw axis lines
    for angle in angles:
        x2, y2 = polar_to_xy(angle, 100)
        svg_parts.append(f'<line x1="{cx}" y1="{cy}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{grid_color}" stroke-width="1"/>')
    
    # Draw sector polygon (background)
    sector_points = []
    for i, angle in enumerate(angles):
        x, y = polar_to_xy(angle, sector_values[i])
        sector_points.append(f"{x:.1f},{y:.1f}")
    svg_parts.append(f'<polygon points="{" ".join(sector_points)}" fill="rgba(90,31,138,0.2)" stroke="{sector_color}" stroke-width="2" stroke-dasharray="6,3"/>')
    
    # Draw stock polygon (foreground)
    stock_points = []
    for i, angle in enumerate(angles):
        x, y = polar_to_xy(angle, stock_values[i])
        stock_points.append(f"{x:.1f},{y:.1f}")
    svg_parts.append(f'<polygon points="{" ".join(stock_points)}" fill="rgba(228,50,99,0.25)" stroke="{stock_color}" stroke-width="2.5"/>')
    
    # Draw data points and labels
    for i, angle in enumerate(angles):
        # Stock data point
        sx, sy = polar_to_xy(angle, stock_values[i])
        svg_parts.append(f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="5" fill="{stock_color}" stroke="white" stroke-width="1.5"/>')
        
        # Sector data point
        secx, secy = polar_to_xy(angle, sector_values[i])
        svg_parts.append(f'<circle cx="{secx:.1f}" cy="{secy:.1f}" r="4" fill="{sector_color}" stroke="white" stroke-width="1"/>')
        
        # Labels — position outside the chart
        lx, ly = polar_to_xy(angle, 118)
        anchor = "middle"
        if lx < cx - 10:
            anchor = "end"
        elif lx > cx + 10:
            anchor = "start"
        
        svg_parts.append(f'<text x="{lx:.1f}" y="{ly:.1f}" fill="{label_color}" font-size="11" font-family="Inter,Arial,sans-serif" text-anchor="{anchor}" dominant-baseline="middle">{labels[i]}</text>')
        
        # Value annotations (stock value near the point)
        vx, vy = polar_to_xy(angle, stock_values[i] + 10 if stock_values[i] < 85 else stock_values[i] - 10)
        svg_parts.append(f'<text x="{vx:.1f}" y="{vy:.1f}" fill="{stock_color}" font-size="9" font-family="Inter,Arial,sans-serif" text-anchor="middle" dominant-baseline="middle" font-weight="bold">{stock_values[i]:.0f}</text>')
    
    # Legend
    legend_y = 470
    svg_parts.append(f'<circle cx="140" cy="{legend_y}" r="6" fill="{stock_color}"/>')
    svg_parts.append(f'<text x="152" y="{legend_y}" fill="{label_color}" font-size="12" font-family="Inter,Arial,sans-serif" dominant-baseline="middle">{stock_name}</text>')
    svg_parts.append(f'<line x1="270" y1="{legend_y-4}" x2="290" y2="{legend_y-4}" stroke="{sector_color}" stroke-width="2" stroke-dasharray="6,3"/>')
    svg_parts.append(f'<circle cx="280" cy="{legend_y}" r="5" fill="{sector_color}"/>')
    svg_parts.append(f'<text x="298" y="{legend_y}" fill="{label_color}" font-size="12" font-family="Inter,Arial,sans-serif" dominant-baseline="middle">{sector_name}</text>')
    
    svg_parts.append('</svg></div>')
    
    return '\n'.join(svg_parts)

st.set_page_config(page_title="BIST Adil Değer Analizi", layout="wide", page_icon="📈")

st.title("📈 Borsa İstanbul (BIST) Adil Değer & Hedef Fiyat Hesaplama")
st.markdown("""
Bu uygulama temel analiz çarpanlarını kullanarak Borsa İstanbul şirketlerinin **olması gereken fiyatlarını (adil değerini)** hesaplar. 
Şirketlerin güncel bilanço verileri İş Yatırım üzerinden anlık çekilir.

Önemli Not: Bankalar ve GYO'lar F/K ve PD/DD açısından sanayi şirketlerinden farklı değerlendirilmelidir, sonuçlar sektör spesifik incelenmelidir.
""")

# Sidebar settings
st.sidebar.header("Hesaplama Parametreleri")
st.sidebar.markdown("Sektör veya genel beklentilerinize göre aşağıdaki varsayılan çarpanları değiştirebilirsiniz.")

target_fk = st.sidebar.number_input("Beklenen F/K Çarpanı", min_value=1.0, max_value=50.0, value=10.0, step=0.5, 
                                    help="Şirket kârlarının kaç katından fiyatlanması gerektiğini temsil eder.")
target_pddd = st.sidebar.number_input("Beklenen PD/DD Çarpanı", min_value=0.5, max_value=10.0, value=1.5, step=0.1,
                                     help="Defter değerinin kaç katından fiyatlanması gerektiğini temsil eder.")
expected_return_pct = st.sidebar.number_input("Beklenen Risksiz Getiri (%)", min_value=10, max_value=100, value=50, step=5,
                                             help="Mevduat veya risksiz sabit getiri oranını temsil eder.")

st.sidebar.markdown("---")
st.sidebar.header("📋 Takip Listeleri")
st.sidebar.markdown("Takip listeleriniz `.env` veya Streamlit Secrets üzerinden yüklenmektedir. (Örn: `WATCHLIST_1_NAME`)")

watchlists = load_env_watchlists()
if watchlists:
    st.sidebar.success(f"{len(watchlists)} adet liste yüklendi.")
    for key, data in watchlists.items():
        st.sidebar.caption(f"**{data['name']}**: {data['tickers'][:30]}...")
else:
    st.sidebar.info("Ayar dosyasında aktif bir takip listesi bulunamadı.")
    
st.sidebar.markdown("---")

# Fetch Data Button
if 'raw_data' not in st.session_state:
    st.session_state.raw_data = None

if st.button("Verileri Çek ve Hesapla", type="primary"):
    with st.spinner('İş Yatırım API üzerinden temel analist verileri çekiliyor... Lütfen bekleyiniz.'):
        df_raw = fetch_bist_fundamentals()
        if df_raw is not None and not df_raw.empty:
            st.session_state.raw_data = df_raw
            st.success(f"{len(df_raw)} adet hisse senedi verisi başarıyla yüklendi!")
        else:
            st.error("Veri çekilirken bir hata oluştu. Lütfen bağlantınızı kontrol edin ve tekrar deneyin.")

# Display Application Logic
if st.session_state.raw_data is not None:
    expected_return = expected_return_pct / 100.0
    
    # Calculate values dynamically based on current slider inputs
    df_calc, stats = calculate_fair_values(st.session_state.raw_data, target_fk, target_pddd, expected_return)
    
    # Display BIST & Sector Averages
    st.markdown("### 📊 Genel Piyasa ve Sektör Ortalamaları")
    colA, colB = st.columns(2)
    colA.metric(label="BİST Ortalama F/K", value=stats['bist_avg_fk'])
    colB.metric(label="BİST Ortalama PD/DD", value=stats['bist_avg_pddd'])
    
    with st.expander("Sektör Ortalamalarını Görüntüle (F/K ve PD/DD)"):
        st.dataframe(
            stats['sector_avg_df'].style.format({
                "Sektör_FK_Ortalama": "{:.2f}",
                "Sektör_PDDD_Ortalama": "{:.2f}"
            }),
            use_container_width=True
        )

    st.markdown("---")
    # Filters
    st.subheader("🔍 Filtreleme")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        min_potential = st.number_input("Minimum Potansiyel Getiri (%)", value=0.0)
        min_graham = st.number_input("Minimum Graham Skoru", min_value=0.0, max_value=10.0, value=0.0, step=1.0)
    with col2:
        search_ticker = st.text_input("Hisse Kodu Ara (Örn: THYAO, TUPRS)").upper()
    with col3:
        # Get sector list dynamically from calculated dataframe
        all_sectors = sorted(df_calc['Sektör'].astype(str).unique().tolist())
        
        # Create a sector count mapping for display
        sector_counts = stats['sector_avg_df'].set_index('Sektör')['Hisse_Sayısı'].to_dict()
        def sector_format_func(option):
            count = sector_counts.get(option, 0)
            return f"{option} ({count})"
            
        selected_sectors = st.multiselect("Sektör Seç", options=all_sectors, default=[], format_func=sector_format_func)
    with col4:
        # Get periods dynamically
        all_periods = sorted(df_calc['Son Dönem'].dropna().astype(str).unique().tolist(), reverse=True)
        selected_periods = st.multiselect("Bilanço Dönemi Seç", options=all_periods, default=[])
    with col5:
        st.write("") # spacer to align with inputs
        st.write("")
        # Add Portfolio filter
        # Try to get from Streamlit Cloud Secrets first, then fallback to .env/os.environ
        try:
            portfolio_tickers_env = st.secrets.get("PORTFOLIO_TICKERS", os.getenv("PORTFOLIO_TICKERS", ""))
        except Exception:
            portfolio_tickers_env = os.getenv("PORTFOLIO_TICKERS", "")
            
        portfolio_tickers = [t.strip().upper() for t in portfolio_tickers_env.split(",") if t.strip()]
        
        watchlists_filter = load_env_watchlists()
        active_lists = {wl["name"]: wl["tickers"] for wl in watchlists_filter.values()}
        
        filter_options = ["Tümü", "Sadece Portföyüm"] + list(active_lists.keys())
        selected_filter = st.selectbox("Gösterim Filtresi", options=filter_options, index=0)
        
        show_minervini = st.checkbox("🎯 Minervini Trend Filtresi", value=False, help="Minervini trend kriterlerine uyan, yükseliş eğilimindeki hisseleri süzer.")
        hide_no_fk = st.checkbox("F/K'sı Olmayanları Gizle", value=False, help="F/K değeri bulunmayan (zarar eden veya verisi eksik) hisseleri tablodan çıkarır.")
        
    with st.expander("📈 Gelişmiş Takas Filtreleri"):
        tc1, tc2, tc3, tc4 = st.columns(4)
        with tc1:
            min_yabanci = st.number_input("Min. Yabancı Payı (%)", value=0.0)
        with tc2:
            min_7g = st.number_input("Min. 7G Değişim (%)", value=-100.0, step=0.1)
        with tc3:
            min_30g = st.number_input("Min. 30G Değişim (%)", value=-100.0, step=0.1)
        with tc4:
            min_90g = st.number_input("Min. 90G Değişim (%)", value=-100.0, step=0.1)
            
    with st.expander("📈 Operasyonel & Büyüme Filtreleri"):
        oc1, oc2, oc3 = st.columns(3)
        with oc1:
            show_cash_rich = st.checkbox("💵 Sadece Net Borç < 0 (Nakit Zenginleri)", value=False)
            min_op_score = st.slider("Min. Operasyonel Skor", 0, 10, 0)
        with oc2:
            min_favok_growth = st.number_input("Min. FAVÖK Büyümesi (%)", value=-99999.0, step=5.0)
        with oc3:
            min_net_growth = st.number_input("Min. Net Kar Büyümesi (%)", value=-99999.0, step=5.0)
        
    # Filter based on potential return, but include NaNs if min_potential is 0 or less
    if min_potential <= 0:
        df_filtered = df_calc.copy()
    else:
        df_filtered = df_calc[df_calc['Potansiyel Getiri (%)'] >= min_potential]
        
    if 'Graham Skoru' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['Graham Skoru'].fillna(0) >= min_graham]
        
    if hide_no_fk:
        df_filtered = df_filtered[df_filtered['F/K'].notna() & (df_filtered['F/K'] > 0)]
    if search_ticker:
        search_list = [x.strip() for x in search_ticker.replace(',', ' ').split() if x.strip()]
        if search_list:
            pattern = '|'.join(search_list)
            df_filtered = df_filtered[df_filtered['Kod'].str.contains(pattern, case=False, na=False, regex=True)]
    if selected_sectors:
        df_filtered = df_filtered[df_filtered['Sektör'].isin(selected_sectors)]
    if selected_periods:
        df_filtered = df_filtered[df_filtered['Son Dönem'].isin(selected_periods)]
    if selected_filter == "Sadece Portföyüm":
        if portfolio_tickers:
            df_filtered = df_filtered[df_filtered['Kod'].isin(portfolio_tickers)]
        else:
            st.warning("Gösterilecek portföy hissesi bulunamadı. Lütfen `.env` (lokal) veya **Streamlit Secrets** (cloud) üzerinde `PORTFOLIO_TICKERS=THYAO, TUPRS` şeklinde tanımlama yapınız.")
    elif selected_filter in active_lists:
        wl_tickers_str = active_lists[selected_filter]
        wl_tickers = [t.strip().upper() for t in wl_tickers_str.replace(',', ' ').split() if t.strip()]
        if wl_tickers:
            df_filtered = df_filtered[df_filtered['Kod'].isin(wl_tickers)]
        else:
            st.warning(f"'{selected_filter}' listesinde uygun hisse bulunamadı. Lütfen sol menüden listeye hisse ekleyin.")
            
    # Takas Filtering
    if 'Yabancı Payı (%)' in df_filtered.columns:
        df_filtered = df_filtered[(df_filtered['Yabancı Payı (%)'] >= min_yabanci) | (df_filtered['Yabancı Payı (%)'].isna())]
    if 'Takas (7G Değişim %)' in df_filtered.columns:
        df_filtered = df_filtered[(df_filtered['Takas (7G Değişim %)'] >= min_7g) | (df_filtered['Takas (7G Değişim %)'].isna())]
    if 'Takas (30G Değişim %)' in df_filtered.columns:
        df_filtered = df_filtered[(df_filtered['Takas (30G Değişim %)'] >= min_30g) | (df_filtered['Takas (30G Değişim %)'].isna())]
    if 'Takas (90G Değişim %)' in df_filtered.columns:
        df_filtered = df_filtered[(df_filtered['Takas (90G Değişim %)'] >= min_90g) | (df_filtered['Takas (90G Değişim %)'].isna())]
    
    # Operational & Growth Filters
    if show_cash_rich and 'Net Borç' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['Net Borç'] < 0]
    if min_op_score > 0:
        df_filtered = df_filtered[df_filtered['Operasyonel Skor'] >= min_op_score]
    if 'FAVÖK Yıllık Büyüme (%)' in df_filtered.columns:
        df_filtered = df_filtered[(df_filtered['FAVÖK Yıllık Büyüme (%)'] >= min_favok_growth) | (df_filtered['FAVÖK Yıllık Büyüme (%)'].isna())]
    if 'Net Kar Yıllık Büyüme (%)' in df_filtered.columns:
        df_filtered = df_filtered[(df_filtered['Net Kar Yıllık Büyüme (%)'] >= min_net_growth) | (df_filtered['Net Kar Yıllık Büyüme (%)'].isna())]

    # --- AI Analyst Panel ---
    st.markdown("---")
    with st.expander("🤖 BIST Yapay Zeka Analisti (Claude Plugin Hazırlığı)", expanded=False):
        st.info("Bu panel, verileri Claude için hazırlanan 'BIST Specialist' plugin formatına dönüştürür.")
        
        mode = st.radio("İş Modu:", ["Genel Özet (/bist-summary)", "Fikir Üretme (/fikir-uret)"], horizontal=True)
        top_n = st.slider("Analiz edilecek hisse sayısı", 5, 20, 10)
        
        if not df_filtered.empty:
            if "Fikir Üretme" in mode:
                # Prioritize Potential Return + Operational Score
                ai_data = df_filtered.sort_values(['Potansiyel Getiri (%)', 'Operasyonel Skor'], ascending=False).head(top_n)
                title = "### BIST FİKİR ÜRETME (DEĞERLİ BÜYÜME) VERİ SETİ"
                hint = "/fikir-uret"
            else:
                # Prioritize Scores
                ai_data = df_filtered.sort_values(['Operasyonel Skor', 'Graham Skoru'], ascending=False).head(top_n)
                title = "### BIST GENEL ÖZET VERİ SETİ"
                hint = "/bist-summary"

            analysis_prompt = f"{title} ({datetime.now().strftime('%d.%m.%Y')})\n\n"
            analysis_prompt += f"Aşağıdaki {top_n} hisse, seçilen moda göre en öncelikli şirketlerdir:\n\n"
            
            for _, row in ai_data.iterrows():
                analysis_prompt += f"- **{row['Kod']}**: Operasyonel Skor: {row['Operasyonel Skor']}/10, Graham Skoru: {row['Graham Skoru']}, Potansiyel: %{row['Potansiyel Getiri (%)']:.1f}, Net Borç: ₺{row['Net Borç']:,.0f}, FAVÖK Büyüme: %{row['FAVÖK Yıllık Büyüme (%)']:.1f}\n"
            
            st.text_area("Claude'a Yapıştırılacak Mesaj:", value=analysis_prompt, height=200)
            st.caption("İpucu: Claude'da '/bist-summary' komutunu kullanarak bu verileri profesyonelce yorumlatabilirsiniz.")
        else:
            st.warning("Filtrelere uygun hisse bulunamadı.")
            
    # --- Portfolio Optimization UI ---
    st.markdown("---")
    with st.expander("🤖 Yapay Zeka ile Portföy Optimizasyonu (Markowitz)"):
        st.markdown("İdeal getiri ve risk oranını (Maksimum Sharpe) yakalamak için **tabloda filtrelenmiş olan** hisselerin son 2 yıllık fiyat dalgalanması (riski) ve güncel **Bilanço Potansiyel Getirisi** kullanılarak en uygun ağırlıklar hesaplanacaktır.")
        
        opt_tickers = df_filtered['Kod'].tolist()
        if len(opt_tickers) < 2:
            st.warning("Optimizasyon için tabloda en az 2 hisse bulunmalıdır.")
        elif len(opt_tickers) > PORTFOLIO_MAX_TICKERS:
            st.warning(f"Tabloda {len(opt_tickers)} hisse var. Aşırı veri indirmesi API engeline takılabileceği ve çok yavaş çalışacağı için lütfen filtreleri kullanarak hisse sayısını en fazla {PORTFOLIO_MAX_TICKERS}'a düşürünüz. (Örn: Sektör seçin veya Potansiyel Getiriyi artırın)")
        else:
            if st.button(f"Filtrelenmiş {len(opt_tickers)} Hisse İçin Ağırlıkları Hesapla", type="primary", key="btn_opt"):
                with st.spinner("Geçmiş piyasa verileri indiriliyor ve temel analiz beklentileriniz ile optimize ediliyor..."):
                    
                    # Create custom returns dict from the calculated 'Potansiyel Getiri (%)'
                    # We divide by 100 because the percentage is displayed as 50.0 instead of 0.50
                    custom_returns = dict(zip(df_filtered['Kod'], df_filtered['Potansiyel Getiri (%)'] / 100.0))
                    
                    weights, perf, warning_msg = optimize_portfolio(opt_tickers, custom_returns_dict=custom_returns)
                    
                    if warning_msg:
                        st.warning(warning_msg)
                        
                    if weights and isinstance(perf, dict):
                        col_w, col_p = st.columns([2, 1])
                        with col_w:
                            st.write("**İdeal Dağılım Ağırlıkları:**")
                            weight_df = pd.DataFrame(list(weights.items()), columns=['Hisse', 'Ağırlık'])
                            weight_df['Ağırlık (%)'] = (weight_df['Ağırlık'] * 100).round(2)
                            st.dataframe(weight_df[['Hisse', 'Ağırlık (%)']].style.format({"Ağırlık (%)": "{:.2f}%"}))
                        with col_p:
                            st.write("**Beklenen Yıllık Performans:**")
                            st.metric("Yıllık Beklenen Getiri", f"%{perf['expected_return']*100:.2f}")
                            st.metric("Yıllık Volatilite (Risk)", f"%{perf['volatility']*100:.2f}")
                            st.metric("Sharpe Oranı", f"{perf['sharpe_ratio']:.2f}", help="1'in üzeri iyidir. Riske göre getiriyi ölçer.")
                    else:
                        st.error(str(perf))
                        
    # --- DCF MODEL UI ---
    st.markdown("---")
    with st.expander("📉 Tekli Hisse İndirgenmiş Nakit Akımları (DCF) Hesaplayıcı"):
        st.markdown("Seçtiğiniz bir hissenin güncel Serbest Nakit Akımı, Nakit Varlıkları ve Borçları yfinance üzerinden anlık çekilerek 10 yıllık nakit akımı projeksiyonu (DCF) ile Gerçek Değeri (Intrinsic Value) hesaplanır.")
        
        ca, cb, cc, cd = st.columns(4)
        with ca:
            dcf_ticker = st.text_input("DCF Hisse Kodu (Örn: THYAO)", key="dcf_ticker").upper()
        with cb:
            dcf_g1 = st.number_input("1-5 Yıllık Büyüme Beklentisi (%)", min_value=-50.0, max_value=300.0, value=25.0, step=1.0)
        with cc:
            dcf_g2 = st.number_input("6-10 Yıllık Büyüme Beklentisi (%)", min_value=-50.0, max_value=300.0, value=15.0, step=1.0)
        with cd:
            dcf_wacc = st.number_input("İndirgeme Oranı / WACC (%)", min_value=1.0, max_value=100.0, value=35.0, step=1.0)
            
        if st.button("DCF Adil Değerini Hesapla", type="primary", key="btn_dcf"):
            if not dcf_ticker.strip():
                st.warning("Lütfen bir hisse kodu girin.")
            else:
                with st.spinner(f"{dcf_ticker} için bilanço verileri çekiliyor ve DCF hesaplanıyor..."):
                    from dcf_model import calculate_dcf
                    iv, cp, details, err = calculate_dcf(
                        ticker=dcf_ticker,
                        growth_rate_1_5=dcf_g1 / 100.0,
                        growth_rate_6_10=dcf_g2 / 100.0,
                        discount_rate=dcf_wacc / 100.0
                    )
                    
                    if err:
                        st.error(err)
                    else:
                        st.success("DCF Hesaplaması Tamamlandı!")
                        c1, c2, c3 = st.columns(3)
                        c1.metric("Güncel Fiyat", f"₺{cp:,.2f}")
                        
                        pot = ((iv - cp) / cp) * 100
                        c2.metric("DCF Adil Değer (Intrinsic Value)", f"₺{iv:,.2f}", f"{pot:,.2f}% Potansiyel", delta_color="normal")
                        
                        with st.expander("Hesaplama Detayları (₺)"):
                            det_df = pd.DataFrame(list(details.items()), columns=['Kalem', 'Değer'])
                            det_df['Değer'] = det_df['Değer'].apply(lambda x: f"₺{x:,.0f}" if isinstance(x, (int, float)) else x)
                            st.table(det_df.set_index('Kalem'))
                            
    st.markdown("---")
    
    # Q1 Bilanço Sezonu Bilgi Banner'ı
    if 'Bilanço Güncelliği' in df_filtered.columns:
        total = len(df_filtered)
        guncel_count = (df_filtered['Bilanço Güncelliği'] == 'Güncel').sum()
        onceki_count = (df_filtered['Bilanço Güncelliği'] == 'Önceki').sum()
        eski_count = (df_filtered['Bilanço Güncelliği'] == 'Eski').sum()
        
        if onceki_count > 0 or eski_count > 0:
            st.info(
                f"📋 **Bilanço Güncellik Durumu:** "
                f"🟢 {guncel_count} hisse güncel çeyrek bilançosu açıklamış | "
                f"🟠 {onceki_count} hisse henüz önceki çeyrek verileriyle gösteriliyor | "
                f"🔴 {eski_count} hisse 2+ çeyrek eski bilanço verileri kullanıyor. "
                f"Güncel olmayan hisselerin F/K bazlı hedef fiyatları TTM normalizasyonu ile yıllıklaştırılmıştır."
            )
        
    st.subheader(f"📊 Değerleme Tablosu ({len(df_filtered)} Hisse)")
    
    if show_minervini:
        if 'Minervini_Uyumlu' in df_filtered.columns:
            df_filtered = df_filtered[df_filtered['Minervini_Uyumlu'] == True]
            st.success(f"Minervini Şablonuna Uyan Sadece {len(df_filtered)} Hisse Bulundu.")
    
    # Select columns to display
    display_cols = [
        'Kod', 'Sektör', 'Son Dönem', 'Bilanço Güncelliği', 'Kapanış (TL)', 'F/K', 'PEG', 'PD/DD', 
        'Operasyonel Skor', 'Graham Skoru', 'Potansiyel Getiri (%)',
        'Halka Açıklık (%)', 'Temettü Verimi (%)',
        'Brüt Marj (%)', 'FAVÖK Marjı (%)', 'Net Kar Marjı (%)',
        'FAVÖK Yıllık Büyüme (%)', 'Net Kar Yıllık Büyüme (%)',
        'Net Borç', 'RSI (14)', 'MA200 Uzaklık (%)', 'Graham Sayısı',
        'Nihai Hedef Fiyat'
    ]
    
    if show_minervini:
        display_cols.insert(7, 'MA50')
        display_cols.insert(8, 'MA150')
        display_cols.insert(9, '52 Haftalık Zirve')
        display_cols.insert(10, '52 Haftalık Dip')
        
    # Sadece mevcut olan kolonları görüntüle (eski önbelleklerde hata vermemesi için)
    display_cols = [col for col in display_cols if col in df_filtered.columns]
    
    df_display = df_filtered[display_cols].copy()
    
    # URL kolonunu oluştur (TradingView'e doğrudan tıklanabilmesi için)
    df_display['Kod'] = df_display['Kod'].apply(lambda x: f"https://www.tradingview.com/chart/?symbol=BIST:{x}")
    
    # Kod sütununu sola sabitlemek için index yap
    df_display.set_index('Kod', inplace=True)
    
    # Formatter for Streamlit Dataframe
    def color_potential(val):
        color = 'green' if val > 0 else 'red'
        return f'color: {color}; font-weight: bold;'
        
    def color_rsi(val):
        if pd.isna(val) or val == 'Belirsiz': return ''
        if float(val) < RSI_OVERSOLD: return 'color: green; font-weight: bold;'
        if float(val) > RSI_OVERBOUGHT: return 'color: red; font-weight: bold;'
        return ''
        
    def color_ma200(val):
        if pd.isna(val) or val == 'Belirsiz': return ''
        if float(val) < 0: return 'color: green;' # Altında (ucuz)
        if float(val) > 0: return 'color: red;'   # Üstünde (pahalı)
        return ''
        
    def color_graham(val):
        if pd.isna(val): return ''
        score = int(val)
        if score >= GRAHAM_SCORE_EXCELLENT: return 'color: white; background-color: darkgreen; font-weight: bold;'
        if score >= GRAHAM_SCORE_GOOD: return 'color: green; font-weight: bold;'
        if score <= GRAHAM_SCORE_POOR: return 'color: red;'
        return ''
        
    def color_halka_aciklik(val):
        if pd.isna(val): return ''
        if val < HALKA_ACIKLIK_LOW: return 'color: orange; font-weight: bold;'
        if HALKA_ACIKLIK_LOW <= val <= HALKA_ACIKLIK_IDEAL_MAX: return 'color: green; font-weight: bold;'
        if HALKA_ACIKLIK_IDEAL_MAX < val <= HALKA_ACIKLIK_HIGH: return 'color: #DAA520;'
        if val > HALKA_ACIKLIK_HIGH: return 'color: red; font-weight: bold;'
        return ''
        
    def color_takas_change(val):
        if pd.isna(val): return ''
        if val > TAKAS_CHANGE_STRONG: return 'color: white; background-color: darkgreen; font-weight: bold;'
        if val > 0: return 'color: green; font-weight: bold;'
        if val < -TAKAS_CHANGE_STRONG: return 'color: white; background-color: darkred; font-weight: bold;'
        if val < 0: return 'color: red; font-weight: bold;'
        return ''
        
    # Sütunları daraltmak ve biçimlendirmek için Column Config
    column_widths = {
        "Kod": st.column_config.LinkColumn("Kod", width="small", display_text=r"https://www\.tradingview\.com/chart/\?symbol=BIST:(.*)"),
        "Sektör": st.column_config.TextColumn("Sektör", width="small"),
        "Son Dönem": st.column_config.TextColumn("Dönem", width="small"),
        "Bilanço Güncelliği": st.column_config.TextColumn("Güncellik", width="small"),
        "Kapanış (TL)": st.column_config.NumberColumn("Fiyat (TL)", width="small"),
        "F/K": st.column_config.NumberColumn("F/K", width="small"),
        "PEG": st.column_config.NumberColumn("PEG", width="small", help="F/K / Net Kar Büyümesi. 1'in altı ucuz kabul edilir."),
        "PD/DD": st.column_config.NumberColumn("PD/DD", width="small"),
        "RSI (14)": st.column_config.NumberColumn("RSI", width="small"),
        "MA200 Uzaklık (%)": st.column_config.NumberColumn("MA200 Uzaklık", width="small"),
        "MA50": st.column_config.NumberColumn("MA50", width="small"),
        "MA150": st.column_config.NumberColumn("MA150", width="small"),
        "52 Haftalık Zirve": st.column_config.NumberColumn("52H Zirve", width="small"),
        "52 Haftalık Dip": st.column_config.NumberColumn("52H Dip", width="small"),
        "Graham Skoru": st.column_config.NumberColumn("Graham Skoru (10)", width="small"),
        "Graham Sayısı": st.column_config.NumberColumn("Graham Say. (TL)", width="small"),
        "Hedef Fiyat (F/K)": st.column_config.NumberColumn("HF (F/K)", width="small"),
        "Hedef Fiyat (PD/DD)": st.column_config.NumberColumn("HF (PD/DD)", width="small"),
        "Hedef Fiyat (ROE)": st.column_config.NumberColumn("HF (ROE)", width="small"),
        "Hedef Fiyat (BIST Ort.)": st.column_config.NumberColumn("HF (BIST Ort.)", width="small"),
        "Hedef Fiyat (Sektör PD/DD)": st.column_config.NumberColumn("HF (Sektör)", width="small"),
        "Nihai Hedef Fiyat": st.column_config.NumberColumn("Nihai Hedef Fiyat", width="small"),
        "Potansiyel Getiri (%)": st.column_config.NumberColumn("Potansiyel", width="small"),
        "Halka Açıklık (%)": st.column_config.NumberColumn("Halka Açıklık (%)", width="small"),
        "Yabancı Payı (%)": st.column_config.NumberColumn("Yabancı Payı (%)", width="small"),
        "Takas (7G Değişim %)": st.column_config.NumberColumn("Takas (7G)", width="small"),
        "Takas (30G Değişim %)": st.column_config.NumberColumn("Takas (30G)", width="small"),
        "Takas (90G Değişim %)": st.column_config.NumberColumn("Takas (90G)", width="small"),
        "Temettü Verimi (%)": st.column_config.NumberColumn("Temettü (%)", width="small"),
    }
    
    # Styling the dataframe safely
    styled_df = df_display.style
    
    # Custom styling for Operational Score
    def color_op_score(val):
        if pd.isna(val): return ''
        if val >= OP_SCORE_EXCELLENT: return 'color: white; background-color: #2E7D32; font-weight: bold;'
        if val >= OP_SCORE_GOOD: return 'color: #4CAF50; font-weight: bold;'
        if val <= OP_SCORE_POOR: return 'color: #D32F2F;'
        return ''

    def color_growth(val):
        if pd.isna(val): return ''
        if val > GROWTH_STRONG_COLOR_THRESHOLD: return 'color: #2E7D32; font-weight: bold;'
        if val > 0: return 'color: #4CAF50;'
        if val < 0: return 'color: #D32F2F;'
        return ''
    
    def color_freshness(val):
        if pd.isna(val) or val == 'Belirsiz': return 'color: #888;'
        if val == 'Güncel': return f'color: {FRESHNESS_CURRENT_COLOR}; font-weight: bold;'
        if val == 'Önceki': return f'color: {FRESHNESS_PREVIOUS_COLOR}; font-weight: bold;'
        if val == 'Eski': return f'color: {FRESHNESS_STALE_COLOR}; font-weight: bold;'
        return ''
    
    DIVIDEND_YIELD_HIGH = 5  # %5 üzeri = yüksek temetü
    DIVIDEND_YIELD_GOOD = 2  # %2 üzeri = makul temetü
    
    def color_dividend(val):
        if pd.isna(val): return ''
        if val >= DIVIDEND_YIELD_HIGH: return 'color: #2E7D32; font-weight: bold;'
        if val >= DIVIDEND_YIELD_GOOD: return 'color: #4CAF50;'
        if val > 0: return 'color: #888;'
        return ''
    
    def color_peg(val):
        if pd.isna(val): return ''
        if val <= 1.0: return 'color: #2E7D32; font-weight: bold;'
        if val > 2.0: return 'color: #D32F2F;'
        return ''
    
    # Define styling rules
    style_rules = [
        (color_potential, ['Potansiyel Getiri (%)']),
        (color_rsi, ['RSI (14)']),
        (color_ma200, ['MA200 Uzaklık (%)']),
        (color_graham, ['Graham Skoru']),
        (color_op_score, ['Operasyonel Skor']),
        (color_growth, ['FAVÖK Yıllık Büyüme (%)', 'Net Kar Yıllık Büyüme (%)']),
        (color_halka_aciklik, ['Halka Açıklık (%)']),
        (color_takas_change, ['Takas (7G Değişim %)', 'Takas (30G Değişim %)', 'Takas (90G Değişim %)']),
        (color_freshness, ['Bilanço Güncelliği']),
        (color_dividend, ['Temettü Verimi (%)']),
        (color_peg, ['PEG']),
    ]
    
    for func, cols in style_rules:
        present_cols = [c for c in cols if c in df_display.columns]
        if present_cols:
            styled_df = styled_df.map(func, subset=present_cols)
            
    format_dict = {
        "Kapanış (TL)": "₺{:.2f}",
        "Nihai Hedef Fiyat": "₺{:.2f}",
        "Graham Sayısı": "₺{:.2f}",
        "Potansiyel Getiri (%)": "{:.2f}%",
        "MA200 Uzaklık (%)": "{:.2f}%",
        "RSI (14)": "{:.2f}",
        "F/K": "{:.2f}",
        "PEG": "{:.2f}",
        "PD/DD": "{:.2f}",
        "Brüt Marj (%)": "{:.1f}%",
        "FAVÖK Marjı (%)": "{:.1f}%",
        "Net Kar Marjı (%)": "{:.1f}%",
        "FAVÖK Yıllık Büyüme (%)": "{:+.1f}%",
        "Net Kar Yıllık Büyüme (%)": "{:+.1f}%",
        "Net Borç": "₺{:,.0f}",
        "Operasyonel Skor": "{:d}/10",
        "Halka Açıklık (%)": "%{:.1f}",
        "Temettü Verimi (%)": "%{:.2f}",
    }
    
    # Apply format only to columns that exist in df_display
    present_formats = {k: v for k, v in format_dict.items() if k in df_display.columns}
    styled_df = styled_df.format(present_formats)

    # --- Tabs for Table and Grid View ---
    tab1, tab2, tab3 = st.tabs(["📊 Tablo Görünümü", "🔍 Hisse Detay (Drill-down)", "🖼️ Grafik Görünümü (Grid)"])
    
    with tab1:
        st.dataframe(
            styled_df,
            use_container_width=True,
            height=600,
            column_config=column_widths
        )
        
    with tab2:
        # =================== HISSE DETAY (DRILL-DOWN) PANELI ===================
        st.markdown("### 🔍 Hisse Detay Analizi")
        st.caption("Aşağıdan bir hisse seçerek detaylı bilanço özeti, sektör karşılaştırması, grafik ve DCF hesaplamasına erişin.")
        
        ticker_list = df_filtered['Kod'].tolist()
        if not ticker_list:
            st.info("Gösterilecek hisse bulunamadı. Lütfen filtreleri kontrol edin.")
        else:
            selected_ticker = st.selectbox(
                "Hisse Seçin",
                options=ticker_list,
                index=0,
                key="detail_ticker_select"
            )
            
            if selected_ticker:
                stock_row = df_filtered[df_filtered['Kod'] == selected_ticker].iloc[0]
                stock_sector = stock_row.get('Sektör', 'Unknown')
                
                # --------- Üst Bilgi Çubuğu ---------
                st.markdown(f"## {selected_ticker} — {stock_sector}")
                
                m1, m2, m3, m4, m5, m6 = st.columns(6)
                m1.metric("💰 Fiyat", f"₺{stock_row.get('Kapanış (TL)', 0):,.2f}")
                m2.metric("🎯 Nihai Hedef", f"₺{stock_row.get('Nihai Hedef Fiyat', 0):,.2f}")
                
                pot = stock_row.get('Potansiyel Getiri (%)', 0)
                m3.metric("📈 Potansiyel", f"%{pot:,.1f}", delta=f"{pot:+.1f}%")
                m4.metric("📊 F/K", f"{stock_row.get('F/K', 0):,.2f}")
                m5.metric("📖 PD/DD", f"{stock_row.get('PD/DD', 0):,.2f}")
                
                div_yield = stock_row.get('Temettü Verimi (%)', 0)
                m6.metric("🌾 Temettü", f"%{div_yield:,.2f}" if pd.notna(div_yield) else "Yok")
                
                # --------- Detay Panelleri ---------
                detail_tab1, detail_tab2, detail_tab3, detail_tab4, detail_tab5 = st.tabs([
                    "📊 Bilanço Özeti", "🛡️ Sektör Karşılaştırma", "📉 TradingView Grafik", "💵 Hızlı DCF", "📰 Haberler & Sentiment"
                ])
                
                # ========== TAB 1: BİLANÇO ÖZETİ ==========
                with detail_tab1:
                    st.markdown("#### Temel Değerleme Metrikleri")
                    
                    # Hedef Fiyat Tablosu
                    hf_data = {
                        'Yöntem': ['F/K Bazlı', 'PD/DD Bazlı', 'ROE Bazlı', 'BİST Ort.', 'Sektör PD/DD', 'Graham Sayısı', 'Nihai Hedef'],
                        'Hedef Fiyat (₺)': [
                            stock_row.get('Hedef Fiyat (F/K)', np.nan),
                            stock_row.get('Hedef Fiyat (PD/DD)', np.nan),
                            stock_row.get('Hedef Fiyat (ROE)', np.nan),
                            stock_row.get('Hedef Fiyat (BIST Ort.)', np.nan),
                            stock_row.get('Hedef Fiyat (Sektör PD/DD)', np.nan),
                            stock_row.get('Graham Sayısı', np.nan),
                            stock_row.get('Nihai Hedef Fiyat', np.nan),
                        ]
                    }
                    hf_df = pd.DataFrame(hf_data)
                    kapanış = stock_row.get('Kapanış (TL)', 0)
                    hf_df['Potansiyel (%)'] = ((hf_df['Hedef Fiyat (₺)'] - kapanış) / kapanış * 100).round(1)
                    
                    st.dataframe(
                        hf_df.style.format({"Hedef Fiyat (₺)": "₺{:.2f}", "Potansiyel (%)": "{:+.1f}%"}),
                        use_container_width=True,
                        hide_index=True
                    )
                    
                    st.markdown("#### Operasyonel & Finansal Göstergeler")
                    fc1, fc2 = st.columns(2)
                    
                    with fc1:
                        fin_metrics = {
                            'Gösterge': ['Graham Skoru', 'Operasyonel Skor', 'PEG Rasyosu', 'RSI (14)', 'MA200 Uzaklık (%)', 
                                         'Cari Oran', 'Borç/Özkaynak', 'Halka Açıklık (%)'],
                            'Değer': [
                                f"{stock_row.get('Graham Skoru', 0)}/10",
                                f"{stock_row.get('Operasyonel Skor', 0)}/10",
                                f"{stock_row.get('PEG', 0):.2f}" if pd.notna(stock_row.get('PEG')) else 'N/A',
                                f"{stock_row.get('RSI (14)', 0):.1f}",
                                f"%{stock_row.get('MA200 Uzaklık (%)', 0):.1f}",
                                f"{stock_row.get('Cari Oran', 0):.2f}" if pd.notna(stock_row.get('Cari Oran')) else 'N/A',
                                f"{stock_row.get('Borç/Özkaynak', 0):.2f}" if pd.notna(stock_row.get('Borç/Özkaynak')) else 'N/A',
                                f"%{stock_row.get('Halka Açıklık (%)', 0):.1f}" if pd.notna(stock_row.get('Halka Açıklık (%)')) else 'N/A',
                            ]
                        }
                        st.dataframe(pd.DataFrame(fin_metrics), use_container_width=True, hide_index=True)
                    
                    with fc2:
                        growth_metrics = {
                            'Gösterge': ['Brüt Marj (%)', 'FAVÖK Marjı (%)', 'Net Kar Marjı (%)',
                                         'FAVÖK Büyüme (%)', 'Net Kar Büyüme (%)', 'Net Borç', 'Temettü Verimi (%)'],
                            'Değer': [
                                f"%{stock_row.get('Brüt Marj (%)', 0):.1f}" if pd.notna(stock_row.get('Brüt Marj (%)')) else 'N/A',
                                f"%{stock_row.get('FAVÖK Marjı (%)', 0):.1f}" if pd.notna(stock_row.get('FAVÖK Marjı (%)')) else 'N/A',
                                f"%{stock_row.get('Net Kar Marjı (%)', 0):.1f}" if pd.notna(stock_row.get('Net Kar Marjı (%)')) else 'N/A',
                                f"%{stock_row.get('FAVÖK Yıllık Büyüme (%)', 0):+.1f}" if pd.notna(stock_row.get('FAVÖK Yıllık Büyüme (%)')) else 'N/A',
                                f"%{stock_row.get('Net Kar Yıllık Büyüme (%)', 0):+.1f}" if pd.notna(stock_row.get('Net Kar Yıllık Büyüme (%)')) else 'N/A',
                                f"₺{stock_row.get('Net Borç', 0):,.0f}" if pd.notna(stock_row.get('Net Borç')) else 'N/A',
                                f"%{div_yield:.2f}" if pd.notna(div_yield) else 'N/A',
                            ]
                        }
                        st.dataframe(pd.DataFrame(growth_metrics), use_container_width=True, hide_index=True)
                    
                    # Bilanço Dönemi Bilgisi
                    period = stock_row.get('Son Dönem', 'Belirsiz')
                    freshness = stock_row.get('Bilanço Güncelliği', 'Belirsiz')
                    ann_factor = stock_row.get('_annualization_factor', 1)
                    if ann_factor > 1:
                        st.warning(f"⚠️ Bu hisse **{period}** dönemi bilançosu kullanıyor. EPS, **{ann_factor:.1f}x** çarpanla yıllıklaştırılmıştır (TTM normalizasyonu).")
                    else:
                        st.success(f"✅ Bu hisse **{period}** yıl sonu bilançosunu kullanmaktadır. Yıllıklaştırma gerekmemektedir.")
                
                # ========== TAB 2: SEKTÖR KARŞILAŞTIRMA (RADAR CHART) ==========
                with detail_tab2:
                    st.markdown(f"#### 🛡️ {selected_ticker} vs {stock_sector} Sektör Ortalaması")
                    
                    # Sektördeki diğer hisseler
                    sector_peers = df_filtered[df_filtered['Sektör'] == stock_sector]
                    
                    if len(sector_peers) < 2:
                        st.info(f"{stock_sector} sektöründe karşılaştırılacak yeterli hisse yok (minimum 2 gerekli).")
                    else:
                        # Radar chart için metrikler
                        RADAR_METRICS = {
                            'F/K Uygunluğu': 'F/K',
                            'PD/DD Uygunluğu': 'PD/DD',
                            'Graham Skoru': 'Graham Skoru',
                            'Op. Skor': 'Operasyonel Skor',
                            'Brüt Marj': 'Brüt Marj (%)',
                            'Net Kar Marjı': 'Net Kar Marjı (%)',
                            'Potansiyel Getiri': 'Potansiyel Getiri (%)',
                            'Temettü Verimi': 'Temettü Verimi (%)',
                        }
                        
                        # Her metrik için hisse ve sektör ortalaması hesapla (0-100 normalize)
                        stock_values = []
                        sector_values = []
                        labels = []
                        
                        for label, col in RADAR_METRICS.items():
                            if col not in sector_peers.columns:
                                continue
                            
                            col_data = pd.to_numeric(sector_peers[col], errors='coerce').dropna()
                            stock_val = pd.to_numeric(stock_row.get(col, np.nan), errors='coerce') if col in stock_row.index else np.nan
                            
                            if pd.isna(stock_val) or col_data.empty:
                                continue
                            
                            col_min = col_data.min()
                            col_max = col_data.max()
                            col_mean = col_data.mean()
                            
                            # F/K ve PD/DD için ters normalize (düşük değer daha iyi)
                            if col in ('F/K', 'PD/DD'):
                                if col_max != col_min:
                                    norm_stock = ((col_max - stock_val) / (col_max - col_min)) * 100
                                    norm_sector = ((col_max - col_mean) / (col_max - col_min)) * 100
                                else:
                                    norm_stock = 50
                                    norm_sector = 50
                            else:
                                if col_max != col_min:
                                    norm_stock = ((stock_val - col_min) / (col_max - col_min)) * 100
                                    norm_sector = ((col_mean - col_min) / (col_max - col_min)) * 100
                                else:
                                    norm_stock = 50
                                    norm_sector = 50
                            
                            # Clamp 0-100
                            norm_stock = max(0, min(100, norm_stock))
                            norm_sector = max(0, min(100, norm_sector))
                            
                            labels.append(label)
                            stock_values.append(round(norm_stock, 1))
                            sector_values.append(round(norm_sector, 1))
                        
                        if len(labels) >= 3:
                            # SVG Radar Chart
                            radar_html = _generate_radar_chart_svg(
                                labels, stock_values, sector_values,
                                selected_ticker, f"{stock_sector} Ort."
                            )
                            components.html(radar_html, height=520)
                        else:
                            st.warning("Radar chart için yeterli metrik bulunamadı.")
                        
                        # Sektör Sıralama Tablosu
                        st.markdown(f"#### 🏆 {stock_sector} Sektör Sıralaması")
                        peer_cols = ['Kod', 'Kapanış (TL)', 'F/K', 'PD/DD', 'Graham Skoru', 
                                     'Operasyonel Skor', 'Potansiyel Getiri (%)', 'Temettü Verimi (%)']
                        peer_display_cols = [c for c in peer_cols if c in sector_peers.columns]
                        peer_df = sector_peers[peer_display_cols].copy()
                        peer_df = peer_df.sort_values('Potansiyel Getiri (%)', ascending=False)
                        
                        # Mevcut hisseyi vurgula — seçili satırların index'lerini kaydet
                        selected_indices = set(peer_df[peer_df['Kod'] == selected_ticker].index.tolist())
                        
                        def highlight_selected(row):
                            if row.name in selected_indices:
                                return ['background-color: rgba(90, 31, 138, 0.15); font-weight: bold;'] * len(row)
                            return [''] * len(row)
                        
                        st.dataframe(
                            peer_df.style.apply(highlight_selected, axis=1).format({
                                "Kapanış (TL)": "₺{:.2f}",
                                "F/K": "{:.2f}",
                                "PD/DD": "{:.2f}",
                                "Potansiyel Getiri (%)": "{:+.1f}%",
                                "Temettü Verimi (%)": "%{:.2f}",
                            }),
                            use_container_width=True,
                            hide_index=True
                        )
                
                # ========== TAB 3: TRADINGVIEW GRAİK ==========
                with detail_tab3:
                    st.markdown(f"#### 📉 {selected_ticker} — 6 Aylık Fiyat Grafiği")
                    with st.spinner(f"{selected_ticker} fiyat verisi indiriliyor..."):
                        try:
                            detail_hist = yf.download(f"{selected_ticker}.IS", period=CHART_HISTORY_PERIOD, interval="1d", progress=False)
                            if detail_hist is not None and not detail_hist.empty:
                                # Flatten multi-index if present
                                if isinstance(detail_hist.columns, pd.MultiIndex):
                                    detail_hist.columns = [col[0] if isinstance(col, tuple) else col for col in detail_hist.columns]
                                
                                ohlc = detail_hist[['Open', 'High', 'Low', 'Close']].dropna().sort_index()
                                if not ohlc.empty:
                                    chart_points = []
                                    for date, row in ohlc.iterrows():
                                        chart_points.append({
                                            "time": date.strftime('%Y-%m-%d'),
                                            "open": float(row['Open']),
                                            "high": float(row['High']),
                                            "low": float(row['Low']),
                                            "close": float(row['Close'])
                                        })
                                    tv_html = render_lightweight_chart(selected_ticker, json.dumps(chart_points), f"detail_chart_{selected_ticker}")
                                    components.html(tv_html, height=420)
                                    st.caption(f"{len(chart_points)} veri noktası yüklendi.")
                                else:
                                    st.warning("Fiyat verisi bulunamadı.")
                            else:
                                st.warning(f"{selected_ticker} için fiyat verisi çekilemedi.")
                        except Exception as e:
                            st.error(f"Grafik yüklenirken hata: {str(e)}")
                
                # ========== TAB 4: HIZLI DCF ==========
                with detail_tab4:
                    st.markdown(f"#### 💵 {selected_ticker} — Hızlı DCF Hesaplaması")
                    
                    dcf_c1, dcf_c2, dcf_c3 = st.columns(3)
                    with dcf_c1:
                        detail_g1 = st.number_input("1-5 Yıl Büyüme (%)", min_value=-50.0, max_value=300.0, value=25.0, step=1.0, key=f"detail_dcf_g1_{selected_ticker}")
                    with dcf_c2:
                        detail_g2 = st.number_input("6-10 Yıl Büyüme (%)", min_value=-50.0, max_value=300.0, value=15.0, step=1.0, key=f"detail_dcf_g2_{selected_ticker}")
                    with dcf_c3:
                        detail_wacc = st.number_input("WACC (%)", min_value=1.0, max_value=100.0, value=35.0, step=1.0, key=f"detail_dcf_wacc_{selected_ticker}")
                    
                    if st.button(f"{selected_ticker} DCF Hesapla", type="primary", key=f"btn_detail_dcf_{selected_ticker}"):
                        with st.spinner(f"{selected_ticker} için DCF hesaplanıyor..."):
                            from dcf_model import calculate_dcf
                            iv, cp, details, err = calculate_dcf(
                                ticker=selected_ticker,
                                growth_rate_1_5=detail_g1 / 100.0,
                                growth_rate_6_10=detail_g2 / 100.0,
                                discount_rate=detail_wacc / 100.0
                            )
                            
                            if err:
                                st.error(err)
                            else:
                                dc1, dc2 = st.columns(2)
                                dcf_pot = ((iv - cp) / cp) * 100
                                dc1.metric("Güncel Fiyat", f"₺{cp:,.2f}")
                                dc2.metric("DCF Adil Değer", f"₺{iv:,.2f}", f"{dcf_pot:+.1f}% Potansiyel")
                                
                                with st.expander("Hesaplama Detayları"):
                                    det_df = pd.DataFrame(list(details.items()), columns=['Kalem', 'Değer'])
                                    det_df['Değer'] = det_df['Değer'].apply(lambda x: f"₺{x:,.0f}" if isinstance(x, (int, float)) else x)
                                    st.table(det_df.set_index('Kalem'))

                # ========== TAB 5: HABERLER & SENTIMENT ==========
                with detail_tab5:
                    st.markdown(f"#### 📰 {selected_ticker} Haber Akışı ve Duyarlılık Analizi")
                    
                    with st.spinner("Haberler çekiliyor ve analiz ediliyor..."):
                        news_items = fetch_stock_news(selected_ticker)
                        
                        if not news_items:
                            st.info("Bu hisse için yakın zamanda önemli bir haber bulunamadı.")
                        else:
                            score, summary, css_class = get_overall_sentiment(news_items)
                            
                            # Sentiment Gauge/Metric
                            sc1, sc2 = st.columns([1, 2])
                            with sc1:
                                delta_val = score - 50
                                st.metric("Genel Duyarlılık Skoru", f"{score}/100", delta=f"{delta_val:+.1f}", delta_color="normal")
                            with sc2:
                                st.markdown(f"**Özet:** {summary}")
                                if css_class == "bullish":
                                    st.success("Haber akışı hisse üzerinde pozitif bir algı yaratıyor.")
                                elif css_class == "bearish":
                                    st.error("Haber akışı hisse üzerinde negatif bir baskı oluşturabilir.")
                                else:
                                    st.info("Haber akışı şu an için nötr veya dengeli bir seyir izliyor.")
                            
                            st.markdown("---")
                            st.subheader("Son Haberler")
                            
                            for item in news_items:
                                with st.container():
                                    c1, c2 = st.columns([0.1, 0.9])
                                    with c1:
                                        if item['score'] > 0:
                                            st.markdown("🟢")
                                        elif item['score'] < 0:
                                            st.markdown("🔴")
                                        else:
                                            st.markdown("⚪")
                                    with c2:
                                        # Display Authority Badge
                                        if item.get('is_authority'):
                                            st.markdown("⭐ **[Otorite Kaynak]**")
                                        
                                        st.markdown(f"**[{item['title']}]({item['link']})**")
                                        st.caption(f"Kaynak: {item['source']} | Tarih: {item['published']}")
                                        if item['keywords']:
                                            st.caption(f"Anahtar Kelimeler: {', '.join(item['keywords'])}")
                                    st.markdown("")
    
    with tab3:
        st.markdown(f"### 📈 Filtrelenmiş İlk {min(GRID_MAX_TICKERS, len(df_filtered))} Hisse Grafiği")
        grid_tickers = df_filtered['Kod'].tolist()[:GRID_MAX_TICKERS]
        
        if not grid_tickers:
            st.info("Gösterilecek hisse bulunamadı. Lütfen filtreleri kontrol edin.")
        else:
            with st.spinner("Grafik verileri indiriliyor (yfinance)..."):
                # Batch download data for the 12 tickers
                yf_symbols = [f"{t}.IS" for t in grid_tickers]
                # Download 6 months of daily data
                hist_df = yf.download(yf_symbols, period=CHART_HISTORY_PERIOD, interval="1d", group_by='ticker', progress=False)
                
                # Create a grid
                rows = (len(grid_tickers) + GRID_COLUMNS - 1) // GRID_COLUMNS
                for r in range(rows):
                    cols = st.columns(GRID_COLUMNS)
                    for c in range(GRID_COLUMNS):
                        idx = r * GRID_COLUMNS + c
                        if idx < len(grid_tickers):
                            ticker = grid_tickers[idx]
                            t_yf = f"{ticker}.IS"
                            
                            with cols[c]:
                                st.write(f"**{ticker}**")
                                
                                # Data Extraction Logic
                                ticker_data = None
                                try:
                                    if isinstance(hist_df.columns, pd.MultiIndex):
                                        if t_yf in hist_df.columns.get_level_values(0):
                                            ticker_data = hist_df[t_yf]
                                    else:
                                        # Single ticker case (simple DataFrame)
                                        ticker_data = hist_df
                                except Exception:
                                    ticker_data = None

                                if ticker_data is not None and not ticker_data.empty:
                                    # Drop NaN rows specifically for OHLC columns
                                    ohlc_cols = ['Open', 'High', 'Low', 'Close']
                                    ticker_data = ticker_data[ohlc_cols].dropna()
                                    
                                    if not ticker_data.empty:
                                        # Sort by date just in case
                                        ticker_data = ticker_data.sort_index()
                                        
                                        # Convert to Lightweight Charts format
                                        chart_points = []
                                        for date, row in ticker_data.iterrows():
                                            chart_points.append({
                                                "time": date.strftime('%Y-%m-%d'),
                                                "open": float(row['Open']),
                                                "high": float(row['High']),
                                                "low": float(row['Low']),
                                                "close": float(row['Close'])
                                            })
                                        
                                        tv_html = render_lightweight_chart(ticker, json.dumps(chart_points), f"custom_chart_{ticker}")
                                        st.caption(f"{len(chart_points)} veri noktası yüklendi.")
                                        components.html(tv_html, height=410)
                                    else:
                                        st.caption(f"{ticker} için son 6 ayda fiyat verisi bulunamadı.")
                                else:
                                    st.caption(f"{ticker} verisi çekilemedi (yfinance).")
    
