from google.colab import files
import io
upload = files.upload()
import pandas as pd
import plotly.graph_objects as go
import numpy as np
#------------------------------------------

# Load dataset
data = pd.read_csv("BTCUSDT-5m-2025-01.csv")
data.head(120000)

#---------------------------------------------

# -------------------------------
# PREPROCESSING
# -------------------------------
#data["date"] = pd.to_datetime(data["date"])
data["date"] = pd.to_datetime(data["open_time"], unit="ms")

data = data.set_index("date")

data = data.loc["2025-01-01":"2025-01-30"]
data = data.between_time("00:00", "23:59")

data["signal"] = ""
data["ORH"] = None
data["ORL"] = None

# -------------------------------
# ORB + SIGNAL GENERATION
# -------------------------------
for day_name, day_rows in data.groupby(data.index.date):

    one_day = data.loc[str(day_name)]

    orb_candle = one_day.between_time("13:00", "13:05")
    if len(orb_candle) == 0:
        continue

    ORH = orb_candle["high"].max()
    ORL = orb_candle["low"].min()

    data.loc[str(day_name), "ORH"] = ORH
    data.loc[str(day_name), "ORL"] = ORL

    last_signal = None


for i in range(len(one_day)):
        candle = one_day.iloc[i]
        open_price = candle["open"]
        close_price = candle["close"]

        if ORL < open_price < ORH:

            if close_price > ORH and last_signal != "BUY":
                data.loc[candle.name, "signal"] = "BUY"
                last_signal = "BUY"

            elif close_price < ORL and last_signal != "SELL":
                data.loc[candle.name, "signal"] = "SELL"
                last_signal = "SELL"

            else:
                data.loc[candle.name, "signal"] = "HOLD"

        else:
            data.loc[candle.name, "signal"] = "HOLD"


# -------------------------------
# PLOT CHART
# -------------------------------
fig = go.Figure()

fig.add_trace(go.Candlestick(
    x=data.index,
    open=data["open"],
    high=data["high"],
    low=data["low"],
    close=data["close"],
    name="Candles"
))

fig.add_trace(go.Scatter(
    x=data.index,
    y=data["ORH"],
    mode="lines",
    name="ORH",
    line=dict(color="green", dash="dot")
))

fig.add_trace(go.Scatter(
    x=data.index,
    y=data["ORL"],
    mode="lines",
    name="ORL",
    line=dict(color="red", dash="dot")
))

buy_points = data[data["signal"] == "BUY"]
fig.add_trace(go.Scatter(
    x=buy_points.index,
    y=buy_points["close"],
    mode="markers",
    marker=dict(size=12, color="blue", symbol="triangle-up"),
    name="BUY"
))

sell_points = data[data["signal"] == "SELL"]
fig.add_trace(go.Scatter(
    x=sell_points.index,
    y=sell_points["close"],
    mode="markers",
    marker=dict(size=12, color="white", symbol="triangle-down"),
    name="SELL"
))

fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False, height=850)
fig.show()


# -------------------------------
# TREND CONTINUATION ANALYSIS
# -------------------------------

results = []

for day_name, one_day in data.groupby(data.index.date):

    one_day = data.loc[str(day_name)]

    ORH = one_day["ORH"].dropna().iloc[0]
    ORL = one_day["ORL"].dropna().iloc[0]
    level = ORH - ORL

    # find breakout entry candle
    entries = one_day[one_day["signal"].isin(["BUY", "SELL"])]

    if len(entries) == 0:
        continue

    entry_time = entries.index[0]
    entry_signal = entries.iloc[0]["signal"]
    entry_price = one_day.loc[entry_time, "close"]

    opposite_signal = "SELL" if entry_signal == "BUY" else "BUY"

    after = one_day.loc[entry_time:]

    exit_point = None
    for t2, row2 in after.iterrows():

        if opposite_signal == "BUY" and row2["close"] > ORH:
            exit_point = t2
            break

        if opposite_signal == "SELL" and row2["close"] < ORL:
            exit_point = t2
            break

    if exit_point is None:
        exit_slice = after
    else:
        exit_slice = after.loc[:exit_point]

    if entry_signal == "BUY":
        max_high = exit_slice["high"].max()
        max_levels = (max_high - entry_price) / level
    else:
        min_low = exit_slice["low"].min()
        max_levels = (entry_price - min_low) / level

    results.append({
        "date": str(day_name),
        "signal": entry_signal,
        "time": entry_time,
        "entry_price": entry_price,
        "max_levels": round(max_levels, 3)
    })

# save results
results_df = pd.DataFrame(results)
results_df.to_csv("ORB_trend_analysis.csv", index=False)
print("CSV saved: ORB_trend_analysis.csv")
