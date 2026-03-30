# 🤖 Binance XRP Futures Auto Trading Bot

바이낸스 선물(Futures) 계좌에서 XRP/USDT를 자동으로 매매하는 Python 봇입니다.
ADX+EMA(>25) 추세 전략으로 강한 추세에서만 롱/숏 포지션을 자동 진입·청산하며, 텔레그램 메시지로 실시간 알림과 원격 제어를 지원합니다.

---

## ⚠️ 주의사항 (반드시 읽어주세요)

> **이 봇은 실제 자금이 걸린 자동매매 프로그램입니다.**
> 암호화폐 선물 거래는 원금 손실 위험이 있으며, 레버리지 사용 시 손실이 배가됩니다.
> 테스트 없이 큰 금액으로 운용하지 마시고, 반드시 소액으로 먼저 검증하세요.
> 이 코드 사용으로 발생하는 손실에 대해 개발자는 책임을 지지 않습니다.

---

## ✨ 주요 기능

- **자동 매매**: 5분마다 XRP/USDT 시세를 분석하여 롱/숏 포지션 자동 진입
- **자동 손절/익절**: 30초마다 가격을 체크하여 조건 도달 시 자동 청산
- **ADX+EMA(>25) 추세 전략**: 강한 추세에서만 진입하여 오신호 최소화 (1년 백테스트 +520%)
- **텔레그램 원격 제어 + 자연어 명령**: 명령어 외에도 "손절 2%로 바꿔줘" 등 자연어로 파라미터 변경 가능
- **Dry-run 모드**: API 키 없이도 전략 신호 테스트 가능
- **포지션 동기화**: 봇 재시작 시 기존 포지션 자동 감지 및 복구
- **매매 로그**: 모든 진입/청산 기록을 파일로 저장
- **백테스트**: 8가지 전략 × 다양한 파라미터 조합을 1년치 데이터로 자동 탐색
- **웹 대시보드**: Streamlit 기반 캔들차트 + 지표 시각화

---

## 📁 파일 구조

```
binance_real/
├── trading_bot.py       # 메인 봇 — 매매 실행, 텔레그램 폴링, SL/TP 관리
├── strategy_analyzer.py # 전략 엔진 — ADX+EMA(>25) 신호 계산 및 LONG/SHORT/HOLD 반환
├── backtest.py          # 백테스트 v1 (단순)
├── backtest_v2.py       # 백테스트 v2 — 28가지 전략 조합 자동 탐색
├── backtest_1year.py    # 백테스트 v3 — 8가지 전략 × 파라미터 1년치 탐색
├── backtest_custom.py   # 현재 전략 기준 1년 백테스트 (설정별 비교)
├── web_dashboard.py     # Streamlit 웹 대시보드 (캔들차트 시각화)
├── app.py               # 별도 앱 — Google News RSS 기반 뉴스 요약 (봇과 무관)
├── debug_symbol.py      # 심볼 디버그 스크립트
├── test_env.py          # 환경변수 연동 테스트
├── test_telegram.py     # 텔레그램 연동 테스트
├── requirements.txt     # 의존성 목록
├── .env                 # API 키 (절대 GitHub에 올리지 마세요!)
├── .gitignore           # .env, 로그 파일 등 제외 목록
└── trade_history.log    # 매매 기록 로그 (자동 생성)
```

---

## 🧠 매매 전략 상세

`strategy_analyzer.py`에 구현된 **ADX+EMA(>25) 추세 전략**입니다.
1년치 백테스트에서 가장 높은 수익률(+520%)을 기록한 전략입니다.

### 진입 조건
| 조건 | 신호 |
|------|------|
| ADX > 25 + EMA9 > EMA20 + EMA9 상승 중 + **첫 신호** | **LONG** |
| ADX > 25 + EMA9 < EMA20 + EMA9 하락 중 + **첫 신호** | **SHORT** |

> **"첫 신호만"** 진입하는 이유: 이전 봉에서 이미 조건이 충족된 경우는 진입하지 않습니다.
> 추세 초기 진입으로 수익 극대화 + 오신호 최소화를 동시에 달성합니다.

### 전략 핵심 로직
```python
if adx > 25:
    long_cond  = (ema9 > ema20) and (ema9 > ema9_prev)   # EMA9 상승 중
    short_cond = (ema9 < ema20) and (ema9 < ema9_prev)   # EMA9 하락 중

    # 이전 봉에서 이미 조건 충족 → 진입 안 함 (첫 신호만)
    if long_cond and not prev_long:  → LONG
    if short_cond and not prev_short: → SHORT
```

### 청산 조건
- **손절 (Stop Loss)**: 진입가 대비 **-1.5%** 도달 시 자동 청산
- **익절 (Take Profit)**: 진입가 대비 **+4.5%** 도달 시 자동 청산
- SL/TP 도달 전까지는 포지션 유지 (반대 신호 무시)

### 사용 지표 요약
| 지표 | 파라미터 | 역할 |
|------|----------|------|
| ADX | 14 | 추세 강도 측정 (>25이면 강한 추세) |
| EMA | 9, 20 | 추세 방향 및 강도 판단 |
| RSI | 14 | 참고용 (진입 조건에 미사용) |
| Stoch RSI | 14 | 참고용 (진입 조건에 미사용) |
| Bollinger Bands | 20, 2σ | 참고용 (진입 조건에 미사용) |

---

## 🛠️ 설치 방법

### 1단계. Python 설치

Python **3.10 이상**이 필요합니다.

- [Python 공식 다운로드](https://www.python.org/downloads/)
- 설치 시 **"Add Python to PATH"** 옵션을 반드시 체크하세요.

설치 확인:
```bash
python --version
```

---

### 2단계. 코드 다운로드

```bash
git clone https://github.com/kasangyong/binance.git
cd binance
```

또는 GitHub에서 ZIP으로 다운로드 후 압축 해제

---

### 3단계. 라이브러리 설치

```bash
pip install -r requirements.txt
```

설치에 오류가 생기면 아래처럼 하나씩 설치해보세요:
```bash
pip install ccxt pandas ta python-dotenv requests schedule streamlit plotly
```

---

### 4단계. .env 파일 설정 (가장 중요!)

프로젝트 루트에 `.env` 파일을 직접 만들어야 합니다.
**이 파일에는 API 키가 들어가므로 절대 GitHub에 올리면 안 됩니다.**

```
BINANCE_API_KEY=여기에_바이낸스_API_키
BINANCE_SECRET_KEY=여기에_바이낸스_시크릿_키
TELEGRAM_BOT_TOKEN=여기에_텔레그램_봇_토큰
TELEGRAM_CHAT_ID=여기에_텔레그램_채팅_ID
```

아래에서 각 키를 발급받는 방법을 설명합니다.

---

## 🔑 API 키 발급 가이드

### 바이낸스 API 키 발급

> 선물 계좌에서 실제 거래를 실행하려면 바이낸스 API 키가 필요합니다.

1. [바이낸스 로그인](https://www.binance.com) → 오른쪽 상단 프로필 아이콘 클릭
2. **API Management** 메뉴 선택
3. **Create API** 클릭 → API 이름 입력 (예: `my_trading_bot`)
4. 이메일/OTP 인증 완료
5. 생성된 API 키 화면에서:
   - **API Key** → `BINANCE_API_KEY`에 복사
   - **Secret Key** → `BINANCE_SECRET_KEY`에 복사 (한 번만 표시되므로 반드시 저장!)
6. **Edit Restrictions** 에서 권한 설정:
   - ✅ **Enable Reading** 체크
   - ✅ **Enable Futures** 체크
   - ❌ **Enable Withdrawals** 체크 해제 (보안을 위해 반드시 해제)
7. IP 제한 설정 권장 (본인 서버/PC IP 입력)

> API 키가 없으면 봇은 자동으로 **Dry-run 모드** (실제 주문 없이 로그만 출력)로 동작합니다.

---

### 텔레그램 봇 토큰 발급

1. 텔레그램 앱에서 **@BotFather** 검색 후 대화 시작
2. `/newbot` 입력
3. 봇 이름 입력 (예: `My Trading Bot`)
4. 봇 아이디(username) 입력 — 반드시 `bot`으로 끝나야 함 (예: `my_xrp_bot`)
5. 완료 후 받은 토큰 (`123456789:AAF...`) → `TELEGRAM_BOT_TOKEN`에 복사

---

### 텔레그램 Chat ID 확인

1. 위에서 만든 봇에게 텔레그램에서 아무 메시지나 전송
2. 브라우저에서 아래 URL 접속 (YOUR_BOT_TOKEN 부분을 실제 토큰으로 교체):
   ```
   https://api.telegram.org/botYOUR_BOT_TOKEN/getUpdates
   ```
3. 응답 JSON에서 `"chat":{"id":` 뒤의 숫자가 Chat ID
   ```json
   "chat": {
     "id": 123456789,   ← 이 숫자가 TELEGRAM_CHAT_ID
     ...
   }
   ```
4. 해당 숫자 → `TELEGRAM_CHAT_ID`에 복사

---

### .env 파일 완성 예시

```env
BINANCE_API_KEY=abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890
BINANCE_SECRET_KEY=abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890
TELEGRAM_BOT_TOKEN=123456789:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TELEGRAM_CHAT_ID=987654321
```

---

## ⚙️ 봇 파라미터 설정

`trading_bot.py` 상단에서 리스크 파라미터를 수정할 수 있습니다:

```python
STOP_LOSS_PCT    = 0.015   # 손절: -1.5%  (예: 0.02 → -2%)
TAKE_PROFIT_PCT  = 0.045   # 익절: +4.5%  (예: 0.05 → +5%)
INITIAL_CAPITAL  = 152.0   # 초기 투자 자본 (USDT, /balance 명령어 기준점)
TRADE_RATIO      = 0.50    # 투자 비율: 잔고의 50% (예: 0.20 → 20%)
```

> `TRADE_RATIO`는 매 거래 시 현재 잔고 기준 몇 %를 투자할지를 결정합니다.
> 잔고가 늘면 투자 금액도 함께 늘어나는 복리 방식입니다.

`strategy_analyzer.py`에서 레버리지를 수정할 수 있습니다:

```python
leverage = 5  # 레버리지 배수 (기본 5배)
```

> ⚠️ 손절/익절 비율과 레버리지는 신중하게 설정하세요. 레버리지가 높을수록 리스크도 커집니다.

### 텔레그램으로 파라미터 변경 (자연어 명령)

봇 실행 중에 텔레그램에서 아래와 같이 **자연어로** 파라미터를 변경할 수 있습니다:

| 예시 메시지 | 적용 효과 |
|------------|----------|
| `손절 2%로 바꿔줘` | STOP_LOSS_PCT = 0.02 |
| `익절 5%로 설정해줘` | TAKE_PROFIT_PCT = 0.05 |
| `잔고의 30%로 해줘` | TRADE_RATIO = 0.30 |
| `레버리지 10배로 올려줘` | leverage = 10 (봇 자동 재시작) |

> 레버리지 변경 시에는 봇이 자동으로 재시작됩니다.

---

## 🚀 실행 방법

### 봇 실행

```bash
python trading_bot.py
```

정상 실행 시 아래와 같은 메시지가 출력됩니다:
```
✅ Binance Futures API Keys loaded.
🔄 [동기화 성공] LONG 35.0개 (진입가: 1.394800, 레버리지: 5x)
🚀 Starting Trading Bot round for XRP/USDT...
⏳ Scheduled to run every 15 minutes. Press Ctrl+C to stop.
⏳ SL/TP check every 30 seconds.
```

API 키가 없을 경우 (Dry-run 모드):
```
⚠️ Binance API Keys NOT FOUND. Running in dry-run (simulation) mode.
```

### 백테스트 실행

```bash
# 1년치 전략 탐색 (8가지 전략 × 파라미터 조합, 15분봉)
python backtest_1year.py

# 현재 전략 기준 설정별 비교 (잔고 100%+10배 vs 현재 설정)
python backtest_custom.py

# 기존 28가지 전략 조합 탐색
python backtest_v2.py
```

### 웹 대시보드 실행

```bash
streamlit run web_dashboard.py
```

브라우저에서 캔들차트와 기술 지표를 시각화합니다.

---

## 📱 텔레그램 명령어 목록

봇이 실행 중인 상태에서 텔레그램에서 아래 명령어를 전송하면 즉시 응답합니다.

| 명령어 | 설명 |
|--------|------|
| `/status` | 봇 상태 + 현재 포지션 (타입, 진입가, 레버리지) 확인 |
| `/price` | 현재가 + 포지션 실시간 손익 확인 |
| `/balance` | 선물 지갑 USDT 잔고 + 초기자본 대비 손익 |
| `/coins` | 현물·선물 전체 지갑 보유 코인 목록 |
| `/market` | 현재 기술 지표값 (ADX, RSI, Stoch RSI, 판단 신호) |
| `/strategy` | 적용 중인 전략 상세 설명 |
| `/stats` | 전체 매매 기록 기반 승률 통계 |
| `/uptime` | 봇 가동 시간 (일·시간·분) |
| `/run` | 즉시 1회 강제 분석 및 매매 실행 |
| `/close` | 현재 포지션 강제 청산 (비상용) |
| `/log` | 최근 매매 로그 5줄 출력 |
| `/help` | 명령어 목록 도움말 |

---

## 🔄 실행 주기

| 작업 | 주기 |
|------|------|
| 전략 분석 + 주문 | 5분마다 |
| 손절/익절 체크 | 30초마다 (포지션 보유 시에만) |
| 텔레그램 명령어 폴링 | 1초마다 |

---

## 📊 실행 흐름 요약

```
봇 시작
  └─ 기존 포지션 동기화 (sync_position)
  └─ 1회 즉시 실행 (job)
  └─ 루프 시작
       ├─ 매 1초: 텔레그램 명령어 확인
       ├─ 매 30초: 손절/익절 가격 체크 (포지션 있을 때만)
       └─ 매 5분: 전략 분석 → LONG/SHORT/HOLD 결정 → 주문 실행
```

---

## 🛡️ 보안 주의사항

1. **`.env` 파일을 절대 GitHub에 올리지 마세요.**
   `.gitignore`에 `.env`가 포함되어 있는지 반드시 확인하세요.

2. **바이낸스 API 키에 출금 권한을 부여하지 마세요.**
   `Enable Futures`만 체크하고 `Enable Withdrawals`는 반드시 해제하세요.

3. **API 키가 유출되었다면 즉시 바이낸스에서 해당 키를 삭제하세요.**

4. **IP 제한 설정을 활용하세요.**
   바이낸스 API Management에서 본인 서버 IP만 허용하면 보안이 강화됩니다.

---

## 🐛 자주 발생하는 오류

### `Margin is insufficient`
- 원인: 선물 지갑에 USDT가 부족합니다.
- 해결: 바이낸스 앱 → 지갑 → 현물에서 선물 지갑으로 USDT 이체

### `주문 금액이 너무 적습니다`
- 원인: 선물 지갑 잔고가 2 USDT 미만입니다.
- 해결: 선물 지갑에 USDT를 충전하세요.

### `Telegram polling error`
- 원인: 텔레그램 토큰 또는 Chat ID가 잘못되었습니다.
- 해결: `.env` 파일의 `TELEGRAM_BOT_TOKEN`과 `TELEGRAM_CHAT_ID` 값을 재확인하세요.

### 여러 인스턴스 중복 실행 문제
- 원인: 봇을 여러 번 실행하면 여러 프로세스가 동시에 돌아가며 중복 주문이 발생할 수 있습니다.
- 해결 (Windows):
  ```bash
  # 실행 중인 Python 프로세스 확인
  tasklist | findstr python
  # 특정 PID 종료
  taskkill /F /PID 12345
  ```

---

## 📦 의존성 목록

| 라이브러리 | 용도 |
|-----------|------|
| `ccxt` | 바이낸스 거래소 API 연동 |
| `ta` | 기술적 지표 계산 (RSI, ADX, EMA 등) |
| `pandas` | 데이터프레임 처리 |
| `python-dotenv` | `.env` 환경변수 로드 |
| `requests` | 텔레그램 API 호출 |
| `schedule` | 주기적 작업 스케줄링 |
| `streamlit` | 웹 대시보드 |
| `plotly` | 캔들차트 시각화 |

---

## 📝 라이선스

MIT License — 자유롭게 사용, 수정, 배포 가능합니다.
단, 이 코드 사용으로 인한 금전적 손실에 대한 책임은 사용자 본인에게 있습니다.
