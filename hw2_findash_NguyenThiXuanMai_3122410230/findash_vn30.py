import requests
import bs4 as bs
import re

import yahoo_fin.stock_info as si
import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# (live từ Vietstock)
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

#==============================================================================
# HÀM LẤY DANH SÁCH VN30 (dùng từ file test_vn30.py)
#==============================================================================

def get_vn30_tickers(yahoo_suffix: bool = True,
                     timeout: int = 15,
                     headless: bool = True):
    url = "https://banggia.vietstock.vn/?id=vn30"

    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1366,768")
    opts.add_argument("--disable-blink-features=AutomationControlled")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=opts
    )

    try:
        driver.get(url)

        # Chờ riêng tbody của bảng giá VN30 (hạn chế dính tbody khác nếu có)
        WebDriverWait(driver, timeout).until(
            EC.presence_of_all_elements_located(
                (By.XPATH, "//table//tbody/tr")
            )
        )

        rows = driver.find_elements(By.XPATH, "//table//tbody/tr")

        symbols = []
        for r in rows:
            tds = r.find_elements(By.TAG_NAME, "td")
            if not tds:
                continue

            raw = tds[0].text.strip().upper()     # 'HPG*', 'POW**', 'VN30'
            sym = re.sub(r"\*+$", "", raw)        # bỏ *, **

            # Lấy đúng mã kiểu AAA, ABCD, VNM...
            if re.fullmatch(r"[A-Z]{3,5}", sym) and sym not in symbols:
                symbols.append(sym)

        if yahoo_suffix:
            symbols = [s + ".VN" for s in symbols]

        return symbols

    finally:
        driver.quit()

#==============================================================================
# Tab 1 Summary cho VN30 (dùng logic từ file test_vn30.py)
#==============================================================================

def tab1_vn30():
    global ticker

    st.title("Summary")
    st.write("Chọn mã VN30 ở sidebar để bắt đầu")
    st.write(f"Mã đang chọn: {ticker}")

    #-----------------------------------------
    # Lấy summary từ yfinance cho mã VN30
    #-----------------------------------------
    @st.cache_data
    def getsummary_vn30(ticker_code: str):
        """
        Lấy một số chỉ tiêu cơ bản cho mã VN30 từ yfinance.
        Nếu yfinance bị timeout / lỗi mạng thì trả về None.
        """
        try:
            tk = yf.Ticker(ticker_code)
            info = tk.info  # dict – đoạn này hay bị timeout
        except Exception:
            return None

        data = {
            "attribute": [
                "Current Price",
                "Previous Close",
                "Open",
                "Day Low",
                "Day High",
                "Volume",
                "Average Volume",
                "Market Cap",
                "Trailing P/E",
                "Forward P/E",
                "52 Week Low",
                "52 Week High",
                "Beta",
                "Currency"
            ],
            "value": [
                info.get("currentPrice"),
                info.get("previousClose"),
                info.get("open"),
                info.get("dayLow"),
                info.get("dayHigh"),
                info.get("volume"),
                info.get("averageVolume"),
                info.get("marketCap"),
                info.get("trailingPE"),
                info.get("forwardPE"),
                info.get("fiftyTwoWeekLow"),
                info.get("fiftyTwoWeekHigh"),
                info.get("beta"),
                info.get("currency"),
            ]
        }

        df = pd.DataFrame(data)
        return df

    c1, c2 = st.columns((1, 1))

    if ticker and ticker != '-':
        summary = getsummary_vn30(ticker)

        if summary is None:
            st.error("Không lấy được thông tin summary từ Yahoo Finance (có thể lỗi mạng / timeout).")
        else:
            summary['value'] = summary['value'].astype(str)

            # chia thành 2 bảng
            with c1:
                showsummary_left = summary.iloc[[0, 1, 2, 3, 4, 5, 7], :].copy()
                showsummary_left.set_index('attribute', inplace=True)
                st.dataframe(showsummary_left)

            with c2:
                showsummary_right = summary.iloc[[6, 8, 9, 10, 11, 12, 13], :].copy()
                showsummary_right.set_index('attribute', inplace=True)
                st.dataframe(showsummary_right)

    #-----------------------------------------
    # Chart giá từ yfinance cho mã VN30
    #-----------------------------------------
    @st.cache_data
    def getstockdata_vn30(ticker_code: str):
        try:
            tk = yf.Ticker(ticker_code)
            # dùng history thay vì download cho ổn định hơn
            stockdata = tk.history(period="max", interval="1d")
        except Exception:
            return None
        return stockdata

    if ticker and ticker != '-':
        chartdata = getstockdata_vn30(ticker)

        if chartdata is None or chartdata.empty:
            st.warning("Không tải được dữ liệu giá cho mã này từ Yahoo Finance (lỗi mạng / timeout).")
        else:
            fig = px.area(chartdata, x=chartdata.index, y=chartdata['Close'])

            fig.update_xaxes(
                rangeselector=dict(
                    buttons=list([
                        dict(count=1, label="1M", step="month", stepmode="backward"),
                        dict(count=3, label="3M", step="month", stepmode="backward"),
                        dict(count=6, label="6M", step="month", stepmode="backward"),
                        dict(count=1, label="YTD", step="year", stepmode="todate"),
                        dict(count=1, label="1Y", step="year", stepmode="backward"),
                        dict(count=3, label="3Y", step="year", stepmode="backward"),
                        dict(count=5, label="5Y", step="year", stepmode="backward"),
                        dict(label="MAX", step="all")
                    ])
                )
            )
            st.plotly_chart(fig)



#==============================================================================
# Tab 2 Chart
#==============================================================================
#==============================================================================
# TAB 2 – FINAL VERSION WITH CANDLE + AUTO FALLBACK
#==============================================================================

def tab2_vn30():
    st.title("Chart")
    st.write(ticker)

    # ==== UI FILTERS ====
    c1, c2, c3, c4, c5 = st.columns((1,1,1,1,1))
    with c1:
        start_date = st.date_input("Start date", datetime(2022,1,1).date())
    with c2:
        end_date = st.date_input("End date", datetime(2023,12,31).date())
    with c3:
        duration = st.selectbox(
            "Select duration", 
            ("-", "1M", "3M", "6M", "YTD", "1Y", "3Y", "5Y")
        )
    with c4:
        interval = st.selectbox("Select interval", ("1d", "1wk", "1mo"))
    with c5:
        plot_type = st.selectbox("Plot", ("Auto", "Candlestick", "Line"))

    # ==== LOAD DATA ====
    @st.cache_data
    def load_data(tk, interval):
        df = yf.download(tk, period="max", interval=interval)
        df.dropna(how="all", inplace=True)
        return df

    df = load_data(ticker, interval)
    if df.empty:
        st.error("Không tải được dữ liệu.")
        return

    # ==== FILTER BY TIME ====
    today = datetime.today().date()
    if duration != "-":
        mapping = {
            "1M": 30, "3M": 90, "6M": 180,
            "1Y": 365, "3Y": 365*3, "5Y": 365*5
        }
        if duration == "YTD":
            start = datetime(today.year, 1, 1)
        else:
            start = today - timedelta(days=mapping[duration])
        df = df[df.index.date >= start]
    else:
        df = df[(df.index.date >= start_date) & (df.index.date <= end_date)]

    if df.empty:
        st.warning("Không có dữ liệu trong khoảng thời gian.")
        return

    # ==== INDICATORS ====
    df["SMA50"] = df["Close"].rolling(50).mean()
    df["MACD"] = df["Close"].ewm(12).mean() - df["Close"].ewm(26).mean()
    df["Signal"] = df["MACD"].ewm(9).mean()
    df["Hist"] = df["MACD"] - df["Signal"]

    # ==== CHECK IF WE HAVE FULL OHLC ====
    has_ohlc = (
        "Open" in df.columns
        and "High" in df.columns
        and "Low" in df.columns
        and df[["Open","High","Low"]].notna().sum().min() > 10
    )

    # Auto logic:
    if plot_type == "Auto":
        if has_ohlc:
            mode = "Candlestick"
        else:
            mode = "Line"
    else:
        # user chọn candle nhưng không có OHLC
        if plot_type == "Candlestick" and not has_ohlc:
            st.warning("Không có OHLC => hiển thị Line chart.")
            mode = "Line"
        else:
            mode = plot_type

    # ==== PLOT ====
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        row_heights=[0.55, 0.25, 0.20],
        vertical_spacing=0.02
    )

    # ---- PRICE ----
    if mode == "Candlestick":
        fig.add_trace(
            go.Candlestick(
                x=df.index,
                open=df["Open"],
                high=df["High"],low=df["Low"],
                close=df["Close"],
                name="Price"
            ),
            row=1, col=1
        )
    else:
        fig.add_trace(
            go.Scatter(
                x=df.index, y=df["Close"],
                mode="lines",
                name="Close"
            ),
            row=1, col=1
        )

    # SMA50
    fig.add_trace(
        go.Scatter(
            x=df.index, y=df["SMA50"],
            mode="lines",
            name="SMA50",
            line=dict(color="orange")
        ),
        row=1, col=1
    )

    # ---- VOLUME ----
    fig.add_trace(
        go.Bar(x=df.index, y=df["Volume"], name="Volume"),
        row=2, col=1
    )

    # ---- MACD ----
    fig.add_trace(
        go.Bar(x=df.index, y=df["Hist"], name="Hist", marker_color="#ffb3b3"),
        row=3, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=df.index, y=df["MACD"],
            mode="lines", name="MACD", line=dict(color="blue")
        ),
        row=3, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=df.index, y=df["Signal"],
            mode="lines", name="Signal", line=dict(color="red")
        ),
        row=3, col=1
    )

    # ---- STYLE ----
    fig.update_layout(
        height=850,
        hovermode="x unified",
        xaxis_rangeslider_visible=False,
        margin=dict(l=40, r=40, t=40, b=40)
    )

    st.plotly_chart(fig, use_container_width=True)

#==============================================================================
# Tab 3 Statistics
#==============================================================================

def tab3_vn30():
    st.title("Statistics")
    st.write(f"Mã đang chọn: {ticker}")

    if ticker == "-" or ticker is None:
        st.warning("Hãy chọn một mã VN30 trong sidebar")
        return

    @st.cache_data
    def get_info(tk):
        try:
            t = yf.Ticker(tk)
            return t.info
        except Exception:
            return {}

    info = get_info(ticker)

    # Nếu không có info → báo lỗi
    if info is None or info == {}:
        st.error("Không lấy được dữ liệu từ Yahoo Finance (yfinance.info).")
        return

    #====================================================
    # Utility function: lấy value an toàn
    #====================================================
    def val(key):
        return info.get(key, "N/A")

    #====================================================
    # BUILD TABLES LIKE SLIDE
    #====================================================

    col1, col2 = st.columns(2)

    #====================================================
    # LEFT COLUMN
    #====================================================

    with col1:

        #----------------------------------------------
        st.header("Valuation Measures")
        #----------------------------------------------
        df_val = pd.DataFrame({
            "Attribute": [
                "Market Cap",
                "Trailing P/E",
                "Forward P/E",
                "Price to Book",
                "PEG Ratio",
            ],
            "Value": [
                val("marketCap"),
                val("trailingPE"),
                val("forwardPE"),
                val("priceToBook"),
                val("pegRatio"),
            ]
        })
        df_val.set_index("Attribute", inplace=True)
        st.table(df_val)

        #----------------------------------------------
        st.header("Financial Highlights")
        st.subheader("Fiscal Year")
        #----------------------------------------------
        df_fiscal = pd.DataFrame({
            "Attribute": ["Fiscal Year End", "Most Recent Quarter"],
            "Value": [val("fiscalYearEnd"), val("mostRecentQuarter")]
        }).set_index("Attribute")
        st.table(df_fiscal)

        #----------------------------------------------
        st.subheader("Profitability")
        #----------------------------------------------
        df_profit = pd.DataFrame({
            "Attribute": ["Profit Margin", "Operating Margin"],
            "Value": [val("profitMargins"), val("operatingMargins")]
        }).set_index("Attribute")
        st.table(df_profit)

        #----------------------------------------------
        st.subheader("Management Effectiveness")
        #----------------------------------------------
        df_eff = pd.DataFrame({
            "Attribute": ["Return on Assets", "Return on Equity"],
            "Value": [val("returnOnAssets"), val("returnOnEquity")]
        }).set_index("Attribute")
        st.table(df_eff)

        #----------------------------------------------
        st.subheader("Income Statement")
        #----------------------------------------------
        df_income = pd.DataFrame({
            "Attribute": [
                "Revenue",
                "Gross Profits",
                "EBITDA",
                "Net Income",
                "Quarterly Revenue Growth",
                "Quarterly Earnings Growth"
            ],
            "Value": [
                val("totalRevenue"),
                val("grossProfits"),
                val("ebitda"),
                val("netIncome"),
                val("revenueQuarterlyGrowth"),
                val("earningsQuarterlyGrowth"),
            ]
        }).set_index("Attribute")
        st.table(df_income)

        #----------------------------------------------
        st.subheader("Balance Sheet")
        #----------------------------------------------
        df_bs = pd.DataFrame({
            "Attribute": [
                "Total Assets",
                "Total Cash",
                "Total Debt",
                "Book Value"
            ],
            "Value": [
                val("totalAssets"),
                val("totalCash"),
                val("totalDebt"),
                val("bookValue"),
            ]
        }).set_index("Attribute")
        st.table(df_bs)

        #----------------------------------------------
        st.subheader("Cash Flow Statement")
        #----------------------------------------------
        df_cf = pd.DataFrame({
            "Attribute": [
                "Operating Cashflow",
                "Free Cashflow",
            ],
            "Value": [
                val("operatingCashflow"),
                val("freeCashflow"),
            ]
        }).set_index("Attribute")
        st.table(df_cf)

    #====================================================
    # RIGHT COLUMN
    #====================================================

    with col2:

        #----------------------------------------------
        st.header("Trading Information")
        st.subheader("Stock Price History")
        #----------------------------------------------
        df_hist = pd.DataFrame({
            "Attribute": [
                "52 Week High", "52 Week Low", "Beta",
                "Previous Close", "Open", "Day Low", "Day High"
            ],
            "Value": [
                val("fiftyTwoWeekHigh"),
                val("fiftyTwoWeekLow"),
                val("beta"),
                val("previousClose"),
                val("open"),
                val("dayLow"),
                val("dayHigh")
            ]
        }).set_index("Attribute")
        st.table(df_hist)

        #----------------------------------------------
        st.subheader("Share Statistics")
        #----------------------------------------------
        df_share = pd.DataFrame({
            "Attribute": [
                "Shares Outstanding",
                "Float Shares",
                "Shares Short",
                "Short Ratio",
                "Short % of Float"
            ],
            "Value": [
                val("sharesOutstanding"),
                val("floatShares"),
                val("sharesShort"),
                val("shortRatio"),
                val("shortPercentOfFloat")
            ]
        }).set_index("Attribute")
        st.table(df_share)

        #----------------------------------------------
        st.subheader("Dividends & Splits")
        #----------------------------------------------
        df_div = pd.DataFrame({
            "Attribute": [
                "Dividend Rate",
                "Dividend Yield",
                "Ex-Dividend Date",
                "Payout Ratio",
                "Last Split Factor",
                "Last Split Date"
            ],
            "Value": [
                val("dividendRate"),
                val("dividendYield"),
                val("exDividendDate"),
                val("payoutRatio"),
                val("lastSplitFactor"),
                val("lastSplitDate")
            ]
        }).set_index("Attribute")
        st.table(df_div)


#==============================================================================
# Tab 4 Financials
#==============================================================================

def tab4_vn30():
    st.title("Financials")
    st.write(ticker)

    statement = st.selectbox("Show", ["Income Statement", "Balance Sheet", "Cash Flow"])
    period = st.selectbox("Period", ["Yearly", "Quarterly"])

    @st.cache_data
    def get_financials_from_yf(ticker_code: str, statement: str, period: str):
        """
        Lấy báo cáo tài chính từ yfinance cho mã .VN
        statement: 'Income Statement' | 'Balance Sheet' | 'Cash Flow'
        period   : 'Yearly' | 'Quarterly'
        Trả về DataFrame đã format cột là năm/quý (string).
        """
        try:
            tk = yf.Ticker(ticker_code)
        except Exception:
            return None

        df = None
        try:
            if statement == "Income Statement":
                df = tk.financials if period == "Yearly" else tk.quarterly_financials
            elif statement == "Balance Sheet":
                df = tk.balance_sheet if period == "Yearly" else tk.quarterly_balance_sheet
            elif statement == "Cash Flow":
                df = tk.cashflow if period == "Yearly" else tk.quarterly_cashflow
        except Exception:
            df = None

        if df is None or df.empty:
            return None

        # Cột là datetime -> đổi sang string cho dễ nhìn, sort giảm dần
        cols = list(df.columns)
        try:
            cols = [c.strftime("%Y-%m-%d") for c in cols]
        except Exception:
            cols = [str(c) for c in cols]
        df.columns = cols
        df = df.sort_index(axis=1, ascending=False)

        # Để index là dòng (item), cột là kỳ báo cáo giống Yahoo
        return df

    if ticker != "-":
        data = get_financials_from_yf(ticker, statement, period)

        if data is None:
            st.warning(
                "Không lấy được dữ liệu {} - {} từ yfinance cho mã này. "
                "Có thể Yahoo không cung cấp đầy đủ báo cáo cho cổ phiếu VN.".format(statement, period)
            )
        else:
            st.dataframe(data)



#==============================================================================
# Tab 5 Analysis 
#==============================================================================

def tab5_vn30():
    st.title("Analysis")
    st.write("Currency: theo đơn vị trên Yahoo Finance (thường là VND)")
    st.write(ticker)

    @st.cache_data
    def get_base_financials(ticker_code: str):
        """
        Lấy yearly financials & balance sheet để tính các tỷ số.
        Trả về (income_statement_df, balance_sheet_df)
        """
        try:
            tk = yf.Ticker(ticker_code)
            is_y = tk.financials        # Income Statement yearly
            bs_y = tk.balance_sheet     # Balance Sheet yearly
        except Exception:
            return None, None

        if is_y is None or is_y.empty or bs_y is None or bs_y.empty:
            return None, None

        return is_y, bs_y

    def pick_line(df: pd.DataFrame, candidates):
        """Lấy dòng đầu tiên tìm được trong danh sách candidates."""
        if df is None or df.empty:
            return None
        for name in candidates:
            if name in df.index:
                return df.loc[name]
        return None

    if ticker == "-":
        return

    is_y, bs_y = get_base_financials(ticker)

    if is_y is None or bs_y is None:
        st.warning(
            "Không đủ dữ liệu báo cáo tài chính yearly trên yfinance để phân tích cho mã này."
        )
        return

    # Giả định cột đầu tiên là kỳ gần nhất (thường là mới nhất)
    latest_col = is_y.columns[0]

    # ----- Lấy một số line item thường gặp -----
    revenue = pick_line(is_y, ["Total Revenue", "TotalRevenue", "Revenue"])
    gross_profit = pick_line(is_y, ["Gross Profit", "GrossProfit"])
    operating_income = pick_line(is_y, ["Operating Income", "OperatingIncome"])
    net_income = pick_line(is_y, ["Net Income", "NetIncome", "Net Income Common Stockholders"])

    total_assets = pick_line(bs_y, ["Total Assets", "TotalAssets"])
    total_equity = pick_line(
        bs_y,
        ["Total Stockholder Equity", "TotalStockholderEquity",
         "Total Equity Gross Minority Interest", "Total Equity"]
    )
    total_debt = pick_line(bs_y, ["Total Debt", "TotalDebt"])
    current_assets = pick_line(bs_y, ["Total Current Assets", "Current Assets", "TotalCurrentAssets"])
    current_liabilities = pick_line(
        bs_y,
        ["Total Current Liabilities", "Current Liabilities", "TotalCurrentLiabilities"]
    )

    # Lấy giá trị kỳ gần nhất (cùng cột latest_col)
    def latest(series):
        if series is None:
            return None
        try:
            return float(series[latest_col])
        except Exception:
            # nếu series là scalar hoặc index không khớp
            try:
                return float(series.iloc[0])
            except Exception:
                return None

    rev_val = latest(revenue)
    gp_val = latest(gross_profit)
    op_val = latest(operating_income)
    ni_val = latest(net_income)
    assets_val = latest(total_assets)
    equity_val = latest(total_equity)
    debt_val = latest(total_debt)
    ca_val = latest(current_assets)
    cl_val = latest(current_liabilities)

    # ---------- Bảng 1: Profitability ----------
    prof_metrics = []
    prof_values = []

    if rev_val is not None:
        prof_metrics.append("Doanh thu ({}):".format(latest_col.date() if hasattr(latest_col, "date") else latest_col))
        prof_values.append(rev_val)

    if gp_val is not None and rev_val:
        prof_metrics.append("Gross Margin")
        prof_values.append(gp_val / rev_val)

    if op_val is not None and rev_val:
        prof_metrics.append("Operating Margin")
        prof_values.append(op_val / rev_val)

    if ni_val is not None and rev_val:
        prof_metrics.append("Net Margin")
        prof_values.append(ni_val / rev_val)

    prof_df = pd.DataFrame({"Metric": prof_metrics, "Value": prof_values})

    # ---------- Bảng 2: Leverage & Liquidity ----------
    lev_metrics = []
    lev_values = []

    if debt_val is not None and equity_val:
        lev_metrics.append("Debt / Equity")
        lev_values.append(debt_val / equity_val)

    if assets_val is not None and equity_val:
        lev_metrics.append("Assets / Equity (leverage)")
        lev_values.append(assets_val / equity_val)

    if ca_val is not None and cl_val:
        lev_metrics.append("Current Ratio (CA / CL)")
        lev_values.append(ca_val / cl_val)

    lev_df = pd.DataFrame({"Metric": lev_metrics, "Value": lev_values})

    # ---------- Bảng 3: Quy mô & lợi nhuận tuyệt đối ----------
    size_metrics = []
    size_values = []

    if assets_val is not None:
        size_metrics.append("Total Assets")
        size_values.append(assets_val)

    if equity_val is not None:
        size_metrics.append("Total Equity")
        size_values.append(equity_val)

    if ni_val is not None and equity_val:
        size_metrics.append("ROE (Net Income / Equity)")
        size_values.append(ni_val / equity_val)

    size_df = pd.DataFrame({"Metric": size_metrics, "Value": size_values})

    # ----------------- Hiển thị -----------------
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Profitability")
        if prof_df.empty:
            st.info("Chưa tính được tỷ số lợi nhuận do thiếu dữ liệu dòng trên báo cáo.")
        else:
            st.table(prof_df)

        st.subheader("Leverage & Liquidity")
        if lev_df.empty:
            st.info("Chưa tính được tỷ số đòn bẩy / thanh khoản do thiếu dữ liệu.")
        else:
            st.table(lev_df)

    with c2:
        st.subheader("Size & Returns")
        if size_df.empty:
            st.info("Chưa tính được các chỉ tiêu quy mô & ROE.")
        else:
            st.table(size_df)

        st.caption(
            "Lưu ý: Các chỉ tiêu được tính từ báo cáo yearly mới nhất trên Yahoo Finance; "
            "tên dòng có thể khác nhau giữa các công ty nên một số tỷ số có thể bị bỏ trống."
        )
            

#==============================================================================
# Tab 6 Monte Carlo Simulation
#==============================================================================

def tab6_vn30():
    st.title("Monte Carlo Simulation")
    st.write(ticker)

    # chọn số lần mô phỏng và time horizon
    simulations = st.selectbox("Number of Simulations (n)", [200, 500, 1000])
    time_horizon = st.selectbox("Time Horizon (t) - days", [30, 60, 90])

    @st.cache_data
    def montecarlo(ticker_code: str, time_horizon: int, simulations: int):
        """
        Monte Carlo cho cổ phiếu VN30 dùng dữ liệu từ yfinance.
        Lấy lịch sử ~ 1 năm để tính volatility.
        """
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=365)

        # tải dữ liệu lịch sử từ yfinance
        data = yf.download(ticker_code, start=start_date, end=end_date, interval="1d")

        # nếu không có dữ liệu thì trả None
        if data is None or data.empty:
            return None, None

        close_price = data["Close"].dropna()

        # tính log-return hoặc pct_change đều được; dùng pct_change như bản gốc
        daily_return = close_price.pct_change().dropna()
        daily_volatility = np.std(daily_return)

        # dataframe để lưu kết quả mô phỏng
        simulation_df = pd.DataFrame()

        last_actual_price = close_price.iloc[-1]

        for i in range(simulations):
            next_price = []
            last_price = last_actual_price

            for _ in range(time_horizon):
                # giả định normal(0, sigma)
                future_return = np.random.normal(0, daily_volatility)
                future_price = last_price * (1 + future_return)
                next_price.append(future_price)
                last_price = future_price

            simulation_df[i] = next_price

        return simulation_df, float(last_actual_price)

    if ticker != '-':
        mc, last_close = montecarlo(ticker, time_horizon, simulations)

        if mc is None:
            st.error("Không tải được dữ liệu giá từ yfinance cho mã này. Vui lòng chọn mã khác.")
            return

        # --- Vẽ đường mô phỏng ---
        fig, ax = plt.subplots(figsize=(15, 8))
        ax.plot(mc)
        plt.title(f"Monte Carlo simulation for {ticker} stock price in next {time_horizon} days")
        plt.xlabel("Day")
        plt.ylabel("Price")

        # đường giá hiện tại + legend
        ax.axhline(
            y=last_close,
            color="red",
            label=f"Current stock price is: {np.round(last_close, 2)}"
        )
        ax.legend()

        st.pyplot(fig)

        # --- Value at Risk (VaR) ---
        st.subheader("Value at Risk (VaR)")
        ending_price = mc.iloc[-1, :].to_numpy().astype(float).ravel()

        fig1, ax1 = plt.subplots(figsize=(15, 8))
        ax1.hist(ending_price, bins=50)
        var_price = np.percentile(ending_price, 5)
        plt.axvline(var_price, color="red", linestyle="--", linewidth=1)
        plt.legend([f"5th Percentile of the Future Price: {np.round(var_price, 2)}"])
        plt.title("Distribution of the Ending Price")
        plt.xlabel("Price")
        plt.ylabel("Frequency")
        st.pyplot(fig1)

        VaR = last_close - var_price
        st.write(
            "VaR at 95% confidence interval is: "
            + str(np.round(VaR, 2))
            + " (đơn vị theo currency của mã cổ phiếu, thường là VND)"
        )



#==============================================================================
# Tab 7 Your Portfolio's Trend
#==============================================================================

def tab7_vn30():
    st.title("Your Portfolio's Trend")

    # dùng lại hàm get_vn30_tickers đã định nghĩa ở trên để lấy danh sách VN30
    vn30_tickers = get_vn30_tickers(yahoo_suffix=True)

    if not vn30_tickers:
        st.error("Không lấy được danh sách VN30 từ Vietstock. Vui lòng tải lại ứng dụng.")
        return

    # gợi ý mặc định: nếu đang chọn 1 mã ở sidebar thì cho vào luôn
    default_selection = []
    if ticker and ticker != '-' and ticker in vn30_tickers:
        default_selection = [ticker]
    else:
        default_selection = vn30_tickers[:3]  # ví dụ: 3 mã đầu danh sách

    selected_tickers = st.multiselect(
        "Select tickers in your VN30 portfolio",
        options=vn30_tickers,
        default=default_selection
    )

    if not selected_tickers:
        st.info("Hãy chọn ít nhất một mã VN30 để xem xu hướng danh mục.")
        return

    # tải dữ liệu giá 5 năm cho từng mã trong danh mục, dùng yfinance
    df = pd.DataFrame()
    for t in selected_tickers:
        hist = yf.download(t, period="5y", interval="1d")

        # nếu tải không được hoặc không có cột Close thì bỏ qua
        if hist is None or hist.empty or "Close" not in hist.columns:
            continue

        series = hist["Close"]
        series = series.dropna()
        series.name = t   # đặt tên series = mã cổ phiếu

        df = pd.concat([df, series], axis=1)

    # nếu toàn bộ bị rỗng
    if df.empty:
        st.error("Không tải được dữ liệu giá cho các mã đã chọn.")
        return

    df = df.dropna(how="all")

    st.subheader("Portfolio Price Trend (Close Price)")
    fig = px.line(df, x=df.index, y=df.columns)
    fig.update_layout(xaxis_title="Date", yaxis_title="Price")
    st.plotly_chart(fig, use_container_width=True)


#==============================================================================
# Main body
#==============================================================================

def run():
    # danh sách VN30 từ Vietstock (dùng hàm mới)
    ticker_list = ['-'] + get_vn30_tickers()
    
    global ticker
    ticker = st.sidebar.selectbox("Select a ticker", ticker_list)
    
    select_tab = st.sidebar.radio("Select tab", ['Summary', 'Chart', 'Statistics', 'Financials', 'Analysis', 'Monte Carlo Simulation', "Your Portfolio's Trend"])
    
    if select_tab == 'Summary':
        tab1_vn30()
    elif select_tab == 'Chart':
        tab2_vn30()
    elif select_tab == 'Statistics':
        tab3_vn30()
    elif select_tab == 'Financials':
        tab4_vn30()
    elif select_tab == 'Analysis':
        tab5_vn30()
    elif select_tab == 'Monte Carlo Simulation':
        tab6_vn30()
    elif select_tab == "Your Portfolio's Trend":
        tab7_vn30()
       
    
if __name__ == "__main__":
    run()
