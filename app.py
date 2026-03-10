import streamlit as st
import pandas as pd
import os
import yfinance as yf
import json
from datetime import datetime
from dotenv import load_dotenv
from data_fetcher import fetch_bist_fundamentals
from calculator import calculate_fair_values
from portfolio_opt import optimize_portfolio
import streamlit.components.v1 as components

# Load environment variables
load_dotenv()

def load_env_watchlists():
    watchlists = {}
    for i in range(1, 6):
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
            min_7g = st.number_input("Min. 7G Değişim (%)", value=-10.0, step=0.1)
        with tc3:
            min_30g = st.number_input("Min. 30G Değişim (%)", value=-20.0, step=0.1)
        with tc4:
            min_90g = st.number_input("Min. 90G Değişim (%)", value=-30.0, step=0.1)
        
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
        df_filtered = df_filtered[df_filtered['Yabancı Payı (%)'] >= min_yabanci]
    if 'Takas (7G Değişim %)' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['Takas (7G Değişim %)'] >= min_7g]
    if 'Takas (30G Değişim %)' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['Takas (30G Değişim %)'] >= min_30g]
    if 'Takas (90G Değişim %)' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['Takas (90G Değişim %)'] >= min_90g]
            
    # --- Portfolio Optimization UI ---
    st.markdown("---")
    with st.expander("🤖 Yapay Zeka ile Portföy Optimizasyonu (Markowitz)"):
        st.markdown("İdeal getiri ve risk oranını (Maksimum Sharpe) yakalamak için **tabloda filtrelenmiş olan** hisselerin son 2 yıllık fiyat dalgalanması (riski) ve güncel **Bilanço Potansiyel Getirisi** kullanılarak en uygun ağırlıklar hesaplanacaktır.")
        
        opt_tickers = df_filtered['Kod'].tolist()
        if len(opt_tickers) < 2:
            st.warning("Optimizasyon için tabloda en az 2 hisse bulunmalıdır.")
        elif len(opt_tickers) > 60:
            st.warning(f"Tabloda {len(opt_tickers)} hisse var. Aşırı veri indirmesi API engeline takılabileceği ve çok yavaş çalışacağı için lütfen filtreleri kullanarak hisse sayısını en fazla 60'a düşürünüz. (Örn: Sektör seçin veya Potansiyel Getiriyi artırın)")
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
        
    st.subheader(f"📊 Değerleme Tablosu ({len(df_filtered)} Hisse)")
    
    if show_minervini:
        if 'Minervini_Uyumlu' in df_filtered.columns:
            df_filtered = df_filtered[df_filtered['Minervini_Uyumlu'] == True]
            st.success(f"Minervini Şablonuna Uyan Sadece {len(df_filtered)} Hisse Bulundu.")
    
    # Select columns to display
    display_cols = [
        'Kod', 'Sektör', 'Son Dönem', 'Kapanış (TL)', 'F/K', 'PD/DD', 'Halka Açıklık (%)',
        'Yabancı Payı (%)', 'Takas (7G Değişim %)', 'Takas (30G Değişim %)', 'Takas (90G Değişim %)',
        'RSI (14)', 'MA200 Uzaklık (%)', 'Graham Skoru', 'Graham Sayısı',
        'Hedef Fiyat (F/K)', 'Hedef Fiyat (PD/DD)', 'Hedef Fiyat (ROE)', 
        'Hedef Fiyat (BIST Ort.)', 'Hedef Fiyat (Sektör PD/DD)',
        'Nihai Hedef Fiyat', 'Potansiyel Getiri (%)'
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
        if float(val) < 30: return 'color: green; font-weight: bold;'
        if float(val) > 70: return 'color: red; font-weight: bold;'
        return ''
        
    def color_ma200(val):
        if pd.isna(val) or val == 'Belirsiz': return ''
        if float(val) < 0: return 'color: green;' # Altında (ucuz)
        if float(val) > 0: return 'color: red;'   # Üstünde (pahalı)
        return ''
        
    def color_graham(val):
        if pd.isna(val): return ''
        score = int(val)
        if score >= 8: return 'color: white; background-color: darkgreen; font-weight: bold;'
        if score >= 6: return 'color: green; font-weight: bold;'
        if score <= 3: return 'color: red;'
        return ''
        
    def color_halka_aciklik(val):
        if pd.isna(val): return ''
        if val < 15: return 'color: orange; font-weight: bold;' # Düşük likidite
        if 15 <= val <= 50: return 'color: green; font-weight: bold;' # İdeal aralık
        if 50 < val <= 80: return 'color: #DAA520;' # Altın sarısı (Biraz yüksek)
        if val > 80: return 'color: red; font-weight: bold;' # Çok yüksek
        return ''
        
    def color_takas_change(val):
        if pd.isna(val): return ''
        if val > 1.0: return 'color: white; background-color: darkgreen; font-weight: bold;'
        if val > 0: return 'color: green; font-weight: bold;'
        if val < -1.0: return 'color: white; background-color: darkred; font-weight: bold;'
        if val < 0: return 'color: red; font-weight: bold;'
        return ''
        
    # Sütunları daraltmak ve biçimlendirmek için Column Config
    column_widths = {
        "Kod": st.column_config.LinkColumn("Kod", width="small", display_text=r"https://www\.tradingview\.com/chart/\?symbol=BIST:(.*)"),
        "Sektör": st.column_config.TextColumn("Sektör", width="small"),
        "Son Dönem": st.column_config.TextColumn("Dönem", width="small"),
        "Kapanış (TL)": st.column_config.NumberColumn("Fiyat (TL)", width="small"),
        "F/K": st.column_config.NumberColumn("F/K", width="small"),
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
        "Takas (90G Değişim %)": st.column_config.NumberColumn("Takas (90G)", width="small")
    }
    
    # Styling the dataframe safely
    styled_df = df_display.style
    
    # Define styling rules
    style_rules = [
        (color_potential, ['Potansiyel Getiri (%)']),
        (color_rsi, ['RSI (14)']),
        (color_ma200, ['MA200 Uzaklık (%)']),
        (color_graham, ['Graham Skoru']),
        (color_halka_aciklik, ['Halka Açıklık (%)']),
        (color_takas_change, ['Takas (7G Değişim %)', 'Takas (30G Değişim %)', 'Takas (90G Değişim %)'])
    ]
    
    for func, cols in style_rules:
        present_cols = [c for c in cols if c in df_display.columns]
        if present_cols:
            styled_df = styled_df.map(func, subset=present_cols)
            
    format_dict = {
        "Kapanış (TL)": "₺{:.2f}",
        "Hedef Fiyat (F/K)": "₺{:.2f}",
        "Hedef Fiyat (PD/DD)": "₺{:.2f}",
        "Hedef Fiyat (ROE)": "₺{:.2f}",
        "Hedef Fiyat (BIST Ort.)": "₺{:.2f}",
        "Hedef Fiyat (Sektör PD/DD)": "₺{:.2f}",
        "Nihai Hedef Fiyat": "₺{:.2f}",
        "Graham Sayısı": "₺{:.2f}",
        "Potansiyel Getiri (%)": "{:.2f}%",
        "MA200 Uzaklık (%)": "{:.2f}%",
        "MA50": "₺{:.2f}",
        "MA150": "₺{:.2f}",
        "52 Haftalık Zirve": "₺{:.2f}",
        "52 Haftalık Dip": "₺{:.2f}",
        "RSI (14)": "{:.2f}",
        "F/K": "{:.2f}",
        "PD/DD": "{:.2f}",
        "Halka Açıklık (%)": "{:.2f}%",
        "Yabancı Payı (%)": "{:.2f}%",
        "Takas (7G Değişim %)": "{:+.2f}%",
        "Takas (30G Değişim %)": "{:+.2f}%",
        "Takas (90G Değişim %)": "{:+.2f}%"
    }
    
    # Apply format only to columns that exist in df_display
    present_formats = {k: v for k, v in format_dict.items() if k in df_display.columns}
    styled_df = styled_df.format(present_formats)

    # --- Tabs for Table and Grid View ---
    tab1, tab2 = st.tabs(["📊 Tablo Görünümü", "🖼️ Grafik Görünümü (Grid)"])
    
    with tab1:
        st.dataframe(
            styled_df,
            use_container_width=True,
            height=600,
            column_config=column_widths
        )
        
    with tab2:
        st.markdown(f"### 📈 Filtrelenmiş İlk {min(12, len(df_filtered))} Hisse Grafiği")
        grid_tickers = df_filtered['Kod'].tolist()[:12]
        
        if not grid_tickers:
            st.info("Gösterilecek hisse bulunamadı. Lütfen filtreleri kontrol edin.")
        else:
            with st.spinner("Grafik verileri indiriliyor (yfinance)..."):
                # Batch download data for the 12 tickers
                yf_symbols = [f"{t}.IS" for t in grid_tickers]
                # Download 6 months of daily data
                hist_df = yf.download(yf_symbols, period="6mo", interval="1d", group_by='ticker', progress=False)
                
                # Create a 4-column grid
                rows = (len(grid_tickers) + 3) // 4
                for r in range(rows):
                    cols = st.columns(4)
                    for c in range(4):
                        idx = r * 4 + c
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
    
