import ccxt, pandas as pd, ta, sys
sys.stdout.reconfigure(encoding='utf-8')

print('=' * 65)
print('XRP/USDT 1년치 전략 탐색 (2025-03-01 ~ 2026-03-01)')
print('=' * 65)

exchange = ccxt.binance({'options': {'defaultType': 'future'}})
since = exchange.parse8601('2025-03-01T00:00:00Z')
until = exchange.parse8601('2026-03-01T00:00:00Z')
all_ohlcv = []
fetch_since = since
print('데이터 수집 중 (15분봉)...')
while True:
    ohlcv = exchange.fetch_ohlcv('XRP/USDT', '15m', since=fetch_since, limit=1000)
    if not ohlcv: break
    all_ohlcv.extend(ohlcv)
    fetch_since = ohlcv[-1][0] + 1
    if ohlcv[-1][0] >= until: break
    if len(ohlcv) < 1000: break

df = pd.DataFrame(all_ohlcv, columns=['timestamp','open','high','low','close','volume'])
df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
df = df[df['timestamp'] <= pd.Timestamp('2026-03-01')].reset_index(drop=True)
print(f'수집 완료: {len(df)}개 캔들\n')

df['rsi']         = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
macd              = ta.trend.MACD(df['close'])
df['macd_hist']   = macd.macd_diff()
df['macd_line']   = macd.macd()
df['macd_signal'] = macd.macd_signal()
bb                = ta.volatility.BollingerBands(df['close'], window=20, window_dev=2)
df['bb_high']     = bb.bollinger_hband()
df['bb_low']      = bb.bollinger_lband()
df['bb_mid']      = bb.bollinger_mavg()
df['ema9']        = ta.trend.EMAIndicator(df['close'], window=9).ema_indicator()
df['ema20']       = ta.trend.EMAIndicator(df['close'], window=20).ema_indicator()
df['ema50']       = ta.trend.EMAIndicator(df['close'], window=50).ema_indicator()
df['adx']         = ta.trend.ADXIndicator(df['high'],df['low'],df['close'],window=14).adx()
stoch             = ta.momentum.StochRSIIndicator(df['close'], window=14)
df['stoch_k']     = stoch.stochrsi_k() * 100
df.dropna(inplace=True)
df.reset_index(drop=True, inplace=True)

START = 152.0
FEE   = 0.0004

def backtest(ls, ss, df, sl, tp, lev, ratio=0.20):
    bal, pos, ep = START, None, 0
    trades, max_bal, max_dd = [], START, 0
    for i in range(len(df)):
        row = df.iloc[i]
        if pos:
            if pos == 'LONG':
                sl_hit = row['low']  <= ep*(1-sl)
                tp_hit = row['high'] >= ep*(1+tp)
                exit_p = ep*(1-sl) if sl_hit else ep*(1+tp)
            else:
                sl_hit = row['high'] >= ep*(1+sl)
                tp_hit = row['low']  <= ep*(1-tp)
                exit_p = ep*(1+sl) if sl_hit else ep*(1-tp)
            if tp_hit or sl_hit:
                pct = (exit_p-ep)/ep if pos=='LONG' else (ep-exit_p)/ep
                amt = bal*ratio
                net = amt*lev*pct - amt*lev*FEE*2
                bal += net; trades.append(net)
                if bal > max_bal: max_bal = bal
                dd = (max_bal-bal)/max_bal*100
                if dd > max_dd: max_dd = dd
                pos = None
                if bal <= 0: bal=0; break
        else:
            if ls[i] and bal>0: pos='LONG';  ep=row['close']
            elif ss[i] and bal>0: pos='SHORT'; ep=row['close']
    if not trades:
        return {'n':0,'wr':0,'ret':(bal-START)/START*100,'bal':bal,'dd':max_dd}
    w = sum(1 for t in trades if t>0)
    return {'n':len(trades),'wr':w/len(trades)*100,'ret':(bal-START)/START*100,'bal':bal,'dd':max_dd}

results = []

# 전략 1: EMA크로스(9/20)
for sl,tp,lev in [(0.015,0.035,5),(0.02,0.05,5),(0.015,0.04,5),(0.02,0.04,3)]:
    ls = (df['ema9']>df['ema20'])&(df['ema9'].shift(1)<=df['ema20'].shift(1))
    ss = (df['ema9']<df['ema20'])&(df['ema9'].shift(1)>=df['ema20'].shift(1))
    r = backtest(ls.values,ss.values,df,sl,tp,lev)
    results.append({'전략':'EMA크로스(9/20)','SL':sl,'TP':tp,'Lev':lev,**r})

# 전략 2: EMA크로스(20/50)
for sl,tp,lev in [(0.015,0.035,5),(0.02,0.05,5),(0.02,0.04,3),(0.025,0.06,3)]:
    ls = (df['ema20']>df['ema50'])&(df['ema20'].shift(1)<=df['ema50'].shift(1))
    ss = (df['ema20']<df['ema50'])&(df['ema20'].shift(1)>=df['ema50'].shift(1))
    r = backtest(ls.values,ss.values,df,sl,tp,lev)
    results.append({'전략':'EMA크로스(20/50)','SL':sl,'TP':tp,'Lev':lev,**r})

# 전략 3: MACD크로스
for sl,tp,lev in [(0.015,0.035,5),(0.02,0.05,5),(0.015,0.04,5),(0.02,0.04,3)]:
    ls = (df['macd_line']>df['macd_signal'])&(df['macd_line'].shift(1)<=df['macd_signal'].shift(1))
    ss = (df['macd_line']<df['macd_signal'])&(df['macd_line'].shift(1)>=df['macd_signal'].shift(1))
    r = backtest(ls.values,ss.values,df,sl,tp,lev)
    results.append({'전략':'MACD크로스','SL':sl,'TP':tp,'Lev':lev,**r})

# 전략 4: ADX+EMA(>25)
for sl,tp,lev in [(0.015,0.035,5),(0.02,0.05,5),(0.015,0.04,5),(0.02,0.04,3)]:
    strong = df['adx']>25
    ls = strong&(df['ema9']>df['ema20'])&(df['ema9']>df['ema9'].shift(1))
    ss = strong&(df['ema9']<df['ema20'])&(df['ema9']<df['ema9'].shift(1))
    ls = ls&~ls.shift(1).fillna(False)
    ss = ss&~ss.shift(1).fillna(False)
    r = backtest(ls.values,ss.values,df,sl,tp,lev)
    results.append({'전략':'ADX+EMA(>25)','SL':sl,'TP':tp,'Lev':lev,**r})

# 전략 5: ADX+EMA(>20)
for sl,tp,lev in [(0.015,0.035,5),(0.02,0.05,5),(0.015,0.04,5),(0.02,0.04,3)]:
    strong = df['adx']>20
    ls = strong&(df['ema9']>df['ema20'])&(df['ema9']>df['ema9'].shift(1))
    ss = strong&(df['ema9']<df['ema20'])&(df['ema9']<df['ema9'].shift(1))
    ls = ls&~ls.shift(1).fillna(False)
    ss = ss&~ss.shift(1).fillna(False)
    r = backtest(ls.values,ss.values,df,sl,tp,lev)
    results.append({'전략':'ADX+EMA(>20)','SL':sl,'TP':tp,'Lev':lev,**r})

# 전략 6: BB+RSI+MACD
for sl,tp,lev in [(0.015,0.035,5),(0.02,0.05,5),(0.015,0.04,5),(0.02,0.04,3)]:
    ls = (df['rsi']<45)&(df['close']<=df['bb_mid'])&(df['adx']>20)&(df['macd_hist']>0)
    ss = (df['rsi']>55)&(df['close']>=df['bb_mid'])&(df['adx']>20)&(df['macd_hist']<0)
    ls = ls&~ls.shift(1).fillna(False)
    ss = ss&~ss.shift(1).fillna(False)
    r = backtest(ls.values,ss.values,df,sl,tp,lev)
    results.append({'전략':'BB+RSI+MACD','SL':sl,'TP':tp,'Lev':lev,**r})

# 전략 7: RSI+MACD
for rsi_lo,rsi_hi,sl,tp,lev in [(35,65,0.015,0.035,5),(40,60,0.02,0.05,5),(35,65,0.02,0.04,3),(30,70,0.015,0.04,5)]:
    ls = (df['rsi']<rsi_lo)&(df['macd_hist']>0)
    ss = (df['rsi']>rsi_hi)&(df['macd_hist']<0)
    r = backtest(ls.values,ss.values,df,sl,tp,lev)
    results.append({'전략':f'RSI+MACD({rsi_lo}/{rsi_hi})','SL':sl,'TP':tp,'Lev':lev,**r})

# 전략 8: 현재 봇 전략 (기준)
eg = (df['ema9']>df['ema20'])&(df['ema9'].shift(1)<=df['ema20'].shift(1))
ed = (df['ema9']<df['ema20'])&(df['ema9'].shift(1)>=df['ema20'].shift(1))
ls = ((df['adx']>15)&eg)|((df['ema9']>df['ema20'])&(df['stoch_k']<20)&(df['close']<df['bb_low']*1.01))|((df['adx']<20)&(df['rsi']<30))
ss = ((df['adx']>15)&ed)|((df['ema9']<df['ema20'])&(df['stoch_k']>80)&(df['close']>df['bb_high']*0.99))|((df['adx']<20)&(df['rsi']>70))
r = backtest(ls.values,ss.values,df,0.015,0.035,5)
results.append({'전략':'[현재봇전략]','SL':0.015,'TP':0.035,'Lev':5,**r})

rdf = pd.DataFrame(results).sort_values('ret', ascending=False)

print('=' * 72)
print(f"{'순위':<4} {'전략':<20} {'SL':>5} {'TP':>5} {'레':>4} {'거래':>5} {'승률':>7} {'수익률':>8} {'최대낙폭':>9}")
print('-' * 72)
for i, (_, row) in enumerate(rdf.head(10).iterrows(), 1):
    mark = '★' if row['전략'] == '[현재봇전략]' else ' '
    rank = f'{i}위'
    print(f"{rank:<4} {mark}{row['전략']:<19} {row['SL']*100:>4.1f}% {row['TP']*100:>4.1f}% {row['Lev']:>3}x {row['n']:>5.0f}회 {row['wr']:>6.1f}% {row['ret']:>+7.2f}% {-row['dd']:>8.2f}%")

best = rdf.iloc[0]
cur  = rdf[rdf['전략']=='[현재봇전략]'].iloc[0]

print()
print('=' * 65)
print(f'1위 전략: [{best["전략"]}]')
print(f'  SL: -{best["SL"]*100:.1f}%  TP: +{best["TP"]*100:.1f}%  레버리지: {best["Lev"]}x')
print(f'  수익률: {best["ret"]:+.2f}%  승률: {best["wr"]:.1f}%  거래: {best["n"]:.0f}회  최대낙폭: {-best["dd"]:.2f}%')
print()
print(f'현재 봇 전략: 수익률 {cur["ret"]:+.2f}%  승률: {cur["wr"]:.1f}%  거래: {cur["n"]:.0f}회')
print(f'수익률 개선 가능폭: {best["ret"]-cur["ret"]:+.2f}%p')
print('=' * 65)
