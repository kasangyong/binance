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
        [ADX+EMA 추세 전략 - 백테스트 1위]
        ADX > 25 (강한 추세) + EMA9 방향 확인으로 진입.
        강한 추세에서만 진입하여 오신호를 최소화.

        진입 조건:
        - LONG: ADX > 25 + EMA9 > EMA20 + EMA9 상승 중 (첫 신호만)
        - SHORT: ADX > 25 + EMA9 < EMA20 + EMA9 하락 중 (첫 신호만)
        """
        df = self.fetch_data()
        df = self.add_indicators(df)
        df.dropna(inplace=True)

        curr = df.iloc[-1]
        prev = df.iloc[-2]

        adx       = curr['adx']
        rsi       = curr['rsi']
        stoch_k   = curr['stoch_k']
        ema9_now  = curr['ema9']
        ema20_now = curr['ema20']
        ema9_prev = prev['ema9']
        price     = curr['close']

        decision = "HOLD"
        leverage = 5
        reason   = ""

        # ─── ADX+EMA 추세 전략 (ADX > 25) ───
        if adx > 25:
            # LONG: EMA9가 EMA20 위 + EMA9 상승 중 + 이전 봉에서는 조건 미충족 (첫 신호)
            long_cond  = (ema9_now > ema20_now) and (ema9_now > ema9_prev)
            short_cond = (ema9_now < ema20_now) and (ema9_now < ema9_prev)

            prev2_ema9  = df.iloc[-3]['ema9']
            prev2_ema20 = df.iloc[-3]['ema20']
            prev_long  = (ema9_prev > prev['ema20']) and (ema9_prev > prev2_ema9)
            prev_short = (ema9_prev < prev['ema20']) and (ema9_prev < prev2_ema9)

            if long_cond and not prev_long:
                decision = "LONG"
                reason = f"🚀 [ADX추세] ADX {adx:.1f} + EMA9 상승추세 진입"
            elif short_cond and not prev_short:
                decision = "SHORT"
                reason = f"📉 [ADX추세] ADX {adx:.1f} + EMA9 하락추세 진입"

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
