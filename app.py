import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import io
import yfinance as yf

API_KEY = "W6UEfHWFrzaTuuVAOpLIhyBvIhdZ1U0o"

def get_profile_data(symbol):
    url = f"https://financialmodelingprep.com/api/v3/profile/{symbol}?apikey={API_KEY}"
    r = requests.get(url).json()
    if r and isinstance(r, list) and len(r) > 0:
        profile = r[0]
        market_cap = profile.get("mktCap", None)
        price = profile.get("price", None)
        beta = profile.get("beta", None)
        sector = profile.get("sector", None)
        return market_cap, price, beta, sector
    return None, None, None, None

def get_shares_outstanding_yahoo(symbol):
    yf_ticker = yf.Ticker(symbol)
    info = yf_ticker.info
    shares_out = info.get("sharesOutstanding", None)
    return shares_out

def get_balance_sheet_data(symbol):
    url = f"https://financialmodelingprep.com/api/v3/balance-sheet-statement/{symbol}?apikey={API_KEY}&limit=1"
    r = requests.get(url).json()
    if r and isinstance(r, list) and len(r) > 0:
        return r[0].get("totalDebt", None)
    return None

def get_income_statement_data(symbol):
    url = f"https://financialmodelingprep.com/api/v3/income-statement/{symbol}?apikey={API_KEY}&limit=1"
    r = requests.get(url).json()
    if r and isinstance(r, list) and len(r) > 0:
        is_data = r[0]
        interest_expense = is_data.get("interestExpense", None)
        income_before_tax = is_data.get("incomeBeforeTax", None)
        tax_expense = is_data.get("incomeTaxExpense", None)
        return interest_expense, income_before_tax, tax_expense
    return None, None, None

def get_key_metrics(symbol):
    url = f"https://financialmodelingprep.com/api/v3/key-metrics/{symbol}?apikey={API_KEY}&limit=1"
    r = requests.get(url).json()
    if not isinstance(r, list) or len(r) == 0:
        return None
    roic = r[0].get("roic", None)
    return roic

def get_cagr(symbol, years=10):
    url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{symbol}?apikey={API_KEY}&serietype=line"
    r = requests.get(url).json()
    if "historical" not in r or len(r["historical"]) == 0:
        return None
    hist = r["historical"]
    hist_sorted = sorted(hist, key=lambda x: datetime.strptime(x["date"], "%Y-%m-%d"))
    end_date = datetime.strptime(hist_sorted[-1]["date"], "%Y-%m-%d")
    end_price = hist_sorted[-1]["close"]
    start_date_limit = end_date - timedelta(days=365*years)
    start_record = None
    for rec in hist_sorted:
        rec_date = datetime.strptime(rec["date"], "%Y-%m-%d")
        if rec_date >= start_date_limit:
            start_record = rec
            break
    if not start_record:
        return None
    start_price = start_record["close"]
    actual_years = (end_date - datetime.strptime(start_record["date"], "%Y-%m-%d")).days / 365
    if actual_years <= 0:
        return None
    cagr = (end_price / start_price)**(1/actual_years) - 1
    return cagr

def get_risk_free_rate():
    today = datetime.today()
    from_date = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    to_date = today.strftime("%Y-%m-%d")
    url = f"https://financialmodelingprep.com/api/v4/treasury?from={from_date}&to={to_date}&apikey={API_KEY}"
    r = requests.get(url).json()
    if isinstance(r, list) and len(r) > 0:
        for data in reversed(r):
            if "tenYear" in data and data["tenYear"] is not None:
                return float(data["tenYear"])/100.0
    return None

def get_market_premium():
    url = f"https://financialmodelingprep.com/api/v4/market_risk_premium?apikey={API_KEY}"
    r = requests.get(url).json()
    if r and isinstance(r, list) and len(r) > 0:
        mp = r[0].get("marketRiskPremium", None)
        return mp
    return None

def calculate_wacc(symbol):
    market_cap, price, beta, sector = get_profile_data(symbol)
    total_debt = get_balance_sheet_data(symbol)
    interest_expense, income_before_tax, tax_expense = get_income_statement_data(symbol)

    if not (market_cap and beta and total_debt and interest_expense and income_before_tax and tax_expense):
        return None

    try:
        market_cap = float(market_cap)
        total_debt = float(total_debt)
        interest_expense = float(interest_expense)
        income_before_tax = float(income_before_tax)
        tax_expense = float(tax_expense)
        beta = float(beta)
    except:
        return None

    if (market_cap + total_debt) == 0 or income_before_tax <= 0 or total_debt <= 0:
        return None

    Rf = get_risk_free_rate()
    if Rf is None:
        Rf = 0.04
    market_premium = get_market_premium()
    if market_premium is None:
        market_premium = 0.05

    Re = Rf + beta * market_premium
    Rd = abs(interest_expense) / total_debt
    T = tax_expense / income_before_tax
    E = market_cap
    D = total_debt
    wacc = (E/(E+D))*Re + (D/(E+D))*Rd*(1 - T)
    return wacc

# Manejamos el reset sin experimental_rerun
if "reset_clicked" not in st.session_state:
    st.session_state.reset_clicked = False
if "last_ticker_input" not in st.session_state:
    st.session_state.last_ticker_input = ""

if st.session_state.reset_clicked:
    st.session_state.last_ticker_input = ""
    st.session_state.reset_clicked = False

st.title("App Datos Financieros de Empresas (FMP + Yahoo Finance)")

ticker_input = st.text_input(
    "Ingresa uno o varios tickers separados por comas (ej: TSLA,GM,F):",
    value=st.session_state.last_ticker_input
)

col1, col2 = st.columns(2)
with col1:
    obtener_btn = st.button("Obtener datos")
with col2:
    reset_btn = st.button("Resetear")

if reset_btn:
    st.session_state.reset_clicked = True
    st.stop()

st.session_state.last_ticker_input = ticker_input

if obtener_btn:
    tickers_raw = ticker_input.strip()
    if tickers_raw:
        tickers = [t.strip().upper() for t in tickers_raw.split(",") if t.strip()]

        data_list = []

        # Crear barra de progreso
        progress_bar = st.progress(0)
        total = len(tickers)

        for i, ticker in enumerate(tickers):
            # Datos de FMP
            roic = get_key_metrics(ticker)
            cagr_val = get_cagr(ticker, 10)
            wacc = calculate_wacc(ticker)
            market_cap, price, beta, sector = get_profile_data(ticker)

            # Acciones en circulación desde Yahoo Finance
            shares_outstanding = get_shares_outstanding_yahoo(ticker)

            roic_pct = f"{roic*100:.2f}%" if roic is not None else "No disponible"
            cagr_pct = f"{cagr_val*100:.2f}%" if cagr_val is not None else "No disponible"
            wacc_pct = f"{wacc*100:.2f}%" if wacc is not None else "No disponible"
            market_cap_str = f"{market_cap}" if market_cap is not None else "No disponible"
            price_str = f"{price}" if price is not None else "No disponible"
            shares_str = f"{shares_outstanding}" if shares_outstanding is not None else "No disponible"
            categoria = sector if sector else "No definido"

            data_list.append({
                "Ticker": ticker,
                "Categoría (Sector)": categoria,
                "ROIC (%)": roic_pct,
                "WACC (%)": wacc_pct,
                "CAGR 10y (%)": cagr_pct,
                "Market Cap": market_cap_str,
                "Price": price_str,
                "Acciones en circulación": shares_str
            })

            # Actualizar barra de progreso
            progress = int((i+1)/total*100)
            progress_bar.progress(progress)

        df = pd.DataFrame(data_list)
        st.write("### Resultados obtenidos:")
        st.dataframe(df)

        # Crear el buffer en memoria para el Excel
        buffer = io.BytesIO()
        df.to_excel(buffer, index=False, engine='openpyxl')
        buffer.seek(0)

        st.download_button(
            label="Descargar datos en Excel",
            data=buffer,
            file_name="datos_empresas.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.warning("Por favor, ingresa al menos un ticker.")
