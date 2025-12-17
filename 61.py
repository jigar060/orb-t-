data["date"] = pd.to_datetime(data["date"])
data = data.set_index("date")
data = data.sort_index()

# Shift index so new session starts at 13:00
data["session_day"] = (data.index - pd.Timedelta(hours=4)).date

# Select month
#data = data.loc["2025-01-01":"2025-02-01"]

# Prepare columns
data["signal"] = "HOLD"
data["ORH"] = np.nan
data["ORL"] = np.nan


# -------------------------------
# BUILD ORB PER SESSION DAY
# -------------------------------
ORB_START = "04:00"
ORB_END   = "05:00"

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
        if  cp > ORH and op <ORH:
            new_signal = "BUY"

        # # Condition 2
        if cp < ORL and op>ORL:
            new_signal = "SELL"


        # Save only new signals
        if new_signal != last_signal:
            data.at[t, "signal"] = new_signal
            new_signal=last_signal
            position=1
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

    signals = one_day[one_day["signal"].isin(["BUY", "SELL"])]
    if len(signals) == 0:
        continue

    for entry_time, row in signals.iterrows():

        entry_signal = row["signal"]
        entry_price  = row["close"]


        after = one_day.loc[entry_time:].iloc[1:]
        if after.empty:
          continue

        exit_time   = None
        exit_price  = None
        exit_reason = None
        if entry_signal == "BUY":
            sl_price = entry_price - 0.9985
            tp_price = entry_price + 1.003
        elif entry_signal == "SELL":
          sl_price = entry_price + 1.0015
          tp_price = entry_price - 0.997


        for t2, r2 in after.iterrows():

           # TAKE PROFIT first
           if entry_signal == "BUY" and r2["close"] >= tp_price:
             exit_time = t2
             exit_reason = "TAKE_PROFIT"
             exit_price = r2["close"]
             pnl=exit_price-entry_price
             break

           if entry_signal == "SELL" and r2["close"] <= tp_price:
             exit_time = t2
             exit_reason = "TAKE_PROFIT"
             exit_price = r2["close"]
             pnl=entry_price-exit_price
             break

             # stop loss
           if entry_signal =="BUY" and r2["low"]<sl_price:
             exit_time = t2
             exit_reason = "SL"
             exit_price = sl_price
             position = 0
             pnl=exit_price-entry_price
             break
           if entry_signal =="SELL" and r2["low"]>sl_price:
              exit_time = t2
              exit_reason = "SL"
              exit_price = sl_price
              pnl=entry_price-exit_price
              position = 0
              break



           if exit_time is None:
            exit_time   = after.index[-1]
            exit_price  = after["close"].iloc[-1]
            exit_reason = "DAY_END"
            exit_slice  = after
            pnl=exit_price-entry_price
           else:
            exit_slice = after.loc[:exit_time]

        

        results.append({
            "entry_time": entry_time,
            "entry_signal": entry_signal,
            "entry_price": entry_price,
            "exit_time": exit_time,
            "exit_price": exit_price,
            "exit_reason": exit_reason,
            "pnl":pnl
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
