import streamlit as st
import pandas as pd
from data_fetcher import fetch_bist_fundamentals
from calculator import calculate_fair_values

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
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        min_potential = st.number_input("Minimum Potansiyel Getiri (%)", value=0.0)
    with col2:
        search_ticker = st.text_input("Hisse Kodu Ara (Örn: THYAO)").upper()
    with col3:
        # Get sector list dynamically from calculated dataframe
        all_sectors = sorted(df_calc['Sektör'].astype(str).unique().tolist())
        selected_sectors = st.multiselect("Sektör Seç", options=all_sectors, default=[])
    with col4:
        # Get periods dynamically
        all_periods = sorted(df_calc['Son Dönem'].dropna().astype(str).unique().tolist(), reverse=True)
        selected_periods = st.multiselect("Bilanço Dönemi Seç", options=all_periods, default=[])
        
    df_filtered = df_calc[df_calc['Potansiyel Getiri (%)'] >= min_potential]
    if search_ticker:
        df_filtered = df_filtered[df_filtered['Kod'].str.contains(search_ticker, case=False, na=False)]
    if selected_sectors:
        df_filtered = df_filtered[df_filtered['Sektör'].isin(selected_sectors)]
    if selected_periods:
        df_filtered = df_filtered[df_filtered['Son Dönem'].isin(selected_periods)]
        
    st.subheader(f"📊 Değerleme Tablosu ({len(df_filtered)} Hisse)")
    
    # Select columns to display
    display_cols = [
        'Kod', 'Sektör', 'Son Dönem', 'Bilanço Açıklanma Tarihi', 'Kapanış (TL)', 'F/K', 'PD/DD', 
        'RSI (14)', 'MA200 Uzaklık (%)', 'Graham Skoru',
        'Hedef Fiyat (F/K)', 'Hedef Fiyat (PD/DD)', 'Hedef Fiyat (ROE)', 
        'Hedef Fiyat (BIST Ort.)', 'Hedef Fiyat (Sektör PD/DD)',
        'Nihai Hedef Fiyat', 'Potansiyel Getiri (%)'
    ]
    df_display = df_filtered[display_cols].copy()
    
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
        
    # Sütunları daraltmak ve biçimlendirmek için Column Config
    column_widths = {
        "Kod": st.column_config.TextColumn("Kod", width="small"),
        "Sektör": st.column_config.TextColumn("Sektör", width="small"),
        "Son Dönem": st.column_config.TextColumn("Dönem", width="small"),
        "Bilanço Açıklanma Tarihi": st.column_config.TextColumn("Tarih", width="small"),
        "Kapanış (TL)": st.column_config.NumberColumn("Fiyat (TL)", width="small"),
        "F/K": st.column_config.NumberColumn("F/K", width="small"),
        "PD/DD": st.column_config.NumberColumn("PD/DD", width="small"),
        "RSI (14)": st.column_config.NumberColumn("RSI", width="small"),
        "MA200 Uzaklık (%)": st.column_config.NumberColumn("MA200 Uzaklık", width="small"),
        "Graham Skoru": st.column_config.NumberColumn("Graham Skoru (10)", width="small"),
        "Hedef Fiyat (F/K)": st.column_config.NumberColumn("HF (F/K)", width="small"),
        "Hedef Fiyat (PD/DD)": st.column_config.NumberColumn("HF (PD/DD)", width="small"),
        "Hedef Fiyat (ROE)": st.column_config.NumberColumn("HF (ROE)", width="small"),
        "Hedef Fiyat (BIST Ort.)": st.column_config.NumberColumn("HF (BIST Ort.)", width="medium"),
        "Hedef Fiyat (Sektör PD/DD)": st.column_config.NumberColumn("HF (Sektör)", width="medium"),
        "Nihai Hedef Fiyat": st.column_config.NumberColumn("Nihai Hedef Fiyat", width="medium"),
        "Potansiyel Getiri (%)": st.column_config.NumberColumn("Potansiyel", width="small")
    }
    
    # Styling the dataframe
    st.dataframe(
        df_display.style
        .map(color_potential, subset=['Potansiyel Getiri (%)'])
        .map(color_rsi, subset=['RSI (14)'])
        .map(color_ma200, subset=['MA200 Uzaklık (%)'])
        .map(color_graham, subset=['Graham Skoru'])
        .format({
            "Kapanış (TL)": "₺{:.2f}",
            "Hedef Fiyat (F/K)": "₺{:.2f}",
            "Hedef Fiyat (PD/DD)": "₺{:.2f}",
            "Hedef Fiyat (ROE)": "₺{:.2f}",
            "Hedef Fiyat (BIST Ort.)": "₺{:.2f}",
            "Hedef Fiyat (Sektör PD/DD)": "₺{:.2f}",
            "Nihai Hedef Fiyat": "₺{:.2f}",
            "Potansiyel Getiri (%)": "{:.2f}%",
            "MA200 Uzaklık (%)": "{:.2f}%",
            "RSI (14)": "{:.2f}",
            "F/K": "{:.2f}",
            "PD/DD": "{:.2f}"
        }),
        use_container_width=True,
        height=600,
        column_config=column_widths
    )
