# 🤖 Binance XRP Futures Auto Trading Bot

바이낸스 선물(Futures) 계좌에서 XRP/USDT를 자동으로 매매하는 Python 봇입니다.
기술적 지표(ADX, EMA, RSI, Stoch RSI, Bollinger Bands)를 조합한 하이브리드 전략으로 롱/숏 포지션을 자동 진입·청산하며, 텔레그램 메시지로 실시간 알림과 원격 제어를 지원합니다.

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
- **3가지 복합 전략**: 추세돌파 + 눌림목 + 극단 과매수/과매도 감지
- **텔레그램 원격 제어**: 12개 명령어로 스마트폰에서 봇 상태 확인 및 제어
- **Dry-run 모드**: API 키 없이도 전략 신호 테스트 가능
- **포지션 동기화**: 봇 재시작 시 기존 포지션 자동 감지 및 복구
- **매매 로그**: 모든 진입/청산 기록을 파일로 저장
- **백테스트**: 28가지 전략 조합을 자동 탐색하여 최적 파라미터 도출
- **웹 대시보드**: Streamlit 기반 캔들차트 + 지표 시각화

---

## 📁 파일 구조

```
binance_real/
├── trading_bot.py       # 메인 봇 — 매매 실행, 텔레그램 폴링, SL/TP 관리
├── strategy_analyzer.py # 전략 엔진 — 지표 계산 및 LONG/SHORT/HOLD 신호 반환
├── backtest.py          # 백테스트 v1 (단순)
├── backtest_v2.py       # 백테스트 v2 — 28가지 전략 조합 자동 탐색
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

`strategy_analyzer.py`에 구현된 **고빈도 하이브리드 전략**입니다.
아래 3가지 케이스를 순서대로 판단하며, 먼저 조건이 충족되는 케이스가 우선됩니다.

### CASE 1. 추세 돌파 (Trend Following)
| 조건 | 신호 |
|------|------|
| ADX > 15 + EMA9가 EMA20을 아래서 위로 돌파 (골든크로스) | **LONG** |
| ADX > 15 + EMA9가 EMA20을 위에서 아래로 돌파 (데스크로스) | **SHORT** |

### CASE 2. 눌림목 매수 / 반등 매도 (Mean Reversion)
| 조건 | 신호 |
|------|------|
| EMA9 > EMA20 (상승추세) + Stoch RSI < 20 + 가격이 BB 하단 근접 | **LONG** |
| EMA9 < EMA20 (하락추세) + Stoch RSI > 80 + 가격이 BB 상단 근접 | **SHORT** |

### CASE 3. 극단 과매수/과매도 (Contrarian, 횡보장 전용)
| 조건 | 신호 |
|------|------|
| ADX < 20 (추세 없음) + RSI < 30 | **LONG** |
| ADX < 20 (추세 없음) + RSI > 70 | **SHORT** |

### 청산 조건
- **손절 (Stop Loss)**: 진입가 대비 **-1.5%** 도달 시 자동 청산
- **익절 (Take Profit)**: 진입가 대비 **+3.5%** 도달 시 자동 청산
- 반대 신호가 들어와도 SL/TP 도달 전까지는 포지션 유지

### 사용 지표 요약
| 지표 | 파라미터 | 역할 |
|------|----------|------|
| ADX | 14 | 추세 강도 측정 |
| EMA | 9, 20 | 추세 방향 판단 |
| RSI | 14 | 과매수/과매도 |
| Stoch RSI | 14 | 민감한 과매수/과매도 |
| Bollinger Bands | 20, 2σ | 가격 채널 상단/하단 |

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
TAKE_PROFIT_PCT  = 0.035   # 익절: +3.5%  (예: 0.05 → +5%)
INITIAL_CAPITAL  = 20.0    # 초기 투자 자본 (USDT, /balance 명령어 기준점)
```

`trading_bot.py` 하단에서 1회 투자 금액을 수정할 수 있습니다:

```python
bot_instance = TradingBot(symbol='XRP/USDT', trade_amount_usdt=20)
#                                                              ↑ 1회 진입 금액 (USDT)
```

`strategy_analyzer.py`에서 레버리지를 수정할 수 있습니다:

```python
leverage = 5  # 레버리지 배수 (기본 5배)
```

> ⚠️ 손절/익절 비율과 레버리지는 신중하게 설정하세요. 레버리지가 높을수록 리스크도 커집니다.

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

### 백테스트 실행 (전략 탐색)

```bash
python backtest_v2.py
```

7가지 전략 × 4가지 파라미터 조합 총 28가지를 자동 탐색하여 수익률 순위를 출력합니다.
최근 60일 XRP/USDT 15분봉 데이터를 사용합니다.

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
