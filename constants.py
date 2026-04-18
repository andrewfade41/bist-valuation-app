"""
constants.py — BIST Valuation App Sabitleri

Tüm magic number ve string'ler burada merkezi olarak tanımlanır.
Değişiklik yapılması gerektiğinde tek bir noktadan güncelleme yeterlidir.
"""
from enum import IntEnum

# =============================================================================
# Hesaplama Sabitleri (calculator.py)
# =============================================================================

# F/K filtreleme — BIST ortalaması hesaplanırken aşırı uç değerleri dışlamak için
FK_VALID_MIN = 0
FK_VALID_MAX = 150

# PD/DD filtreleme
PDDD_VALID_MIN = 0
PDDD_VALID_MAX = 50

# Graham Kriterleri
GRAHAM_MARKET_CAP_THRESHOLD = 5_000_000_000  # ₺5 Milyar
GRAHAM_CURRENT_RATIO_MIN = 1.5
GRAHAM_DEBT_TO_EQUITY_MAX = 0.5
GRAHAM_FK_MAX = 15
GRAHAM_PDDD_MAX = 1.5
GRAHAM_MULTIPLIER_MAX = 22.5  # F/K * PD/DD < 22.5
GRAHAM_ROE_MIN = 0.20
GRAHAM_RSI_MAX = 60
GRAHAM_NUMBER_CONSTANT = 22.5  # sqrt(22.5 * EPS * BVPS)

# Operasyonel Skor Eşikleri
GROWTH_STRONG_THRESHOLD = 25  # %25 üzeri büyüme = güçlü
NET_DEBT_CASH_RICH_BONUS = 2  # Nakit zenginlerine verilen ek puan

# Minervini Trend Şablonu
MINERVINI_52W_LOW_MULTIPLIER = 1.3  # Fiyat >= 1.3 * 52H Dip
MINERVINI_52W_HIGH_MULTIPLIER = 0.75  # Fiyat >= 0.75 * 52H Zirve

# Varsayılan Hesaplama Parametreleri
DEFAULT_TARGET_FK = 10.0
DEFAULT_TARGET_PDDD = 1.5
DEFAULT_EXPECTED_RETURN_PCT = 50  # %50

# =============================================================================
# TTM (Trailing Twelve Months) Yıllıklaştırma Çarpanları
# =============================================================================

# Çeyreklik bilanço dönemine göre EPS'yi yıllıklaştırmak için çarpanlar
# Ay → Çarpan: Q1(3)=4x, Q2(6)=2x, Q3(9)=4/3x, Q4(12)=1x
ANNUALIZATION_MULTIPLIERS = {
    3: 4,       # Q1: 3 aylık kâr × 4
    6: 2,       # Q2: 6 aylık kâr × 2
    9: 4 / 3,   # Q3: 9 aylık kâr × (4/3)
    12: 1,      # Q4: 12 aylık kâr (zaten yıllık)
}

# Yıllıklaştırmanın güvenilir olmadığı sektörler (mevsimsel kâr yapısı)
# Bu sektörlerdeki hisseler için yıllıklaştırma uyarısı gösterilir
SEASONAL_SECTORS = frozenset([
    "Turizm",
    "Tarım",
])

# =============================================================================
# Bilanço Güncellik Göstergesi
# =============================================================================

# Son Dönem'in güncellik durumlarına göre renk kodları (Streamlit CSS)
FRESHNESS_CURRENT_COLOR = "#2E7D32"    # Yeşil — Güncel çeyrek
FRESHNESS_PREVIOUS_COLOR = "#E65100"   # Turuncu — Bir önceki çeyrek
FRESHNESS_STALE_COLOR = "#D32F2F"      # Kırmızı — 2+ çeyrek eski

# =============================================================================
# UI Sabitleri (app.py)
# =============================================================================

# Sidebar parametre sınırları
FK_INPUT_MIN = 1.0
FK_INPUT_MAX = 50.0
FK_INPUT_STEP = 0.5

PDDD_INPUT_MIN = 0.5
PDDD_INPUT_MAX = 10.0
PDDD_INPUT_STEP = 0.1

EXPECTED_RETURN_INPUT_MIN = 10
EXPECTED_RETURN_INPUT_MAX = 100
EXPECTED_RETURN_INPUT_STEP = 5

# Renk kodlama eşikleri
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
HALKA_ACIKLIK_LOW = 15
HALKA_ACIKLIK_IDEAL_MAX = 50
HALKA_ACIKLIK_HIGH = 80
TAKAS_CHANGE_STRONG = 1.0  # %1 üzeri = güçlü değişim

# Operasyonel skor renk eşikleri
OP_SCORE_EXCELLENT = 8
OP_SCORE_GOOD = 6
OP_SCORE_POOR = 3

# Graham skor renk eşikleri
GRAHAM_SCORE_EXCELLENT = 8
GRAHAM_SCORE_GOOD = 6
GRAHAM_SCORE_POOR = 3

# Büyüme renk eşikleri
GROWTH_STRONG_COLOR_THRESHOLD = 25  # %25 üzeri = koyu yeşil

# Grid görünümü
GRID_MAX_TICKERS = 12
GRID_COLUMNS = 4
CHART_HISTORY_PERIOD = "6mo"

# Portföy Optimizasyonu
PORTFOLIO_MIN_TICKERS = 2
PORTFOLIO_MAX_TICKERS = 60
PORTFOLIO_HISTORY_YEARS = 2

# DCF varsayılanları
DCF_DEFAULT_GROWTH_1_5 = 25.0
DCF_DEFAULT_GROWTH_6_10 = 15.0
DCF_DEFAULT_WACC = 35.0
DCF_PERPETUAL_GROWTH = 0.02

# =============================================================================
# API URL'leri
# =============================================================================

IS_YATIRIM_FUNDAMENTALS_URL = (
    "https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/"
    "Temel-Degerler-Ve-Oranlar.aspx"
)

IS_YATIRIM_TAKAS_URL = (
    "https://www.isyatirim.com.tr/_layouts/15/IsYatirim.Website/"
    "StockInfo/CompanyInfoAjax.aspx/GetYabanciOranlarXHR"
)

TRADINGVIEW_SCANNER_URL = "https://scanner.tradingview.com/turkey/scan"

# =============================================================================
# Dosya Yolları
# =============================================================================

SECTORS_FILENAME = "sectors.json"
PERIODS_SNAPSHOT_FILENAME = "is_yatirim_periods.json"

# =============================================================================
# Watchlist Sabitleri
# =============================================================================

MAX_WATCHLISTS = 5  # .env'de desteklenen maksimum watchlist sayısı

