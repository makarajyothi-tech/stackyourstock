"""
update_prices.py

Fetches current market prices (CMP) for the 5 stocks tracked on the
StackYourStock page and rewrites index.html in place, replacing only
the price text between the <!--CMP_TICKER--> ... <!--/CMP_TICKER-->
marker comments. Also updates the "Last updated" timestamp banner.

Run by the GitHub Actions workflow daily at 9:30 AM IST.
Safe to run manually too: `python scripts/update_prices.py`
"""

import re
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import yfinance as yf

# Ticker -> Yahoo Finance symbol (NSE listings use the .NS suffix)
TICKERS = {
    "HAL": "HAL.NS",
    "DIXON": "DIXON.NS",
    "SBIN": "SBIN.NS",
    "HCLTECH": "HCLTECH.NS",
    "HDFCBANK": "HDFCBANK.NS",
}

INDEX_PATH = "index.html"


def fetch_price(yahoo_symbol: str) -> float | None:
    """Return the latest available price for a symbol, or None on failure."""
    try:
        ticker = yf.Ticker(yahoo_symbol)
        price = ticker.fast_info.get("lastPrice")
        if price:
            return float(price)
    except Exception as e:
        print(f"  fast_info failed for {yahoo_symbol}: {e}", file=sys.stderr)

    # Fallback: pull the most recent close from a short history window
    try:
        hist = ticker.history(period="5d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception as e:
        print(f"  history fallback failed for {yahoo_symbol}: {e}", file=sys.stderr)

    return None


def format_inr(value: float) -> str:
    """Format a number as an Indian-style rupee string, e.g. ₹14,532."""
    rounded = round(value)
    s = str(rounded)
    if len(s) <= 3:
        formatted = s
    else:
        last3 = s[-3:]
        rest = s[:-3]
        groups = []
        while len(rest) > 2:
            groups.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.insert(0, rest)
        formatted = ",".join(groups) + "," + last3
    return f"₹{formatted}*"


def main():
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    updated_any = False

    for label, yahoo_symbol in TICKERS.items():
        print(f"Fetching {label} ({yahoo_symbol})...")
        price = fetch_price(yahoo_symbol)

        if price is None:
            print(f"  WARNING: could not fetch price for {label}, leaving unchanged.")
            continue

        new_text = format_inr(price)
        pattern = re.compile(
            rf"(<!--CMP_{label}-->)(.*?)(<!--/CMP_{label}-->)", re.DOTALL
        )

        if not pattern.search(html):
            print(f"  WARNING: marker for {label} not found in {INDEX_PATH}.")
            continue

        html = pattern.sub(rf"\g<1>{new_text}\g<3>", html)
        print(f"  Updated {label} -> {new_text}")
        updated_any = True

    # Update the "Last updated" timestamp regardless, so visitors can see
    # the page checked even if a particular ticker fetch failed.
    ist_now = datetime.now(ZoneInfo("Asia/Kolkata"))
    stamp = ist_now.strftime("%d %b %Y, %I:%M %p IST")
    html = re.sub(
        r"(<!--LAST_UPDATED-->)(.*?)(<!--/LAST_UPDATED-->)",
        rf"\g<1>{stamp}\g<3>",
        html,
        flags=re.DOTALL,
    )

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    if updated_any:
        print("Done. index.html updated.")
    else:
        print("No prices were updated this run (all fetches failed or no markers matched).")


if __name__ == "__main__":
    main()
