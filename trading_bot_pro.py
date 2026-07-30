"""
Trading Bot Pro — Alpaca Paper Trading
=======================================
Upgrades over the starter bot:
  - Multi-symbol trading
  - Combined signals: MA crossover + RSI filter (fewer false signals)
  - Per-position stop-loss and take-profit
  - Trade journal saved to CSV
  - Built-in BACKTEST mode — test the strategy on historical data
    with zero risk before ever connecting to a broker

Usage:
  python trading_bot_pro.py backtest        # test strategy on history (no API keys needed for yfinance)
  python trading_bot_pro.py live            # run paper trading (needs Alpaca keys)

Setup:
  pip install alpaca-py pandas yfinance
  export ALPACA_API_KEY="your_key"          # only needed for live mode
  export ALPACA_SECRET_KEY="your_secret"
"""

import os
import sys
import time
import csv
from datetime import datetime, timedelta

import pandas as pd

# ----------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------
SYMBOLS = ["SPY", "QQQ", "AAPL"]   # symbols to trade
FAST_MA = 10
SLOW_MA = 30
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70                # don't buy above this
RSI_OVERSOLD = 30                  # don't sell below this (avoid panic exits)
POSITION_DOLLARS = 1000            # $ per position
STOP_LOSS_PCT = 0.05               # exit if position drops 5%
TAKE_PROFIT_PCT = 0.10             # exit if position gains 10%
MAX_DAILY_LOSS = 100               # halt bot if down this much today ($)
MAX_OPEN_POSITIONS = 3
CHECK_INTERVAL = 300               # seconds between live checks
JOURNAL_FILE = "trade_journal.csv"

# Backtest settings
BACKTEST_START = "2022-01-01"
BACKTEST_CAPITAL = 10_000


# ----------------------------------------------------------------------
# INDICATORS
# ----------------------------------------------------------------------
def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["fast"] = df["close"].rolling(FAST_MA).mean()
    df["slow"] = df["close"].rolling(SLOW_MA).mean()

    # RSI
    delta = df["close"].diff()
    gain = delta.clip(lower=0).rolling(RSI_PERIOD).mean()
    loss = (-delta.clip(upper=0)).rolling(RSI_PERIOD).mean()
    rs = gain / loss.replace(0, 1e-9)
    df["rsi"] = 100 - (100 / (1 + rs))
    return df


def signal_at(df: pd.DataFrame, i: int) -> str:
    """Signal for row i using crossover + RSI filter."""
    if i < SLOW_MA:
        return "HOLD"
    pf, ps = df["fast"].iloc[i - 1], df["slow"].iloc[i - 1]
    cf, cs = df["fast"].iloc[i], df["slow"].iloc[i]
    rsi = df["rsi"].iloc[i]

    if pf <= ps and cf > cs and rsi < RSI_OVERBOUGHT:
        return "BUY"
    if pf >= ps and cf < cs and rsi > RSI_OVERSOLD:
        return "SELL"
    return "HOLD"


# ----------------------------------------------------------------------
# TRADE JOURNAL
# ----------------------------------------------------------------------
def log_trade(symbol, side, qty, price, reason):
    exists = os.path.exists(JOURNAL_FILE)
    with open(JOURNAL_FILE, "a", newline="") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["timestamp", "symbol", "side", "qty", "price", "reason"])
        w.writerow([datetime.now().isoformat(), symbol, side, qty, f"{price:.2f}", reason])
    print(f"[TRADE] {side} {qty:.4f} {symbol} @ ${price:.2f} ({reason})")


# ----------------------------------------------------------------------
# BACKTEST MODE
# ----------------------------------------------------------------------
def backtest():
    import yfinance as yf

    print(f"Backtesting {SYMBOLS} from {BACKTEST_START} with ${BACKTEST_CAPITAL:,}\n")
    total_final = 0
    per_symbol_capital = BACKTEST_CAPITAL / len(SYMBOLS)

    for symbol in SYMBOLS:
        raw = yf.download(symbol, start=BACKTEST_START, progress=False, auto_adjust=True)
        if raw.empty:
            print(f"{symbol}: no data, skipping")
            continue
        df = pd.DataFrame({"close": raw["Close"].squeeze()}).reset_index()
        df = add_indicators(df)

        cash = per_symbol_capital
        shares = 0.0
        entry_price = None
        trades = 0
        wins = 0

        for i in range(len(df)):
            price = df["close"].iloc[i]

            # Stop-loss / take-profit check on open position
            if shares > 0 and entry_price:
                change = (price - entry_price) / entry_price
                if change <= -STOP_LOSS_PCT or change >= TAKE_PROFIT_PCT:
                    cash += shares * price
                    wins += 1 if price > entry_price else 0
                    trades += 1
                    shares, entry_price = 0.0, None
                    continue

            sig = signal_at(df, i)
            if sig == "BUY" and shares == 0:
                shares = cash / price
                cash = 0.0
                entry_price = price
            elif sig == "SELL" and shares > 0:
                cash += shares * price
                wins += 1 if price > entry_price else 0
                trades += 1
                shares, entry_price = 0.0, None

        final = cash + shares * df["close"].iloc[-1]
        total_final += final
        ret = (final / per_symbol_capital - 1) * 100
        buy_hold = (df["close"].iloc[-1] / df["close"].iloc[SLOW_MA] - 1) * 100
        win_rate = (wins / trades * 100) if trades else 0
        print(f"{symbol:6s} | return {ret:+7.1f}% | buy&hold {buy_hold:+7.1f}% | "
              f"trades {trades:3d} | win rate {win_rate:.0f}%")

    total_ret = (total_final / BACKTEST_CAPITAL - 1) * 100
    print(f"\nPortfolio: ${BACKTEST_CAPITAL:,.0f} -> ${total_final:,.0f} ({total_ret:+.1f}%)")
    print("\nNote: past performance never guarantees future results. If the strategy")
    print("loses in backtest, it will almost certainly lose live. If it wins in")
    print("backtest, it may STILL lose live (overfitting, fees, slippage).")


# ----------------------------------------------------------------------
# LIVE (PAPER) MODE
# ----------------------------------------------------------------------
def live():
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce

    API_KEY = os.environ["ALPACA_API_KEY"]
    SECRET_KEY = os.environ["ALPACA_SECRET_KEY"]
    trading = TradingClient(API_KEY, SECRET_KEY, paper=True)  # paper=True = no real money
    data = StockHistoricalDataClient(API_KEY, SECRET_KEY)

    def bars(symbol):
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=datetime.now() - timedelta(days=SLOW_MA * 3),
        )
        df = data.get_stock_bars(req).df.reset_index()
        return add_indicators(df)

    def position(symbol):
        try:
            p = trading.get_open_position(symbol)
            return float(p.qty), float(p.avg_entry_price)
        except Exception:
            return 0.0, None

    def order(symbol, side, dollars=None, qty=None, reason=""):
        req = MarketOrderRequest(
            symbol=symbol, side=side, time_in_force=TimeInForce.DAY,
            notional=dollars, qty=qty,
        )
        trading.submit_order(req)
        price = bars(symbol)["close"].iloc[-1]
        log_trade(symbol, side.name, qty or dollars / price, price, reason)

    print(f"Paper trading {SYMBOLS} | ${POSITION_DOLLARS}/position | "
          f"SL {STOP_LOSS_PCT*100:.0f}% / TP {TAKE_PROFIT_PCT*100:.0f}%\n")

    while True:
        try:
            clock = trading.get_clock()
            if not clock.is_open:
                print(f"[{datetime.now():%H:%M}] Market closed. Next open: {clock.next_open}")
                time.sleep(CHECK_INTERVAL)
                continue

            # Daily loss circuit breaker
            acct = trading.get_account()
            daily_pl = float(acct.equity) - float(acct.last_equity)
            if daily_pl < -MAX_DAILY_LOSS:
                print(f"[RISK] Daily loss ${-daily_pl:.2f} > cap. Halting for the day.")
                break

            open_positions = len(trading.get_all_positions())

            for symbol in SYMBOLS:
                df = bars(symbol)
                price = df["close"].iloc[-1]
                qty, entry = position(symbol)

                # Stop-loss / take-profit
                if qty > 0 and entry:
                    change = (price - entry) / entry
                    if change <= -STOP_LOSS_PCT:
                        order(symbol, OrderSide.SELL, qty=qty, reason="stop-loss")
                        continue
                    if change >= TAKE_PROFIT_PCT:
                        order(symbol, OrderSide.SELL, qty=qty, reason="take-profit")
                        continue

                sig = signal_at(df, len(df) - 1)
                print(f"[{datetime.now():%H:%M}] {symbol} ${price:.2f} | {sig} | "
                      f"held={qty:.4f} | RSI={df['rsi'].iloc[-1]:.0f}")

                if sig == "BUY" and qty == 0 and open_positions < MAX_OPEN_POSITIONS:
                    order(symbol, OrderSide.BUY, dollars=POSITION_DOLLARS, reason="crossover+rsi")
                    open_positions += 1
                elif sig == "SELL" and qty > 0:
                    order(symbol, OrderSide.SELL, qty=qty, reason="crossover+rsi")
                    open_positions -= 1

        except KeyboardInterrupt:
            print("Stopped by user.")
            break
        except Exception as e:
            print(f"[ERROR] {e}")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "backtest"
    if mode == "live":
        live()
    else:
        backtest()
