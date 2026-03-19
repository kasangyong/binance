import streamlit as st
import pandas as pd
import time
import os
import plotly.graph_objects as go
from strategy_analyzer import StrategyAnalyzer
from dotenv import load_dotenv

st.set_page_config(page_title="Binance AI Trading Bot", page_icon="📈", layout="wide")

# 로딩 및 캐싱
@st.cache_data(ttl=60) # 1분 지난 데이터는 다시 가져오기
def get_chart_data():
    analyzer = StrategyAnalyzer(limit=100)
    df = analyzer.fetch_data()
    df = analyzer.add_indicators(df)
    return analyzer, df
    
def load_log():
    log_file = 'trade_history.log'
    if os.path.exists(log_file):
        # UTF-8 시도 후 실패 시 CP949 시도 (윈도우 환경 대응)
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                return lines[-20:]
        except UnicodeDecodeError:
            try:
                with open(log_file, 'r', encoding='cp949') as f:
                    lines = f.readlines()
                    return lines[-20:]
            except:
                return ["⚠️ 로그 파일 읽기 오류 (인코딩 불일치)"]
    return []

st.title("📈 Binance Trading Bot Dashboard")
st.markdown("XRP/USDT 고빈도 하이브리드 전략 (추세돌파 + 눌림목/반등) 모니터링")

col1, col2 = st.columns([2, 1])

analyzer, df = get_chart_data()

with col1:
    st.subheader(f"📊 {analyzer.symbol} {analyzer.timeframe.upper()} Chart & Indicators")
    
    # Plotly 캔들스틱 차트 표시
    fig = go.Figure(data=[go.Candlestick(x=df['timestamp'],
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name='Candles')])
    
    # 볼린저 밴드 선 추가
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['bb_high'], mode='lines', line=dict(color='rgba(255, 0, 0, 0.4)', width=1), name='BB High'))
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['bb_low'], mode='lines', line=dict(color='rgba(0, 0, 255, 0.4)', width=1), name='BB Low'))
    
    fig.update_layout(height=400, margin=dict(l=0, r=0, t=30, b=0), xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)
    
    # 지표 데이터프레임
    st.subheader("📋 Recent Indicators")
    # 마지막 5행, 필요한 컬럼만 (ADX, Stoch 추가)
    display_df = df[['timestamp', 'close', 'rsi', 'adx', 'stoch_k', 'macd_hist', 'bb_high', 'bb_low']].tail(7)
    st.dataframe(display_df, use_container_width=True)

with col2:
    st.subheader("🔍 Market Analysis (Live)")
    if st.button("실시간 전략 판단 및 지표 분석"):
        with st.spinner("현재 차트 데이터를 바탕으로 전략을 분석 중입니다..."):
            import json
            try:
                signal_str = analyzer.get_signal()
                signal_data = json.loads(signal_str)
                decision = signal_data.get('decision', 'N/A')
                leverage = signal_data.get('leverage', 1)
                reason = signal_data.get('reason', 'N/A')
                
                # HTML과 CSS로 직접 꾸미기 (선물 거래 맞춤 색상)
                color = "green" if decision == "LONG" else "red" if decision == "SHORT" else "gray"
                st.markdown(f"""
                <div style="padding:20px; border-radius:10px; border:1px solid #e0e0e0; text-align:center;">
                    <h3 style="color:{color};">Signal: {decision} (Leverage: {leverage}x)</h3>
                    <p style="font-size:1.1rem; color:#555;">{reason}</p>
                </div>
                """, unsafe_allow_html=True)
            except Exception as e:
                st.error(f"분석 중 오류 발생: {e}")
                
    st.markdown("---")
    st.subheader("📝 Trade History Logs")
    logs = load_log()
    if logs:
        log_text = "".join(logs)
        st.text_area("Last 20 Logs", log_text, height=300)
    else:
        st.info("Log 파일이 아직 생성되지 않았거나 비어 있습니다.")

st.markdown("---")
st.markdown("💡 *참고: 실제 거래를 수행하려면 백그라운드에서 `python trading_bot.py` 스크립트를 실행해 두어야 합니다.*")
