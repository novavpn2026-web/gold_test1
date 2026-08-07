import asyncio
from datetime import datetime
import sqlite3
import flet as ft
import requests
import yfinance as yf

# ==========================================
# تنظیمات اختصاصی و کلیدهای امنیتی شما
# ==========================================
GOOGLE_API_KEY = "AQ.Ab8RN6K1HRwDR7039iBTlpz1kHfSNbpVMYbkYjmchhS74-MzLw"
TELEGRAM_BOT_TOKEN = "8742857684:AAG9RPKSwBvATem_lNEa_kfCNgc-1WvHXf0"
TELEGRAM_CHAT_ID = "692142878"


# ==========================================
# مدیریت دیتابیس (Thread-Safe & Context Manager)
# ==========================================
def init_db():
  with sqlite3.connect("gold_signals.db") as conn:
    cursor = conn.cursor()
    cursor.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                action TEXT,
                price REAL,
                stop_loss REAL,
                take_profit REAL,
                confidence INTEGER,
                status TEXT DEFAULT 'OPEN'
            )
        """)
    conn.commit()


def log_signal(action, price, sl, tp, conf):
  with sqlite3.connect("gold_signals.db") as conn:
    cursor = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        """
            INSERT INTO signals (timestamp, action, price, stop_loss, take_profit, confidence, status)
            VALUES (?, ?, ?, ?, ?, ?, 'OPEN')
        """,
        (timestamp, action, price, sl, tp, conf),
    )
    conn.commit()


def get_db_stats():
  try:
    with sqlite3.connect("gold_signals.db") as conn:
      cursor = conn.cursor()
      cursor.execute("SELECT COUNT(*) FROM signals")
      total = cursor.fetchone()[0]
      cursor.execute("SELECT COUNT(*) FROM signals WHERE action='BUY'")
      buys = cursor.fetchone()[0]
      cursor.execute("SELECT COUNT(*) FROM signals WHERE action='SELL'")
      sells = cursor.fetchone()[0]
      return total, buys, sells
  except Exception:
    return 0, 0, 0


# ==========================================
# لایه شبکه و تحلیل تکنیکال
# ==========================================
def send_telegram_alert(message):
  url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
  payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
  try:
    response = requests.post(url, json=payload, timeout=10)
    return response.status_code == 200
  except Exception:
    return False


def fetch_advanced_gold_data():
  import pandas as pd

  try:
    gold = yf.Ticker("GC=F")
    hist = gold.history(period="5d", interval="1h")

    if not hist.empty and len(hist) > 20:
      current_price = round(float(hist["Close"].iloc[-1]), 2)

      delta = hist["Close"].diff()
      gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
      loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
      rs = gain / loss
      rsi = round(float(100 - (100 / (1 + rs.iloc[-1]))), 2)
      if pd.isna(rsi):
        rsi = 50.0

      ema_20 = round(
          float(hist["Close"].ewm(span=20, adjust=False).mean().iloc[-1]), 2
      )
      ema_50 = round(
          float(hist["Close"].ewm(span=50, adjust=False).mean().iloc[-1]), 2
      )

      rolling_mean = hist["Close"].rolling(window=20).mean().iloc[-1]
      rolling_std = hist["Close"].rolling(window=20).std().iloc[-1]

      if pd.isna(rolling_std) or rolling_std == 0:
        rolling_std = 5.0

      upper_band = round(float(rolling_mean + (2 * rolling_std)), 2)
      lower_band = round(float(rolling_mean - (2 * rolling_std)), 2)

      return {
          "symbol": "XAU/USD (Live)",
          "current_price": current_price,
          "rsi_14": rsi,
          "ema_20": ema_20,
          "ema_50": ema_50,
          "upper_band": upper_band,
          "lower_band": lower_band,
      }
  except Exception:
    pass

  base_price = 2650.50
  return {
      "symbol": "XAU/USD (Fallback)",
      "current_price": base_price,
      "rsi_14": 50.0,
      "ema_20": base_price,
      "ema_50": base_price,
      "upper_band": base_price + 15,
      "lower_band": base_price - 15,
  }


def high_precision_quant_analyzer(market_data):
  price = market_data["current_price"]
  rsi = market_data["rsi_14"]
  ema_20 = market_data["ema_20"]
  ema_50 = market_data["ema_50"]
  lower = market_data["lower_band"]
  upper = market_data["upper_band"]

  if rsi < 35 and price <= lower and ema_20 > ema_50 * 0.995:
    return {
        "action": "BUY",
        "confidence_score": 91,
        "stop_loss": round(price - 14.0, 2),
        "take_profit": round(price + 28.0, 2),
        "reason": f"RSI ({rsi}) oversold at Lower Bollinger Band.",
    }
  elif rsi > 65 and price >= upper and ema_20 < ema_50 * 1.005:
    return {
        "action": "SELL",
        "confidence_score": 91,
        "stop_loss": round(price + 14.0, 2),
        "take_profit": round(price - 28.0, 2),
        "reason": f"RSI ({rsi}) overbought at Upper Bollinger Band.",
    }
  else:
    return {
        "action": "HOLD",
        "confidence_score": 60,
        "stop_loss": 0.0,
        "take_profit": 0.0,
        "reason": f"Market is consolidating. RSI is neutral ({rsi}).",
    }


# ==========================================
# رابط کاربری مدرن فلت (بر پایه Async و ساختار جدید)
# ==========================================
async def main(page: ft.Page):
  page.title = "Gold Quant AI - Mobile Dashboard"
  page.theme_mode = ft.ThemeMode.DARK
  page.padding = 20
  page.vertical_alignment = ft.MainAxisAlignment.START
  page.scroll = ft.ScrollMode.AUTO

  # 1. مقداردهی اولیه المان‌های UI (بدون متن نهایی)
  signal_title = ft.Text(
      "Signal: WAITING FOR SCAN", weight=ft.FontWeight.BOLD, size=16
  )
  price_text = ft.Text("💰 Price: $0.00", size=15)
  conf_text = ft.Text("📊 Confidence: 0%", size=15)
  details_text = ft.Text(
      "🛑 Stop Loss: $0.0 | 🎯 Take Profit: $0.0", size=12, color="grey400"
  )
  reason_text = ft.Text("📝 Reason: Press scan to analyze market.", size=12)

  # 2. فراخوانی اولیه UI قبل از پردازش سنگین
  page.add(
      ft.Row([ft.Icon("trending_up", size=28, color="amber400"), ft.Text("Gold Quant Mobile", size=20, weight=ft.FontWeight.BOLD, color="white")], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
      ft.Divider(height=10, color="transparent"),
      ft.Card(content=ft.Container(content=ft.Column([signal_title, ft.Divider(), price_text, conf_text, details_text, reason_text], spacing=8), padding=20)),
  )
  # حیاتی: مجبور کردن فلت به رندر کردن عناصر بالا قبل از ادامه
  page.update()

  # 3. اجرای سنگین در ترد پس‌زمینه (بدون فریز کردن UI)
  await asyncio.to_thread(init_db)
  initial_stats = await asyncio.to_thread(get_db_stats)
  total_sig, buy_sig, sell_sig = initial_stats
  
  # 4. به‌روزرسانی نهایی UI با آمار دیتابیس
  stats_text = ft.Text(f"Total Logged: {total_sig} | Buy: {buy_sig} | Sell: {sell_sig}", size=13, color="blue200")
  status_banner = ft.Text("Status: Ready", size=12, color="green400")
  scan_button = ft.Button(
      content="Run Live Market Scan & Alert",
      icon="bolt",
      style=ft.ButtonStyle(color="white", bgcolor="blue700", shape=ft.RoundedRectangleBorder(radius=12)),
      width=400,
  )

  # تابع اصلی اسکن که با کلیک اجرا می‌شود
  async def run_full_scan_async(e):
    scan_button.disabled = True
    status_banner.value = "Status: Fetching live market & analyzing..."
    page.update()

    try:
      market_data = await asyncio.to_thread(fetch_advanced_gold_data)
      analysis = high_precision_quant_analyzer(market_data)

      action = analysis.get("action")
      conf = analysis.get("confidence_score", 0)
      price = market_data["current_price"]
      sl = analysis.get("stop_loss")
      tp = analysis.get("take_profit")
      reason = analysis.get("reason")

      if action == "BUY":
        signal_title.value = "Signal: BUY 🟢"
        signal_title.color = "green400"
      elif action == "SELL":
        signal_title.value = "Signal: SELL 🔴"
        signal_title.color = "red400"
      else:
        signal_title.value = "Signal: HOLD 🟡"
        signal_title.color = "amber400"

      price_text.value = f"💰 Price: ${price}"
      conf_text.value = f"📊 Confidence: {conf}%"
      details_text.value = f"🛑 Stop Loss: ${sl} | 🎯 Take Profit: ${tp}"
      reason_text.value = f"📝 Reason: {reason}"

      if action in ["BUY", "SELL"] and conf >= 85:
        await asyncio.to_thread(log_signal, action, price, sl, tp, conf)
        msg = f"🚨 *Mobile App Signal Alert* 🚨\n\n🔹 *Action:* `{action}`\n💰 *Price:* `${price}`\n📊 *Confidence:* `{conf}%`\n🛑 *Stop Loss:* `${sl}`\n🎯 *Take Profit:* `${tp}`\n📝 *Reason:* {reason}"
        await asyncio.to_thread(send_telegram_alert, msg)
        status_banner.value = "Status: Scan complete! Signal sent & logged successfully."
      else:
        status_banner.value = "Status: Scan complete. No high-probability entry detected."

      t, b, s = await asyncio.to_thread(get_db_stats)
      stats_text.value = f"Total Logged: {t} | Buy: {b} | Sell: {s}"

    except Exception as ex:
      status_banner.value = f"Status: Error occurred -> {str(ex)}"
    finally:
      scan_button.disabled = False
      page.update()

  scan_button.on_click = run_full_scan_async

  # 5. اضافه کردن بقیه عناصر به صفحه
  page.add(
      ft.Card(content=ft.Container(content=ft.Column([ft.Text("📈 Database Statistics", weight=ft.FontWeight.BOLD, size=14), stats_text], spacing=5), padding=15)),
      ft.Divider(height=10, color="transparent"),
      scan_button,
      ft.Divider(height=10, color="transparent"),
      status_banner,
  )
  page.update()


if __name__ == "__main__":
  # اجرای برنامه به صورت Async (سازگار با نسخه‌های جدید فلت)
  ft.run(main)