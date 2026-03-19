import pandas as pd
import ta
import ccxt
import json

class StrategyAnalyzer:
    def __init__(self, symbol='XRP/USDT', timeframe='5m', limit=200):
        self.symbol = symbol
        self.timeframe = timeframe
        self.limit = limit
        self.exchange = ccxt.binance({
            'options': {
                'defaultType': 'future'
            }
        })

    def fetch_data(self):
        """바이낸스에서 시세 데이터를 가져옵니다."""
        ohlcv = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, limit=self.limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df

    def add_indicators(self, df):
        """기술적 지표를 추가합니다."""
        # RSI
        df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
        
        # Stochastic RSI (더 민감한 과매수/과매도)
        stoch = ta.momentum.StochRSIIndicator(df['close'], window=14)
        df['stoch_k'] = stoch.stochrsi_k() * 100
        df['stoch_d'] = stoch.stochrsi_d() * 100

        # MACD
        macd = ta.trend.MACD(df['close'])
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['macd_hist'] = macd.macd_diff()

        # Bollinger Bands
        bb = ta.volatility.BollingerBands(df['close'], window=20, window_dev=2)
        df['bb_high'] = bb.bollinger_hband()
        df['bb_low'] = bb.bollinger_lband()

        # EMA
        df['ema9'] = ta.trend.EMAIndicator(df['close'], window=9).ema_indicator()
        df['ema20'] = ta.trend.EMAIndicator(df['close'], window=20).ema_indicator()
        
        # ADX (추세 강도)
        df['adx'] = ta.trend.ADXIndicator(df['high'], df['low'], df['close'], window=14).adx()

        return df

    def get_signal(self):
        """
        [고빈도 하이브리드 전략] 
        거래 빈도를 높이기 위해 ADX 임계값을 낮추고, 
        추세(EMA 크로스)와 반전(Stoch RSI) 신호를 모두 활용합니다.
        
        진입 조건:
        1. 추세 추종 (Trend Following): ADX > 18 이고 EMA 9/20 크로스 발생 시
        2. 눌림목 매수/반등 매도 (Mean Reversion): 
           - LONG: 가격이 BB 하단 근처 + Stoch RSI < 20 + EMA9가 EMA20 위에 있을 때
           - SHORT: 가격이 BB 상단 근처 + Stoch RSI > 80 + EMA9가 EMA20 아래에 있을 때
        """
        df = self.fetch_data()
        df = self.add_indicators(df)
        df.dropna(inplace=True)

        curr = df.iloc[-1]
        prev = df.iloc[-2]

        adx = curr['adx']
        rsi = curr['rsi']
        stoch_k = curr['stoch_k']
        ema9_now = curr['ema9']
        ema20_now = curr['ema20']
        ema9_prev = prev['ema9']
        ema20_prev = prev['ema20']
        price = curr['close']
        bb_high = curr['bb_high']
        bb_low = curr['bb_low']

        decision = "HOLD"
        leverage = 5 # 기본 레버리지 5배 고정
        reason = ""

        # ─── CASE 1: 강력한 추세 돌파 (ADX 18 이상 + EMA 크로스) ───
        ema_gold_cross = (ema9_prev <= ema20_prev) and (ema9_now > ema20_now)
        ema_dead_cross = (ema9_prev >= ema20_prev) and (ema9_now < ema20_now)

        if adx > 15:
            if ema_gold_cross:
                decision = "LONG"
                reason = f"🚀 [추세돌파] ADX {adx:.1f} 돌파 + EMA 골든크로스 발생"
            elif ema_dead_cross:
                decision = "SHORT"
                reason = f"📉 [추세돌파] ADX {adx:.1f} 돌파 + EMA 데스크로스 발생"

        # ─── CASE 2: 추세 내 눌림목/반등 (EMA 정배열/역배열 중 과매수/과매도) ───
        if decision == "HOLD":
            # LONG 눌림목: 상승 추세 중(EMA9 > EMA20) + 과매동(Stoch < 20) + BB 하단 근접
            if ema9_now > ema20_now and stoch_k < 20 and price < (bb_low * 1.01):
                decision = "LONG"
                reason = f"💰 [눌림목] 상승추세 중 과매도 도달 (Stoch:{stoch_k:.1f}, BB하단근접)"
            
            # SHORT 반등: 하락 추세 중(EMA9 < EMA20) + 과매수(Stoch > 80) + BB 상단 근접
            elif ema9_now < ema20_now and stoch_k > 80 and price > (bb_high * 0.99):
                decision = "SHORT"
                reason = f"🔥 [기술적반등] 하락추세 중 과매수 도달 (Stoch:{stoch_k:.1f}, BB상단근접)"

        # ─── CASE 3: 극단적 과매수/과매도 반전 (RSI 기준, 추세 없을 때만) ───
        if decision == "HOLD" and adx < 20:
            if rsi < 30:
                decision = "LONG"
                reason = f"⚡ [극단과매도] RSI {rsi:.1f} 도달. 기술적 반등 기대."
            elif rsi > 70:
                decision = "SHORT"
                reason = f"❄️ [극단과매수] RSI {rsi:.1f} 도달. 기술적 조정 기대."

        result = {
            "decision": decision,
            "leverage": leverage,
            "reason": reason,
            "adx": round(adx, 2),
            "rsi": round(rsi, 2),
            "stoch_k": round(stoch_k, 2),
            "price": round(price, 6)
        }

        return json.dumps(result)

if __name__ == "__main__":
    analyzer = StrategyAnalyzer()
    print("Testing Active Hybrid Strategy Analyzer...")
    signal = analyzer.get_signal()
    print(json.dumps(json.loads(signal), indent=2, ensure_ascii=False))
