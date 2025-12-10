from google.colab import files
import io
upload = files.upload()
import pandas as pd
import plotly.graph_objects as go
import numpy as np

data = pd.read_feather("BTC_USDT_USDT-15m-futures.feather")

data["date"] = pd.to_datetime(data["date"])
data = data.set_index("date")
data = data.sort_index()

# Shift index so new session starts at 13:00
data["session_day"] = (data.index - pd.Timedelta(hours=12)).date

# Select month
data = data.loc["2025-01-01":"2025-06-30"]

# Prepare columns
data["signal"] = "HOLD"
data["ORH"] = np.nan
data["ORL"] = np.nan


# -------------------------------
# BUILD ORB PER SESSION DAY
# -------------------------------
ORB_START = "12:45"
ORB_END   = "12:55"

for day, rows in data.groupby(data["session_day"]):
    one_day = rows.sort_index()
    day_str = str(day)

    orb = one_day.between_time(ORB_START, ORB_END)
    if len(orb) == 0:
        continue

    ORH = orb["high"].max()
    ORL = orb["low"].min()

    data.loc[data["session_day"] == day, "ORH"] = ORH
    data.loc[data["session_day"] == day, "ORL"] = ORL


# -------------------------------
# SIGNAL GENERATION (CONDITIONS 1–4)
# USING session_day
# -------------------------------
for day, rows in data.groupby(data["session_day"]):
    one_day = rows.sort_index()
    day_str = str(day)

    if one_day["ORH"].isna().all():
        continue

    ORH = one_day["ORH"].iloc[0]
    ORL = one_day["ORL"].iloc[0]

    last_signal = "HOLD"

    for t, row in one_day.iterrows():
        op = row["open"]
        cp = row["close"]

        new_signal = last_signal

        # Condition 1
        if ORL < op < ORH and cp > ORH:
            new_signal = "BUY"

        # Condition 2
        elif ORL < op < ORH and cp < ORL:
            new_signal = "SELL"

        # Condition 3
        elif last_signal == "BUY" and cp < ORL:
            new_signal = "SELL"

        # Condition 4
        elif last_signal == "SELL" and cp > ORH:
            new_signal = "BUY"

        # Save only new signals
        if new_signal != last_signal:
            data.at[t, "signal"] = new_signal
            last_signal = new_signal
        else:
            data.at[t, "signal"] = "HOLD"


# -------------------------------
# MULTI-SIGNAL TREND CONTINUATION ANALYSIS
# USING session_day
# -------------------------------
results = []

for day, rows in data.groupby(data["session_day"]):
    one_day = rows.sort_index()
    day_str = str(day)

    if one_day["ORH"].isna().all():
        continue

    ORH = one_day["ORH"].dropna().iloc[0]
    ORL = one_day["ORL"].dropna().iloc[0]
    level = ORH - ORL
    if level <= 0:
        continue

    signals = one_day[one_day["signal"].isin(["BUY", "SELL"])]
    if len(signals) == 0:
        continue

    for entry_time, row in signals.iterrows():

        entry_signal = row["signal"]
        entry_price  = row["close"]
        opposite = "SELL" if entry_signal == "BUY" else "BUY"

        after = one_day.loc[entry_time:]

        exit_time = None
        exit_reason = "DAY_END"

        # Opposite signal
        for t2, r2 in after.iterrows():
            if r2["signal"] == opposite:
                exit_time = t2
                exit_reason = "OPPOSITE_SIGNAL"
                break

        if exit_time is None:
            exit_time = after.index[-1]
            exit_price = after["close"].iloc[-1]
            exit_slice = after
        else:
            exit_price = one_day.loc[exit_time, "close"]
            exit_slice = after.loc[:exit_time]

        if entry_signal == "BUY":
            max_high = exit_slice["high"].max()
            max_levels = (max_high - entry_price) / level
        else:
            min_low = exit_slice["low"].min()
            max_levels = (entry_price - min_low) / level

        results.append({
            "session_day": day_str,
            "entry_time": entry_time,
            "entry_signal": entry_signal,
            "entry_price": entry_price,
            "exit_time": exit_time,
            "exit_price": exit_price,
            "exit_reason": exit_reason,
            "max_levels": round(float(max_levels), 3)
        })
results_df = pd.DataFrame(results)
results_df.to_csv("ORB_trend_analysis.csv", index=False)
print("CSV saved — rows:", len(results_df))
# # -------------------------------
# # PLOT CHART (OPTIONAL)
# # -------------------------------
fig = go.Figure()

fig.add_trace(go.Candlestick(
    x=data.index,
    open=data["open"],
    high=data["high"],
    low=data["low"],
    close=data["close"],
    name="Candles"
))

fig.add_trace(go.Scatter(x=data.index, y=data["ORH"], mode="lines", name="ORH"))
fig.add_trace(go.Scatter(x=data.index, y=data["ORL"], mode="lines", name="ORL"))

# Plot buy/sell points
bp = data[data["signal"] == "BUY"]
fig.add_trace(go.Scatter(x=bp.index, y=bp["close"], mode="markers",
    marker=dict(size=10, symbol="triangle-up"), name="BUY"))

sp = data[data["signal"] == "SELL"]
fig.add_trace(go.Scatter(x=sp.index, y=sp["close"], mode="markers",
    marker=dict(size=10, symbol="triangle-down"), name="SELL"))

fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False, height=850)
fig.show()
