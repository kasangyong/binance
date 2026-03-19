import ccxt
import pandas as pd
import ta
from datetime import datetime, timedelta

print("=" * 60)
print("📊 XRP/USDT 15분봉 백테스트 (최근 30일)")
print("=" * 60)

# 바이낸스에서 최근 30일 15분봉 데이터 수집
# 30일 × 24시간 × 4(15분봉) = 2880개
exchange = ccxt.binance({'options': {'defaultType': 'future'}})

since = exchange.parse8601((datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ'))
all_ohlcv = []
fetch_since = since

print("데이터 수집 중... (약 2880개 캔들)")
while True:
    ohlcv = exchange.fetch_ohlcv('XRP/USDT', '15m', since=fetch_since, limit=1000)
    if not ohlcv:
        break
    all_ohlcv.extend(ohlcv)
    fetch_since = ohlcv[-1][0] + 1
    if len(ohlcv) < 1000:
        break

df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
df = df.drop_duplicates('timestamp').reset_index(drop=True)

print(f"총 {len(df)}개 캔들 수집 완료")
print(f"기간: {df['timestamp'].iloc[0]} ~ {df['timestamp'].iloc[-1]}")
print()

# 지표 계산
df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
macd = ta.trend.MACD(df['close'])
df['macd_hist'] = macd.macd_diff()
bb = ta.volatility.BollingerBands(df['close'], window=20, window_dev=2)
df['bb_high'] = bb.bollinger_hband()
df['bb_low'] = bb.bollinger_lband()
df.dropna(inplace=True)

# -------------------------------------------------------
# 현재 봇의 AI 로직을 규칙 기반으로 근사 (Approximation)
# AI가 보는 기준과 동일하게 설정:
#   RSI < 35 + MACD > 0 → LONG
#   RSI > 65 + MACD < 0 → SHORT
#   나머지             → HOLD
# -------------------------------------------------------
def rule_based_signal(row):
    rsi = row['rsi']
    macd_hist = row['macd_hist']
    price = row['close']
    bb_low = row['bb_low']
    bb_high = row['bb_high']

    near_bb_low = price <= bb_low * 1.01   # BB하단 근처(1% 이내)
    near_bb_high = price >= bb_high * 0.99  # BB상단 근처(1% 이내)

    if rsi < 35 and macd_hist > 0:
        return 'LONG', 3
    elif rsi > 65 and macd_hist < 0:
        return 'SHORT', 3
    elif rsi < 40 and near_bb_low and macd_hist > 0:
        return 'LONG', 2
    elif rsi > 60 and near_bb_high and macd_hist < 0:
        return 'SHORT', 2
    else:
        return 'HOLD', 1

# 신호 생성
df['signal'], df['leverage'] = zip(*df.apply(rule_based_signal, axis=1))

# -------------------------------------------------------
# 거래 시뮬레이션 (포지션 중복 방지)
# -------------------------------------------------------
balance = 20.0           # 시작 잔고 20 USDT
trade_amount = 10.0      # 1회 거래 금액
fee_rate = 0.0004        # 수수료 0.04% (왕복)

trades = []
position = None  # 현재 포지션: None, 'LONG', 'SHORT'
entry_price = 0
entry_leverage = 1
entry_balance = 0

for _, row in df.iterrows():
    signal = row['signal']
    price = row['close']
    lev = row['leverage']

    # 포지션 없을 때 진입
    if position is None:
        if signal in ('LONG', 'SHORT') and balance >= trade_amount:
            position = signal
            entry_price = price
            entry_leverage = lev
            entry_balance = trade_amount
    else:
        # 반대 신호 오면 청산
        if (position == 'LONG' and signal == 'SHORT') or \
           (position == 'SHORT' and signal == 'LONG'):
            if position == 'LONG':
                pnl_pct = (price - entry_price) / entry_price
            else:
                pnl_pct = (entry_price - price) / entry_price

            pnl = trade_amount * entry_leverage * pnl_pct
            fee = trade_amount * entry_leverage * fee_rate * 2
            net_pnl = pnl - fee
            balance += net_pnl

            trades.append({
                'type': position,
                'entry': entry_price,
                'exit': price,
                'leverage': entry_leverage,
                'pnl': net_pnl,
                'balance_after': balance,
                'time': row['timestamp']
            })

            # 새 포지션 즉시 진입
            position = signal
            entry_price = price
            entry_leverage = lev
            entry_balance = trade_amount

# 결과 출력
print("=" * 60)
print(f"📈 신호 분포")
print(f"  LONG  신호: {(df['signal']=='LONG').sum()}회")
print(f"  SHORT 신호: {(df['signal']=='SHORT').sum()}회")
print(f"  HOLD  신호: {(df['signal']=='HOLD').sum()}회")
print()
print("=" * 60)
print(f"💸 거래 실적 (규칙 기반 시뮬레이션)")
print(f"  총 체결된 거래: {len(trades)}회")
if trades:
    trade_df = pd.DataFrame(trades)
    wins = trade_df[trade_df['pnl'] > 0]
    losses = trade_df[trade_df['pnl'] <= 0]
    print(f"  수익 거래: {len(wins)}회")
    print(f"  손실 거래: {len(losses)}회")
    print(f"  승률: {len(wins)/len(trades)*100:.1f}%")
    print(f"  총 수익: {trade_df['pnl'].sum():.4f} USDT")
    print(f"  최대 단일 수익: +{trade_df['pnl'].max():.4f} USDT")
    print(f"  최대 단일 손실: {trade_df['pnl'].min():.4f} USDT")
    print(f"  시작 잔고: 20.0000 USDT")
    print(f"  최종 잔고: {balance:.4f} USDT")
    print(f"  수익률: {(balance-20)/20*100:.2f}%")
    print()
    print("최근 5개 거래 내역:")
    for t in trades[-5:]:
        emoji = "✅" if t['pnl'] > 0 else "❌"
        print(f"  {emoji} {t['type']} | 진입: {t['entry']:.4f} → 청산: {t['exit']:.4f} | 레버: {t['leverage']}x | 손익: {t['pnl']:+.4f} USDT")
else:
    print("  거래 없음 (조건 미충족)")
print("=" * 60)
