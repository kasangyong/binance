import sys
import os
import json
import time
import schedule
import ccxt
import logging
import requests
from dotenv import load_dotenv
from strategy_analyzer import StrategyAnalyzer

# Windows 환경에서 이모지 출력 인코딩 오류 방지
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# 로깅 설정
logging.basicConfig(
    filename='trade_history.log',
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    encoding='utf-8'
)

# 환경 변수 로드
load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ═══════════════════════════════════════════════════════
# 리스크 관리 설정 (백테스트 최적값)
# ═══════════════════════════════════════════════════════
STOP_LOSS_PCT    = 0.015  # 손절: -1.5%
TAKE_PROFIT_PCT  = 0.035  # 익절: +3.5%
INITIAL_CAPITAL  = 20.0   # 초기 투자 자본 (USDT)

def send_telegram_message(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"❌ Telegram Notification Failed: {e}")

class TradingBot:
    def __init__(self, symbol='XRP/USDT', trade_amount_usdt=20):
        self.symbol = symbol
        self.trade_amount_usdt = trade_amount_usdt
        self.analyzer = StrategyAnalyzer(symbol=self.symbol)
        
        # 포지션 상태 추적
        self.position = None       # None, 'LONG', 'SHORT'
        self.entry_price = 0
        self.entry_leverage = 1
        self.order_qty = 0
        self.start_time = time.time()  # 봇 시작 시간 기록
        
        # 바이낸스 선물 객체 초기화
        if API_KEY and SECRET_KEY:
            self.exchange = ccxt.binance({
                'apiKey': API_KEY,
                'secret': SECRET_KEY,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future'
                }
            })
            print("✅ Binance Futures API Keys loaded.")
            self.sync_position() # 시작 시 실제 포지션 확인
        else:
            self.exchange = None
            print("⚠️ Binance API Keys NOT FOUND. Running in dry-run (simulation) mode.")

    def sync_position(self):
        """바이낸스 거래소와 현재 포지션 상태를 동기화합니다."""
        try:
            all_positions = self.exchange.fetch_positions()
            symbol_matched = False
            for pos in all_positions:
                target_raw = self.symbol.replace('/', '')
                if pos['symbol'].split(':')[0] == self.symbol or pos['info'].get('symbol') == target_raw:
                    # positionAmt로 방향 + 수량 판단 (음수=SHORT, 양수=LONG)
                    position_amt = float(pos['info'].get('positionAmt', 0))
                    if position_amt != 0:
                        self.position = 'LONG' if position_amt > 0 else 'SHORT'
                        self.entry_price = float(pos['entryPrice'] or 0)
                        self.order_qty = abs(position_amt)
                        self.entry_leverage = int(pos['leverage'] or 5)
                        msg = f"🔄 [동기화 성공] {self.position} {self.order_qty}개 (진입가: {self.entry_price:.6f}, 레버리지: {self.entry_leverage}x)"
                        print(msg)
                        logging.info(msg)
                        symbol_matched = True
                        break
            
            if not symbol_matched:
                self.position = None
                print("🔄 [동기화] 현재 열린 포지션이 없습니다.")
                logging.info("sync_position: No open positions found.")
                
        except Exception as e:
            err_msg = f"⚠️ 포지션 동기화 중 오류 발생: {e}"
            print(err_msg)
            logging.error(err_msg)

    def set_leverage(self, leverage):
        try:
            self.exchange.set_leverage(leverage, self.symbol)
            msg = f"✅ Leverage set to {leverage}x for {self.symbol}"
            print(msg)
            logging.info(msg)
        except Exception as e:
            err = f"❌ Failed to set leverage: {e}"
            print(err)
            logging.error(err)

    def close_position(self, reason, current_price):
        """현재 포지션을 청산합니다. (reduceOnly로 증거금 불필요)"""
        if self.position is None or self.exchange is None:
            return
        
        try:
            params = {'reduceOnly': True}  # 기존 포지션 청산만 (증거금 불필요)
            if self.position == 'LONG':
                order = self.exchange.create_market_sell_order(self.symbol, self.order_qty, params=params)
                pnl_pct = (current_price - self.entry_price) / self.entry_price * 100
            else:
                order = self.exchange.create_market_buy_order(self.symbol, self.order_qty, params=params)
                pnl_pct = (self.entry_price - current_price) / self.entry_price * 100
            
            emoji = "✅" if pnl_pct > 0 else "❌"
            msg = f"{emoji} [{self.position} 포지션 청산 - {reason}]\n진입가: {self.entry_price:.6f}\n청산가: {current_price:.6f}\n레버리지: {self.entry_leverage}x\n실제 손익: {pnl_pct * self.entry_leverage:+.2f}%"
            print(msg)
            logging.info(msg)
            send_telegram_message(msg)
            
            self.position = None
            self.entry_price = 0
            self.order_qty = 0
            
        except Exception as e:
            err = f"❌ 청산 실패: {e}"
            print(err)
            logging.error(err)
            send_telegram_message(f"🚨 [청산 에러]\n{e}")


    def check_stop_loss_take_profit(self):
        """손절/익절 조건을 확인하고 해당 시 청산합니다."""
        if self.position is None or self.exchange is None:
            return
        
        try:
            ticker = self.exchange.fetch_ticker(self.symbol)
            current_price = ticker['last']
            
            if self.position == 'LONG':
                pnl_pct = (current_price - self.entry_price) / self.entry_price
                sl_hit = current_price <= self.entry_price * (1 - STOP_LOSS_PCT)
                tp_hit = current_price >= self.entry_price * (1 + TAKE_PROFIT_PCT)
            else:  # SHORT
                pnl_pct = (self.entry_price - current_price) / self.entry_price
                sl_hit = current_price >= self.entry_price * (1 + STOP_LOSS_PCT)
                tp_hit = current_price <= self.entry_price * (1 - TAKE_PROFIT_PCT)
            
            if tp_hit:
                self.close_position(f"🎯 익절(+{TAKE_PROFIT_PCT*100:.0f}%)", current_price)
            elif sl_hit:
                self.close_position(f"🛑 손절(-{STOP_LOSS_PCT*100:.0f}%)", current_price)
                
        except Exception as e:
            print(f"SL/TP check error: {e}")

    def execute_trade(self, decision, leverage, reason):
        msg = f"Signal: {decision} | Leverage: {leverage}x | Reason: {reason}"
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}")
        logging.info(msg)

        # HOLD 신호: 기존 포지션 유지, 아무것도 하지 않음
        if decision == "HOLD":
            return

        if self.exchange is None:
            no_api_msg = "[DRY-RUN] No trade executed due to missing API keys."
            print(no_api_msg)
            logging.info(no_api_msg)
            return
        
        # 포지션이 있으면 SL/TP가 처리할 때까지 유지 (반대 신호로 청산 금지)
        if self.position is not None:
            print(f"포지션 유지 중 ({self.position}). SL/TP 대기.")
            return
        
        try:
            # 1. 가용 잔고 다시 한 번 확인
            balance = self.exchange.fetch_balance()
            usdt_balance = float(balance['free'].get('USDT', 0))
            
            # 2. 현재가 확인
            ticker = self.exchange.fetch_ticker(self.symbol)
            current_price = float(ticker['last'])
            
            # 3. 주문 수량 계산 (안전을 위해 가용 잔고의 90%만 사용하거나 trade_amount 적용)
            actual_trade_amount = min(self.trade_amount_usdt, usdt_balance * 0.95)
            total_position_value = actual_trade_amount * leverage
            order_qty = self.exchange.amount_to_precision(self.symbol, total_position_value / current_price)
            
            if actual_trade_amount < 2: # 최소 주문 금액 하향 (XRP 5배 레버리지 고려)
                raise Exception(f"주문 금액이 너무 적습니다. (가용: {usdt_balance:.2f} USDT)")
            
            if decision == "LONG":
                self.set_leverage(leverage)
                if actual_trade_amount >= 2:
                    print(f"Executing LONG order for {order_qty} {self.symbol}...")
                    order = self.exchange.create_market_buy_order(self.symbol, order_qty)
                    
                    # 포지션 상태 저장
                    self.position = 'LONG'
                    self.entry_price = current_price
                    self.entry_leverage = leverage
                    self.order_qty = order_qty
                    
                    success_msg = f"💰 [LONG 포지션 진입]\n{self.symbol} @ {current_price:.6f}\n레버리지: {leverage}x | 수량: {order_qty}\n손절: {current_price*(1-STOP_LOSS_PCT):.6f} (-{STOP_LOSS_PCT*100:.0f}%)\n익절: {current_price*(1+TAKE_PROFIT_PCT):.6f} (+{TAKE_PROFIT_PCT*100:.0f}%)\n사유: {reason}"
                    print(success_msg)
                    logging.info(success_msg)
                    send_telegram_message(success_msg)
                else:
                    err_msg = f"❌ 가용 잔고 부족 (최소 2 USDT 필요). 현재: {usdt_balance:.2f}"
                    print(err_msg)
                    logging.info(err_msg)
                    send_telegram_message(f"⚠️ [LONG 진입 실패]\n{err_msg}\n💡 현물 지갑의 USDT를 선물 지갑으로 이체했는지 확인해 주세요.")

            elif decision == "SHORT":
                self.set_leverage(leverage)
                if actual_trade_amount >= 2:
                    print(f"Executing SHORT order for {order_qty} {self.symbol}...")
                    order = self.exchange.create_market_sell_order(self.symbol, order_qty)
                    
                    # 포지션 상태 저장
                    self.position = 'SHORT'
                    self.entry_price = current_price
                    self.entry_leverage = leverage
                    self.order_qty = order_qty
                    
                    success_msg = f"📉 [SHORT 포지션 진입]\n{self.symbol} @ {current_price:.6f}\n레버리지: {leverage}x | 수량: {order_qty}\n손절: {current_price*(1+STOP_LOSS_PCT):.6f} (-{STOP_LOSS_PCT*100:.0f}%)\n익절: {current_price*(1-TAKE_PROFIT_PCT):.6f} (+{TAKE_PROFIT_PCT*100:.0f}%)\n사유: {reason}"
                    print(success_msg)
                    logging.info(success_msg)
                    send_telegram_message(success_msg)
                else:
                    err_msg = f"❌ 가용 잔고 부족 (최소 2 USDT 필요). 현재: {usdt_balance:.2f}"
                    print(err_msg)
                    logging.info(err_msg)
                    send_telegram_message(f"⚠️ [SHORT 진입 실패]\n{err_msg}\n💡 현물 지갑의 USDT를 선물 지갑으로 이체했는지 확인해 주세요.")
                    
        except Exception as e:
            err_msg = str(e)
            if "Margin is insufficient" in err_msg:
                err_exec = "❌ 매매 실패: 선물 지갑에 증거금이 부족합니다. (현물->선물 이체 필요)"
            else:
                err_exec = f"❌ Trade Execution Failed: {e}"
            print(err_exec)
            logging.error(err_exec)
            send_telegram_message(f"🚨 [매매 에러 발생]\n{err_exec}")

    def run(self):
        start_msg = f"🚀 Starting Trading Bot round for {self.symbol}..."
        print(start_msg)
        logging.info(start_msg)
        
        # 먼저 손절/익절 조건 확인
        self.check_stop_loss_take_profit()
        
        try:
            signal_str = self.analyzer.get_signal()
            signal_data = json.loads(signal_str)
            decision = signal_data.get('decision', 'HOLD').upper()
            leverage = int(signal_data.get('leverage', 1))
            reason = signal_data.get('reason', 'No reason provided')
            
            self.execute_trade(decision, leverage, reason)
        except json.JSONDecodeError:
            json_err = f"❌ JSON Decode Error. Raw response:\n{signal_str}"
            print(json_err)
            logging.error(json_err)
        except Exception as e:
            gen_err = f"❌ Error during Bot Run: {e}"
            print(gen_err)
            logging.error(gen_err)

bot_instance = TradingBot(symbol='XRP/USDT', trade_amount_usdt=20)
last_update_id = None

# 봇 시작 시 이전 메시지 클리어
if TELEGRAM_BOT_TOKEN:
    try:
        res = requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates").json()
        if res.get("ok") and len(res["result"]) > 0:
            last_update_id = res["result"][-1]["update_id"] + 1
    except:
        pass

# 손절/익절 체크 카운터 (매 30초마다)
sl_tp_check_counter = 0

def process_telegram_commands():
    global last_update_id
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    params = {"timeout": 1}
    if last_update_id:
        params["offset"] = last_update_id

    try:
        response = requests.get(url, params=params, timeout=3)
        data = response.json()
        if data.get("ok"):
            for result in data["result"]:
                update_id = result["update_id"]
                last_update_id = update_id + 1
                
                message = result.get("message", {})
                text = message.get("text", "")
                chat_id = str(message.get("chat", {}).get("id"))
                
                if chat_id != str(TELEGRAM_CHAT_ID):
                    continue
                    
                if text in ["/status", "status"]:
                    pos_info = f"\n현재 포지션: {bot_instance.position or '없음'}"
                    if bot_instance.position:
                        pos_info += f"\n진입가: {bot_instance.entry_price:.6f}"
                        pos_info += f"\n레버리지: {bot_instance.entry_leverage}x"
                    send_telegram_message(f"✅ 봇 정상 작동 중\n전략: 고빈도 하이브리드\n타겟: {bot_instance.symbol}\n주기: 5분\n손절: -{STOP_LOSS_PCT*100:.1f}% | 익절: +{TAKE_PROFIT_PCT*100:.1f}%{pos_info}")
                elif text in ["/balance", "balance"]:
                    if bot_instance.exchange:
                        balance = bot_instance.exchange.fetch_balance()
                        usdt_balance = float(balance['total'].get('USDT', 0))
                        pnl = usdt_balance - INITIAL_CAPITAL
                        pnl_pct = (pnl / INITIAL_CAPITAL) * 100
                        emoji = "📈" if pnl >= 0 else "📉"
                        send_telegram_message(f"💰 [현재 선물 잔고]\nUSDT: {usdt_balance:.2f} 💵\n{emoji} 초기 자본 대비: {pnl:+.2f} USDT ({pnl_pct:+.1f}%)")
                    else:
                        send_telegram_message("⚠️ API 키가 없어 잔고를 조회할 수 없습니다.")
                elif text in ["/run", "run"]:
                    send_telegram_message("🚀 강제로 1회 분석 및 매매를 시작합니다.")
                    bot_instance.run()
                elif text in ["/price", "price"]:
                    if bot_instance.exchange:
                        # 매번 API 호출할 때마다 포지션 최신 상태 동기화 시도 (손익 정확도 향상)
                        bot_instance.sync_position()
                        
                        ticker = bot_instance.exchange.fetch_ticker(bot_instance.symbol)
                        current_price = ticker['last']
                        pos_msg = ""
                        if bot_instance.position:
                            if bot_instance.position == 'LONG':
                                pnl_pct = (current_price - bot_instance.entry_price) / bot_instance.entry_price * 100
                                pnl_usdt = (current_price - bot_instance.entry_price) * bot_instance.order_qty
                            else:
                                pnl_pct = (bot_instance.entry_price - current_price) / bot_instance.entry_price * 100
                                pnl_usdt = (bot_instance.entry_price - current_price) * bot_instance.order_qty
                            
                            total_pnl_pct = pnl_pct * bot_instance.entry_leverage
                            emoji = "➕" if total_pnl_pct >= 0 else "➖"
                            pos_msg = (
                                f"\n\n📊 [보유 포지션 내역]\n"
                                f"• 타입: {bot_instance.position}\n"
                                f"• 진입가: {bot_instance.entry_price:.6f}\n"
                                f"• 현재가: {current_price:.6f}\n"
                                f"• {emoji} 수익률: {total_pnl_pct:+.2f}%\n"
                                f"• 💵 예상손익: {pnl_usdt:+.2f} USDT"
                            )
                        send_telegram_message(f"📈 [시세 및 손익 조회]\n종목: {bot_instance.symbol}\n가격: {current_price:.6f} USDT{pos_msg}")
                    else:
                        send_telegram_message("⚠️ API 키가 없어 가격을 조회할 수 없습니다.")
                elif text in ["/log", "log"]:
                    if os.path.exists('trade_history.log'):
                        try:
                            with open('trade_history.log', 'r', encoding='utf-8') as f:
                                lines = f.readlines()
                        except UnicodeDecodeError:
                            with open('trade_history.log', 'r', encoding='latin-1') as f:
                                lines = f.readlines()
                        recent_logs = "".join(lines[-5:]) if lines else "기록된 로그가 없습니다."
                        send_telegram_message(f"📝 [최근 거래 로그 (최대 5줄)]\n{recent_logs}")
                    else:
                        send_telegram_message("⚠️ 기록된 로그 파일이 없습니다.")
                elif text in ["/coins", "coins"]:
                    if bot_instance.exchange:
                        spot_exchange = ccxt.binance({
                            'apiKey': API_KEY,
                            'secret': SECRET_KEY,
                            'enableRateLimit': True,
                            'options': {'defaultType': 'spot'}
                        })
                        spot_balance = spot_exchange.fetch_balance()
                        futures_balance = bot_instance.exchange.fetch_balance()
                        
                        lines = ["🪙 [보유 코인 현황]"]
                        lines.append("\n📦 [현물 지갑]")
                        spot_total = spot_balance.get('total', {})
                        has_spot = False
                        for coin, amount in spot_total.items():
                            if amount and float(amount) > 0:
                                has_spot = True
                                if coin == 'USDT':
                                    lines.append(f"  {coin}: {float(amount):.4f} USDT")
                                else:
                                    try:
                                        ticker = spot_exchange.fetch_ticker(f"{coin}/USDT")
                                        value = float(amount) * ticker['last']
                                        lines.append(f"  {coin}: {float(amount):.6f} 개 (≈ {value:.2f} USDT)")
                                    except:
                                        lines.append(f"  {coin}: {float(amount):.6f} 개")
                        if not has_spot:
                            lines.append("  보유 코인 없음")
                        
                        lines.append("\n📊 [선물 지갑]")
                        futures_total = futures_balance.get('total', {})
                        has_futures = False
                        for coin, amount in futures_total.items():
                            if amount and float(amount) > 0:
                                has_futures = True
                                lines.append(f"  {coin}: {float(amount):.4f}")
                        if not has_futures:
                            lines.append("  보유 자산 없음")
                        
                        send_telegram_message("\n".join(lines))
                    else:
                        send_telegram_message("⚠️ API 키가 없어 잔고를 조회할 수 없습니다.")
                elif text in ["/strategy", "strategy"]:
                    strategy_desc = (
                        "🎯 [현재 매매 전략: 하이브리드 SL/TP 전략]\n\n"
                        "📌 [진입 조건]\n"
                        "1. 추세 추종: ADX > 15 + EMA 9/20 골든/데드크로스 시 진입\n"
                        "2. 눌림목/반등: EMA 정배열 중 Stoch RSI < 20 + BB 하단 근접 → LONG\n"
                        "   EMA 역배열 중 Stoch RSI > 80 + BB 상단 근접 → SHORT\n"
                        "3. 역추세(횡보장만): ADX < 20일 때 RSI < 30 → LONG / RSI > 70 → SHORT\n\n"
                        "📌 [청산 조건]\n"
                        "• 손절(SL): -1.5% 도달 시 자동 청산\n"
                        "• 익절(TP): +3.5% 도달 시 자동 청산\n"
                        "• 반대 신호로는 청산 안 함 (SL/TP 전용)\n\n"
                        "📌 [기타]\n"
                        f"• 타임프레임: 5분봉\n"
                        f"• 레버리지: 5x\n"
                        f"• 분석 주기: 5분\n"
                        f"• SL/TP 체크: 30초"
                    )
                    send_telegram_message(strategy_desc)
                elif text in ["/market", "market"]:
                    try:
                        signal_str = bot_instance.analyzer.get_signal()
                        data = json.loads(signal_str)
                        market_msg = (
                            f"📊 [현재 시장 지표]\n"
                            f"• 현재가: {data.get('price'):.6f}\n"
                            f"• ADX (추세강도): {data.get('adx')}\n"
                            f"• RSI (심리치): {data.get('rsi')}\n"
                            f"• Stoch RSI: {data.get('stoch_k')}\n"
                            f"• 판단: {data.get('decision')}"
                        )
                        send_telegram_message(market_msg)
                    except Exception as e:
                        send_telegram_message(f"⚠️ 지표 조회 실패: {e}")
                elif text in ["/uptime", "uptime"]:
                    uptime_seconds = int(time.time() - bot_instance.start_time)
                    days = uptime_seconds // (24 * 3600)
                    hours = (uptime_seconds % (24 * 3600)) // 3600
                    minutes = (uptime_seconds % 3600) // 60
                    send_telegram_message(f"⏳ [봇 가동 시간]\n{days}일 {hours}시간 {minutes}분째 가동 중 🚀")
                elif text in ["/close", "close"]:
                    if bot_instance.position:
                        ticker = bot_instance.exchange.fetch_ticker(bot_instance.symbol)
                        current_price = ticker['last']
                        bot_instance.close_position("🚨 사용자 강제 종료", current_price)
                    else:
                        send_telegram_message("⚠️ 현재 보유 중인 포지션이 없습니다.")
                elif text in ["/stats", "/stat", "stats", "stat"]:
                    if os.path.exists('trade_history.log'):
                        with open('trade_history.log', 'r', encoding='utf-8', errors='ignore') as f:
                            lines = f.readlines()
                        wins   = sum(1 for line in lines if "✅" in line and "청산" in line)
                        losses = sum(1 for line in lines if "❌" in line and "청산" in line)
                        trades = wins + losses
                        wr = (wins / trades * 100) if trades > 0 else 0
                        send_telegram_message(f"📊 [봇 매매 통계]\n• 총 거래: {trades}회\n• 승리: {wins}회 / 패배: {losses}회\n• 승률: {wr:.1f}%")
                    else:
                        send_telegram_message("⚠️ 기록된 통계가 없습니다.")
                elif text in ["/help", "help"]:
                    help_msg = (
                        "🤖 [사용 가능 명령어 목록]\n\n"
                        "📈 [시장/계좌 관련]\n"
                        "/status : 봇 상태 + 포지션 확인\n"
                        "/balance : 선물 USDT 잔고 확인\n"
                        "/coins : 전체 지갑 잔고 확인\n"
                        "/price : 현재가 + 손익 확인\n"
                        "/market : 현재 기술 지표값 확인 🆕\n\n"
                        "⚙️ [봇 제어/전략 관련]\n"
                        "/strategy : 적용된 매매 전략 상세 🆕\n"
                        "/stats : 최근 매매 성적(승률) 🆕\n"
                        "/uptime : 봇 가동 시간 확인 🆕\n"
                        "/run : 즉시 AI 분석 실행\n"
                        "/close : 포지션 강제 종료(비상용) 🆕\n"
                        "/log : 최근 로그 확인\n"
                        "/help : 도움말"
                    )
                    send_telegram_message(help_msg)
    except requests.exceptions.ReadTimeout:
        pass
    except Exception as e:
        print(f"Telegram polling error: {e}")

def job():
    bot_instance.run()

if __name__ == "__main__":
    send_telegram_message("🤖 봇 재시작 완료!\n명령어 목록이 업데이트되었습니다.\n/help 명령어로 확인해 주세요.")
    
    # 시작할 때 1회 실행
    job()
    
    # 15분마다 실행하도록 스케줄링
    schedule.every(5).minutes.do(job)
    
    print("⏳ Scheduled to run every 15 minutes. Press Ctrl+C to stop.")
    print("⏳ SL/TP check every 30 seconds.")
    while True:
        schedule.run_pending()
        process_telegram_commands()
        
        # 매 30초마다 손절/익절 체크 (포지션이 있을 때만)
        sl_tp_check_counter += 1
        if sl_tp_check_counter >= 30 and bot_instance.position:
            bot_instance.check_stop_loss_take_profit()
            sl_tp_check_counter = 0
        
        time.sleep(1)
