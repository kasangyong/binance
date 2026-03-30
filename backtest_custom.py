import ccxt
import pandas as pd
import ta
from datetime import datetime, timezone

print("=" * 60)
print("XRP/USDT 백테스트: 현재 전략 / 잔고 100% / 레버리지 10배")
print("기간: 2025-03-01 ~ 2026-03-01")
print("=" * 60)

exchange = ccxt.binance({'options': {'defaultType': 'future'}})

since = exchange.parse8601('2025-03-01T00:00:00Z')
until = exchange.parse8601('2026-03-01T00:00:00Z')

print("데이터 수집 중 (5분봉, 약 1년)...")
all_ohlcv = []
fetch_since = since
while True:
    ohlcv = exchange.fetch_ohlcv('XRP/USDT', '5m', since=fetch_since, limit=1000)
    if not ohlcv:
        break
    all_ohlcv.extend(ohlcv)
    fetch_since = ohlcv[-1][0] + 1
    if ohlcv[-1][0] >= until:
        break
    if len(ohlcv) < 1000:
        break

df = pd.DataFrame(all_ohlcv, columns=['timestamp','open','high','low','close','volume'])
df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
df = df[df['timestamp'] <= pd.Timestamp('2026-03-01')].reset_index(drop=True)
print(f"수집 완료: {len(df)}개 캔들 ({df['timestamp'].iloc[0]} ~ {df['timestamp'].iloc[-1]})\n")

# 지표 계산
df['rsi']     = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
stoch         = ta.momentum.StochRSIIndicator(df['close'], window=14)
df['stoch_k'] = stoch.stochrsi_k() * 100
bb            = ta.volatility.BollingerBands(df['close'], window=20, window_dev=2)
df['bb_high'] = bb.bollinger_hband()
df['bb_low']  = bb.bollinger_lband()
df['ema9']    = ta.trend.EMAIndicator(df['close'], window=9).ema_indicator()
df['ema20']   = ta.trend.EMAIndicator(df['close'], window=20).ema_indicator()
df['adx']     = ta.trend.ADXIndicator(df['high'], df['low'], df['close'], window=14).adx()
df.dropna(inplace=True)
df.reset_index(drop=True, inplace=True)

# 백테스트 파라미터
START_BALANCE = 152.0   # 초기 자본 (USDT)
LEVERAGE      = 10      # 레버리지
SL_PCT        = 0.015   # 손절 1.5%
TP_PCT        = 0.035   # 익절 3.5%
TRADE_RATIO   = 1.0     # 잔고 100%
FEE           = 0.0004  # 수수료 0.04%

balance     = START_BALANCE
position    = None
entry_price = 0
trades      = []
max_balance = START_BALANCE
max_drawdown = 0

for i in range(1, len(df)):
    curr = df.iloc[i]
    prev = df.iloc[i-1]

    price     = curr['close']
    high      = curr['high']
    low       = curr['low']
    adx       = curr['adx']
    rsi       = curr['rsi']
    stoch_k   = curr['stoch_k']
    ema9_now  = curr['ema9']
    ema20_now = curr['ema20']
    ema9_prev = prev['ema9']
    ema20_prev= prev['ema20']
    bb_high   = curr['bb_high']
    bb_low    = curr['bb_low']

    # 포지션 보유 중: SL/TP 체크
    if position:
        if position == 'LONG':
            sl_hit = low  <= entry_price * (1 - SL_PCT)
            tp_hit = high >= entry_price * (1 + TP_PCT)
            exit_p = entry_price * (1 - SL_PCT) if sl_hit else entry_price * (1 + TP_PCT)
        else:
            sl_hit = high >= entry_price * (1 + SL_PCT)
            tp_hit = low  <= entry_price * (1 - TP_PCT)
            exit_p = entry_price * (1 + SL_PCT) if sl_hit else entry_price * (1 - TP_PCT)

        if tp_hit or sl_hit:
            reason = 'TP' if tp_hit else 'SL'
            if position == 'LONG':
                pnl_pct = (exit_p - entry_price) / entry_price
            else:
                pnl_pct = (entry_price - exit_p) / entry_price

            trade_amount = balance * TRADE_RATIO
            pnl = trade_amount * LEVERAGE * pnl_pct - trade_amount * LEVERAGE * FEE * 2
            balance += pnl
            trades.append({'reason': reason, 'pnl': pnl, 'balance': balance})

            # 최대 낙폭 계산
            if balance > max_balance:
                max_balance = balance
            drawdown = (max_balance - balance) / max_balance * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown

            position = None

            if balance <= 0:
                print("💀 계좌 강제 청산! 잔고 0 이하")
                break
        continue

    # 신호 판단 (현재 전략과 동일)
    ema_gold = (ema9_prev <= ema20_prev) and (ema9_now > ema20_now)
    ema_dead = (ema9_prev >= ema20_prev) and (ema9_now < ema20_now)

    decision = 'HOLD'
    if adx > 15:
        if ema_gold:
            decision = 'LONG'
        elif ema_dead:
            decision = 'SHORT'

    if decision == 'HOLD':
        if ema9_now > ema20_now and stoch_k < 20 and price < bb_low * 1.01:
            decision = 'LONG'
        elif ema9_now < ema20_now and stoch_k > 80 and price > bb_high * 0.99:
            decision = 'SHORT'

    if decision == 'HOLD' and adx < 20:
        if rsi < 30:
            decision = 'LONG'
        elif rsi > 70:
            decision = 'SHORT'

    if decision != 'HOLD' and balance > 0:
        position = decision
        entry_price = price

# 결과 출력
print("=" * 60)
print("백테스트 결과")
print("=" * 60)

total    = len(trades)
wins     = sum(1 for t in trades if t['pnl'] > 0)
losses   = total - wins
wr       = wins / total * 100 if total > 0 else 0
ret      = (balance - START_BALANCE) / START_BALANCE * 100
total_fee= sum(152 * TRADE_RATIO * LEVERAGE * FEE * 2 for _ in trades)

print(f"기간         : 2025-03-01 ~ 2026-03-01")
print(f"초기 자본    : {START_BALANCE:.2f} USDT")
print(f"최종 잔고    : {balance:.2f} USDT")
print(f"총 수익률    : {ret:+.2f}%")
print(f"최대 낙폭    : -{max_drawdown:.2f}%")
print(f"총 거래 수   : {total}회")
print(f"승 / 패      : {wins}승 {losses}패")
print(f"승률         : {wr:.1f}%")
print()

# 비교: 현재 설정 (잔고 20% + 레버리지 5배)
print("=" * 60)
print("비교: 현재 설정 (잔고 20% + 레버리지 5배)")
print("=" * 60)

balance2    = START_BALANCE
max_bal2    = START_BALANCE
max_dd2     = 0
trades2     = []
position2   = None
entry2      = 0

for i in range(1, len(df)):
    curr = df.iloc[i]
    prev = df.iloc[i-1]
    price     = curr['close']
    high      = curr['high']
    low       = curr['low']
    adx       = curr['adx']
    rsi       = curr['rsi']
    stoch_k   = curr['stoch_k']
    ema9_now  = curr['ema9']
    ema20_now = curr['ema20']
    ema9_prev = prev['ema9']
    ema20_prev= prev['ema20']
    bb_high   = curr['bb_high']
    bb_low    = curr['bb_low']

    if position2:
        if position2 == 'LONG':
            sl_hit = low  <= entry2 * (1 - SL_PCT)
            tp_hit = high >= entry2 * (1 + TP_PCT)
            exit_p = entry2 * (1 - SL_PCT) if sl_hit else entry2 * (1 + TP_PCT)
        else:
            sl_hit = high >= entry2 * (1 + SL_PCT)
            tp_hit = low  <= entry2 * (1 - TP_PCT)
            exit_p = entry2 * (1 + SL_PCT) if sl_hit else entry2 * (1 - TP_PCT)

        if tp_hit or sl_hit:
            pnl_pct = (exit_p - entry2) / entry2 if position2 == 'LONG' else (entry2 - exit_p) / entry2
            trade_amount = balance2 * 0.20
            pnl = trade_amount * 5 * pnl_pct - trade_amount * 5 * FEE * 2
            balance2 += pnl
            trades2.append(pnl)
            if balance2 > max_bal2:
                max_bal2 = balance2
            dd = (max_bal2 - balance2) / max_bal2 * 100
            if dd > max_dd2:
                max_dd2 = dd
            position2 = None
        continue

    ema_gold = (ema9_prev <= ema20_prev) and (ema9_now > ema20_now)
    ema_dead = (ema9_prev >= ema20_prev) and (ema9_now < ema20_now)
    decision = 'HOLD'
    if adx > 15:
        if ema_gold: decision = 'LONG'
        elif ema_dead: decision = 'SHORT'
    if decision == 'HOLD':
        if ema9_now > ema20_now and stoch_k < 20 and price < bb_low * 1.01: decision = 'LONG'
        elif ema9_now < ema20_now and stoch_k > 80 and price > bb_high * 0.99: decision = 'SHORT'
    if decision == 'HOLD' and adx < 20:
        if rsi < 30: decision = 'LONG'
        elif rsi > 70: decision = 'SHORT'
    if decision != 'HOLD':
        position2 = decision
        entry2 = price

w2 = sum(1 for t in trades2 if t > 0)
print(f"최종 잔고    : {balance2:.2f} USDT")
print(f"총 수익률    : {(balance2-START_BALANCE)/START_BALANCE*100:+.2f}%")
print(f"최대 낙폭    : -{max_dd2:.2f}%")
print(f"총 거래 수   : {len(trades2)}회")
print(f"승률         : {w2/len(trades2)*100:.1f}%" if trades2 else "거래 없음")
print()
print("=" * 60)
print("결론")
print("=" * 60)
diff = balance - balance2
print(f"잔고 100%+10배 최종: {balance:.2f} USDT  (수익률: {ret:+.2f}%,  최대낙폭: -{max_drawdown:.2f}%)")
print(f"잔고 20%+5배  최종: {balance2:.2f} USDT  (수익률: {(balance2-START_BALANCE)/START_BALANCE*100:+.2f}%,  최대낙폭: -{max_dd2:.2f}%)")
