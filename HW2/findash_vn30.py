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

def get_vn30_tickers(yahoo_suffix: bool = True, timeout: int = 15, headless: bool = True):
    url = "https://banggia.vietstock.vn/?id=vn30"

    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    try:
        driver.get(url)

        WebDriverWait(driver, timeout).until(
            EC.presence_of_all_elements_located((By.XPATH, "//tbody/tr"))
        )

        rows = driver.find_elements(By.XPATH, "//tbody/tr")

        symbols = []
        for r in rows:
            tds = r.find_elements(By.TAG_NAME, "td")
            if not tds:
                continue

            raw = tds[0].text.strip().upper()   # ví dụ: 'HPG*', 'POW**', 'VN30'
            sym = re.sub(r"\*+$", "", raw)      # 'HPG*' -> 'HPG', 'POW**' -> 'POW'

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


#The code below divides the streamlit page into 5 columns. The first two columns
#have a date picker option to select start and end dates and the the other three
#have dropdown selection boxes for duration, interval, and type of plot.

def tab2():
    st.title("Chart")
    st.write(ticker)
    
    st.write("Set duration to '-' to select date range")
    
    c1, c2, c3, c4,c5 = st.columns((1,1,1,1,1))
    
    with c1:
        
        start_date = st.date_input("Start date", datetime.today().date() - timedelta(days=30))
        
    with c2:
        
        end_date = st.date_input("End date", datetime.today().date())        
        
    with c3:
        
        duration = st.selectbox("Select duration", ['-', '1Mo', '3Mo', '6Mo', 'YTD','1Y', '3Y','5Y', 'MAX'])          
        
    with c4: 
        
        inter = st.selectbox("Select interval", ['1d', '1mo'])
        
    with c5:
        
        plot = st.selectbox("Select Plot", ['Line', 'Candle'])
        
 
    @st.cache             
    def getchartdata(ticker):
        SMA = yf.download(ticker, period = 'MAX')
        SMA['SMA'] = SMA['Close'].rolling(50).mean()
        SMA = SMA.reset_index()
        SMA = SMA[['Date', 'SMA']]
        
        if duration != '-':        
            chartdata1 = yf.download(ticker, period = duration, interval = inter)
            chartdata1 = chartdata1.reset_index()
            chartdata1 = chartdata1.merge(SMA, on='Date', how='left')
            return chartdata1
        else:
            chartdata2 = yf.download(ticker, start_date, end_date, interval = inter)
            chartdata2 = chartdata2.reset_index()
            chartdata2 = chartdata2.merge(SMA, on='Date', how='left')                             
            return chartdata2
        
        
    if ticker != '-':
            chartdata = getchartdata(ticker) 
            
                       
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            
            if plot == 'Line':
                fig.add_trace(go.Scatter(x=chartdata['Date'], y=chartdata['Close'], mode='lines', 
                                         name = 'Close'), secondary_y = False)
            else:
                fig.add_trace(go.Candlestick(x = chartdata['Date'], open = chartdata['Open'], 
                                             high = chartdata['High'], low = chartdata['Low'], close = chartdata['Close'], name = 'Candle'))
              
                    
            fig.add_trace(go.Scatter(x=chartdata['Date'], y=chartdata['SMA'], mode='lines', name = '50-day SMA'), secondary_y = False)
            
            fig.add_trace(go.Bar(x = chartdata['Date'], y = chartdata['Volume'], name = 'Volume'), secondary_y = True)

            fig.update_yaxes(range=[0, chartdata['Volume'].max()*3], showticklabels=False, secondary_y=True)
        
      
            st.plotly_chart(fig)
           
             

#==============================================================================
# Tab 3 Statistics
#==============================================================================

def tab3():
     st.title("Statistics")
     st.write(ticker)
     c1, c2 = st.columns(2)
     
     with c1:
         st.header("Valuation Measures")
         def getvaluation(ticker):
                 return si.get_stats_valuation(ticker)
    
         if ticker != '-':
                valuation = getvaluation(ticker)
                valuation[1] = valuation[1].astype(str)
                valuation = valuation.rename(columns = {0: 'Attribute', 1: ''})
                valuation.set_index('Attribute', inplace=True)
                st.table(valuation)
                
        
         st.header("Financial Highlights")
         st.subheader("Fiscal Year")
         
         def getstats(ticker):
                 return si.get_stats(ticker)
         
         if ticker != '-':
                stats = getstats(ticker)
                stats['Value'] = stats['Value'].astype(str)
                stats.set_index('Attribute', inplace=True)
                st.table(stats.iloc[29:31,])
                
        
         st.subheader("Profitability")
         
         if ticker != '-':
                stats = getstats(ticker)
                stats['Value'] = stats['Value'].astype(str)
                stats.set_index('Attribute', inplace=True)
                st.table(stats.iloc[31:33,])
                
         st.subheader("Management Effectiveness")
         
         if ticker != '-':
                stats = getstats(ticker)
                stats['Value'] = stats['Value'].astype(str)
                stats.set_index('Attribute', inplace=True)
                st.table(stats.iloc[33:35,])
         
         st.subheader("Income Statement")
         
         if ticker != '-':
                stats = getstats(ticker)
                stats['Value'] = stats['Value'].astype(str)
                stats.set_index('Attribute', inplace=True)
                st.table(stats.iloc[35:43,])  
            
         st.subheader("Balance Sheet")
         
         if ticker != '-':
                stats = getstats(ticker)
                stats['Value'] = stats['Value'].astype(str)
                stats.set_index('Attribute', inplace=True)
                st.table(stats.iloc[43:49,])
         
         st.subheader("Cash Flow Statement")
         
         if ticker != '-':
                stats = getstats(ticker)
                stats['Value'] = stats['Value'].astype(str)
                stats.set_index('Attribute', inplace=True)
                st.table(stats.iloc[49:,])
         
        
                           
     with c2:
         st.header("Trading Information")
         
         st.subheader("Stock Price History")
                  
         if ticker != '-':
                stats = getstats(ticker)
                stats['Value'] = stats['Value'].astype(str)
                stats.set_index('Attribute', inplace=True)
                st.table(stats.iloc[:7,])
         
         st.subheader("Share Statistics")
                  
         if ticker != '-':
                stats = getstats(ticker)
                stats['Value'] = stats['Value'].astype(str)
                stats.set_index('Attribute', inplace=True)
                st.table(stats.iloc[7:19,])
         
         st.subheader("Dividends & Splits")
                  
         if ticker != '-':
                stats = getstats(ticker)
                stats['Value'] = stats['Value'].astype(str)
                stats.set_index('Attribute', inplace=True)
                st.table(stats.iloc[19:29,])


#==============================================================================
# Tab 4 Financials
#==============================================================================

def tab4():
      st.title("Financials")
      st.write(ticker)
      
      statement = st.selectbox("Show", ['Income Statement', 'Balance Sheet', 'Cash Flow'])
      period = st.selectbox("Period", ['Yearly', 'Quarterly'])
      
      @st.cache
      def getyearlyincomestatement(ticker):
            return si.get_income_statement(ticker)
      
      @st.cache
      def getquarterlyincomestatement(ticker):
            return si.get_income_statement(ticker, yearly = False)
      
      @st.cache
      def getyearlybalancesheet(ticker):
            return si.get_balance_sheet(ticker)
      
      @st.cache
      def getquarterlybalancesheet(ticker):
            return si.get_balance_sheet(ticker, yearly = False)      

      @st.cache
      def getyearlycashflow(ticker):
            return si.get_cash_flow(ticker)
      
      @st.cache
      def getquarterlycashflow(ticker):
            return si.get_cash_flow(ticker, yearly = False)
        
          
      if ticker != '-' and statement == 'Income Statement' and period == 'Yearly':
                data = getyearlyincomestatement(ticker)
                st.table(data)
            
      if ticker != '-' and statement == 'Income Statement' and period == 'Quarterly':
                data = getquarterlyincomestatement(ticker)
                st.table(data)            

      if ticker != '-' and statement == 'Balance Sheet' and period == 'Yearly':
                data = getyearlybalancesheet(ticker)
                st.table(data)            
      
      if ticker != '-' and statement == 'Balance Sheet' and period == 'Quarterly':
                data = getquarterlybalancesheet(ticker)
                st.table(data)        
      
      if ticker != '-' and statement == 'Cash Flow' and period == 'Yearly':
                data = getyearlycashflow(ticker)
                st.table(data)        
      
      if ticker != '-' and statement == 'Cash Flow' and period == 'Quarterly':
                data = getquarterlycashflow(ticker)
                st.table(data)      


#==============================================================================
# Tab 5 Analysis
#==============================================================================

def tab5():
      st.title("Analysis")
      st.write("Currency in USD")
      st.write(ticker)
      
      @st.cache
      def getanalysis(ticker):
            analysis_dict = si.get_analysts_info(ticker)
            return analysis_dict.items()
 
           
      if ticker != '-':           
           for i in range(6):
            analysis = getanalysis(ticker)
            df = pd.DataFrame(list(analysis)[i][1])
            st.table(df)
            

#==============================================================================
# Tab 6 Monte Carlo Simulation
#==============================================================================

def tab6():
     st.title("Monte Carlo Simulation")
     st.write(ticker)
     
     simulations = st.selectbox("Number of Simulations (n)", [200, 500, 1000])
     time_horizon = st.selectbox("Time Horizon (t)", [30, 60, 90])
     
     @st.cache
     def montecarlo(ticker, time_horizon, simulations):
     
         end_date = datetime.now().date()
         start_date = end_date - timedelta(days=30)
     
         stock_price = si.get_data(ticker, start_date, end_date)
         close_price = stock_price['close']
     
         daily_return = close_price.pct_change()
         daily_volatility = np.std(daily_return)
     
         simulation_df = pd.DataFrame()
     
         for i in range(simulations):        
                next_price = []
                last_price = close_price[-1]
    
                for x in range(time_horizon):
                      future_return = np.random.normal(0, daily_volatility)
                      future_price = last_price * (1 + future_return)
                      next_price.append(future_price)
                      last_price = future_price
    
                simulation_df[i] = next_price
                
         return simulation_df   

     if ticker != '-':
         mc = montecarlo(ticker, time_horizon, simulations)
                  
         end_date = datetime.now().date()
         start_date = end_date - timedelta(days=30)
         
         stock_price = si.get_data(ticker, start_date, end_date)
         close_price = stock_price['close']
         
         fig, ax = plt.subplots(figsize=(15, 10))
         
         ax.plot(mc)
         plt.title('Monte Carlo simulation for ' + str(ticker) + ' stock price in next ' + str(time_horizon) + ' days')
         plt.xlabel('Day')
         plt.ylabel('Price')
         
         plt.axhline(y= close_price[-1], color ='red')
         plt.legend(['Current stock price is: ' + str(np.round(close_price[-1], 2))])
         ax.get_legend().legendHandles[0].set_color('red')

         st.pyplot(fig)
         
         st.subheader('Value at Risk (VaR)')
         ending_price = mc.iloc[-1:, :].values[0, ]
         fig1, ax = plt.subplots(figsize=(15, 10))
         ax.hist(ending_price, bins=50)
         plt.axvline(np.percentile(ending_price, 5), color='red', linestyle='--', linewidth=1)
         plt.legend(['5th Percentile of the Future Price: ' + str(np.round(np.percentile(ending_price, 5), 2))])
         plt.title('Distribution of the Ending Price')
         plt.xlabel('Price')
         plt.ylabel('Frequency')
         st.pyplot(fig1)
         
         future_price_95ci = np.percentile(ending_price, 5)
         VaR = close_price[-1] - future_price_95ci
         st.write('VaR at 95% confidence interval is: ' + str(np.round(VaR, 2)) + ' USD')


#==============================================================================
# Tab 7 Your Portfolio's Trend
#==============================================================================

def tab7():
      st.title("Your Portfolio's Trend")
      alltickers = si.tickers_sp500()
      selected_tickers = st.multiselect("Select tickers in your portfolio", options = alltickers, default = ['AAPL'])
      
      df = pd.DataFrame(columns=selected_tickers)
      for t in selected_tickers:
          df[t] = yf.download(t, period = '5Y')['Close']
                
      fig = px.line(df)
      st.plotly_chart(fig) 


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
        tab2()
    elif select_tab == 'Statistics':
        tab3()
    elif select_tab == 'Financials':
        tab4()
    elif select_tab == 'Analysis':
        tab5()
    elif select_tab == 'Monte Carlo Simulation':
        tab6()
    elif select_tab == "Your Portfolio's Trend":
        tab7()
       
    
if __name__ == "__main__":
    run()
