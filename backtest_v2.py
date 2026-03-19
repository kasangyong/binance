import ccxt
import pandas as pd
import ta
import itertools
from datetime import datetime, timedelta

print("=" * 65)
print("� XRP/USDT 최적 전략 탐색기 (최근 30일)")
print("=" * 65)

# -------------------------------------------------------
# 데이터 수집 (1회만)
# -------------------------------------------------------
exchange = ccxt.binance({'options': {'defaultType': 'future'}})
since = exchange.parse8601((datetime.utcnow() - timedelta(days=60)).strftime('%Y-%m-%dT%H:%M:%SZ'))
all_ohlcv = []
fetch_since = since
print("📡 데이터 수집 중...")
while True:
    ohlcv = exchange.fetch_ohlcv('XRP/USDT', '15m', since=fetch_since, limit=1000)
    if not ohlcv:
        break
    all_ohlcv.extend(ohlcv)
    fetch_since = ohlcv[-1][0] + 1
    if len(ohlcv) < 1000:
        break

df_raw = pd.DataFrame(all_ohlcv, columns=['timestamp','open','high','low','close','volume'])
df_raw['timestamp'] = pd.to_datetime(df_raw['timestamp'], unit='ms')
df_raw = df_raw.drop_duplicates('timestamp').reset_index(drop=True)
print(f"✅ {len(df_raw)}개 캔들 수집 완료\n")

# -------------------------------------------------------
# 지표 계산 (한번만)
# -------------------------------------------------------
df = df_raw.copy()
df['rsi']        = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
macd             = ta.trend.MACD(df['close'])
df['macd_hist']  = macd.macd_diff()
df['macd_line']  = macd.macd()
df['macd_signal']= macd.macd_signal()
bb               = ta.volatility.BollingerBands(df['close'], window=20, window_dev=2)
df['bb_high']    = bb.bollinger_hband()
df['bb_low']     = bb.bollinger_lband()
df['bb_mid']     = bb.bollinger_mavg()
df['ema20']      = ta.trend.EMAIndicator(df['close'], window=20).ema_indicator()
df['ema50']      = ta.trend.EMAIndicator(df['close'], window=50).ema_indicator()
df['ema9']       = ta.trend.EMAIndicator(df['close'], window=9).ema_indicator()
df['atr']        = ta.volatility.AverageTrueRange(df['high'],df['low'],df['close'],window=14).average_true_range()
df['adx']        = ta.trend.ADXIndicator(df['high'],df['low'],df['close'],window=14).adx()
stoch            = ta.momentum.StochRSIIndicator(df['close'], window=14)
df['stoch_k']    = stoch.stochrsi_k() * 100
df.dropna(inplace=True)

START   = 20.0
TRADE   = 10.0
FEE     = 0.0004

# -------------------------------------------------------
# 공통 백테스트 함수
# -------------------------------------------------------
def backtest(signals_long, signals_short, df, sl=0.03, tp=0.05, lev=3):
    balance  = START
    position = None
    entry_price = 0
    trades   = []

    for i in range(len(df)):
        row   = df.iloc[i]
        price = row['close']
        high  = row['high']
        low   = row['low']
        long_sig  = signals_long[i]
        short_sig = signals_short[i]

        if position:
            if position == 'LONG':
                sl_hit = low  <= entry_price * (1 - sl)
                tp_hit = high >= entry_price * (1 + tp)
            else:
                sl_hit = high >= entry_price * (1 + sl)
                tp_hit = low  <= entry_price * (1 - tp)

            exit_p = None
            reason = None
            if tp_hit:
                reason = 'TP'
                exit_p = entry_price*(1+tp) if position=='LONG' else entry_price*(1-tp)
            elif sl_hit:
                reason = 'SL'
                exit_p = entry_price*(1-sl) if position=='LONG' else entry_price*(1+sl)
            elif (position=='LONG' and short_sig) or (position=='SHORT' and long_sig):
                reason = 'Flip'
                exit_p = price

            if reason:
                pnl_pct = (exit_p-entry_price)/entry_price if position=='LONG' else (entry_price-exit_p)/entry_price
                net = TRADE*lev*pnl_pct - TRADE*lev*FEE*2
                balance += net
                trades.append(net)
                position = None
                if reason=='Flip':
                    signal_dir = 'LONG' if long_sig else 'SHORT'
                    if balance >= TRADE:
                        position = signal_dir
                        entry_price = price
        else:
            if long_sig and balance >= TRADE:
                position = 'LONG'; entry_price = price
            elif short_sig and balance >= TRADE:
                position = 'SHORT'; entry_price = price

    if not trades:
        return {'n':0,'wr':0,'ret':(balance-START)/START*100,'bal':balance}
    wins = sum(1 for t in trades if t>0)
    return {
        'n':   len(trades),
        'wr':  wins/len(trades)*100,
        'ret': (balance-START)/START*100,
        'bal': balance
    }

results = []

# ═══════════════════════════════════════════════════════
# 전략 1: EMA 크로스오버 (추세추종)
# EMA9가 EMA20을 상향돌파 → LONG
# EMA9가 EMA20을 하향돌파 → SHORT
# ═══════════════════════════════════════════════════════
for sl, tp, lev in [(0.02,0.04,3),(0.03,0.06,3),(0.02,0.05,5),(0.03,0.05,3)]:
    long_s  = (df['ema9'] > df['ema20']) & (df['ema9'].shift(1) <= df['ema20'].shift(1))
    short_s = (df['ema9'] < df['ema20']) & (df['ema9'].shift(1) >= df['ema20'].shift(1))
    r = backtest(long_s.values, short_s.values, df, sl, tp, lev)
    results.append({'Strategy':'EMA 크로스(9/20)', 'SL':sl, 'TP':tp, 'Lev':lev, **r})

# ═══════════════════════════════════════════════════════
# 전략 2: EMA 크로스오버 (20/50)
# ═══════════════════════════════════════════════════════
for sl, tp, lev in [(0.02,0.04,3),(0.03,0.06,3),(0.03,0.05,3),(0.04,0.08,2)]:
    long_s  = (df['ema20'] > df['ema50']) & (df['ema20'].shift(1) <= df['ema50'].shift(1))
    short_s = (df['ema20'] < df['ema50']) & (df['ema20'].shift(1) >= df['ema50'].shift(1))
    r = backtest(long_s.values, short_s.values, df, sl, tp, lev)
    results.append({'Strategy':'EMA 크로스(20/50)', 'SL':sl, 'TP':tp, 'Lev':lev, **r})

# ═══════════════════════════════════════════════════════
# 전략 3: MACD 크로스 (MACD선이 시그널선 상향돌파)
# ═══════════════════════════════════════════════════════
for sl, tp, lev in [(0.02,0.04,3),(0.03,0.06,3),(0.02,0.05,5),(0.03,0.05,3)]:
    long_s  = (df['macd_line'] > df['macd_signal']) & (df['macd_line'].shift(1) <= df['macd_signal'].shift(1))
    short_s = (df['macd_line'] < df['macd_signal']) & (df['macd_line'].shift(1) >= df['macd_signal'].shift(1))
    r = backtest(long_s.values, short_s.values, df, sl, tp, lev)
    results.append({'Strategy':'MACD 크로스', 'SL':sl, 'TP':tp, 'Lev':lev, **r})

# ═══════════════════════════════════════════════════════
# 전략 4: 볼린저 밴드 브레이크아웃 (추세추종)
# 가격이 상단 돌파 → LONG (강한 상승 추세)
# 가격이 하단 하향돌파 → SHORT (강한 하락 추세)
# ═══════════════════════════════════════════════════════
for sl, tp, lev in [(0.02,0.04,3),(0.03,0.06,3),(0.02,0.05,3),(0.03,0.05,5)]:
    long_s  = (df['close'] > df['bb_high']) & (df['close'].shift(1) <= df['bb_high'].shift(1))
    short_s = (df['close'] < df['bb_low'])  & (df['close'].shift(1) >= df['bb_low'].shift(1))
    r = backtest(long_s.values, short_s.values, df, sl, tp, lev)
    results.append({'Strategy':'BB 브레이크아웃', 'SL':sl, 'TP':tp, 'Lev':lev, **r})

# ═══════════════════════════════════════════════════════
# 전략 5: RSI + MACD 복합 (기존 전략 개선)
# ═══════════════════════════════════════════════════════
for rsi_lo, rsi_hi, sl, tp, lev in [
    (40,60,0.03,0.05,3),(35,65,0.03,0.06,3),
    (45,55,0.02,0.04,3),(40,60,0.02,0.05,5)]:
    long_s  = (df['rsi'] < rsi_lo) & (df['macd_hist'] > 0)
    short_s = (df['rsi'] > rsi_hi) & (df['macd_hist'] < 0)
    r = backtest(long_s.values, short_s.values, df, sl, tp, lev)
    results.append({'Strategy':f'RSI+MACD({rsi_lo}/{rsi_hi})', 'SL':sl, 'TP':tp, 'Lev':lev, **r})

# ═══════════════════════════════════════════════════════
# 전략 6: ADX + EMA 추세 필터
# ADX > 25 (강한 추세) + EMA9 방향으로만 진입
# ═══════════════════════════════════════════════════════
for sl, tp, lev in [(0.02,0.04,3),(0.03,0.06,3),(0.03,0.05,3),(0.02,0.05,5)]:
    strong_trend = df['adx'] > 25
    long_s  = strong_trend & (df['ema9'] > df['ema20']) & (df['ema9'] > df['ema9'].shift(1))
    short_s = strong_trend & (df['ema9'] < df['ema20']) & (df['ema9'] < df['ema9'].shift(1))
    # 연속 신호 → 첫 신호만 (크로스 시점)
    long_s  = long_s  & ~long_s.shift(1).fillna(False)
    short_s = short_s & ~short_s.shift(1).fillna(False)
    r = backtest(long_s.values, short_s.values, df, sl, tp, lev)
    results.append({'Strategy':'ADX+EMA 추세', 'SL':sl, 'TP':tp, 'Lev':lev, **r})

# ═══════════════════════════════════════════════════════
# 전략 7: BB + RSI + ADX 복합
# ═══════════════════════════════════════════════════════
for sl, tp, lev in [(0.02,0.04,3),(0.03,0.05,3),(0.02,0.05,5),(0.03,0.06,3)]:
    long_s  = (df['rsi'] < 45) & (df['close'] <= df['bb_mid']) & (df['adx'] > 20) & (df['macd_hist'] > 0)
    short_s = (df['rsi'] > 55) & (df['close'] >= df['bb_mid']) & (df['adx'] > 20) & (df['macd_hist'] < 0)
    long_s  = long_s  & ~long_s.shift(1).fillna(False)
    short_s = short_s & ~short_s.shift(1).fillna(False)
    r = backtest(long_s.values, short_s.values, df, sl, tp, lev)
    results.append({'Strategy':'BB+RSI+ADX', 'SL':sl, 'TP':tp, 'Lev':lev, **r})

# ═══════════════════════════════════════════════════════
# 결과 정렬 & 출력
# ═══════════════════════════════════════════════════════
rdf = pd.DataFrame(results)
rdf = rdf.sort_values('ret', ascending=False)

print("=" * 65)
print("🏆 전략 성과 순위 (수익률 기준 상위 15개)")
print("=" * 65)
print(f"{'순위':<4} {'전략':20} {'SL':>5} {'TP':>5} {'레':>4} {'거래':>4} {'승률':>7} {'수익률':>8} {'잔고':>8}")
print("-" * 65)
for i, (_, row) in enumerate(rdf.head(15).iterrows(), 1):
    emoji = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else f"{i:2}위"
    print(f"{emoji:<4} {row['Strategy']:20} {row['SL']*100:>4.0f}% {row['TP']*100:>4.0f}% "
          f"{row['Lev']:>3}x {row['n']:>4.0f}회 {row['wr']:>6.1f}% {row['ret']:>+7.2f}% {row['bal']:>8.4f}")

best = rdf.iloc[0]
print()
print("=" * 65)
print(f"🏆 최고 전략: [{best['Strategy']}]")
print(f"   손절: -{best['SL']*100:.0f}% | 익절: +{best['TP']*100:.0f}% | 레버리지: {best['Lev']}x")
print(f"   총 거래: {best['n']:.0f}회 | 승률: {best['wr']:.1f}% | 수익률: {best['ret']:+.2f}%")
print(f"   시작 잔고 20 USDT → 최종 잔고: {best['bal']:.4f} USDT")

# 수익 나는 전략 개수
profitable = rdf[rdf['ret'] > 0]
print(f"\n📊 전체 {len(rdf)}개 전략 중 수익 나는 전략: {len(profitable)}개")
