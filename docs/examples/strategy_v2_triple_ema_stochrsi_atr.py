"""Triple EMA + StochRSI + ATR crypto futures strategy, long and short."""

# @param fast_ema_length int 8 range=3:30:1
# @param mid_ema_length int 14 range=5:60:1
# @param slow_ema_length int 50 range=20:200:5
# @param rsi_length int 14 range=5:50:1
# @param stoch_length int 14 range=5:50:1
# @param signal_level float 0.2 range=0.05:0.45:0.05
# @param atr_length int 14 range=5:50:1
# @param stop_multiplier float 1.8 range=0.5:6:0.1
# @param reward_risk float 2.0 range=0.5:5:0.25
# @param max_stop_pct float 0.04 range=0.005:0.15:0.005
# target_pct is a per-symbol cap before the selected futures leverage multiplier;
# risk_per_trade_pct reduces it when the ATR stop is wider.
# @param target_pct float 0.1 range=0.05:0.2:0.05
# @param risk_per_trade_pct float 0.005 range=0.001:0.02:0.001
# @param min_ema_spread_atr float 0.25 range=0:2:0.05
# @param time_limit_bars int 288 range=12:576:12
# @param profit_lock_activation_r float 0.5 range=0.25:2:0.25
# @param profit_lock_trail_r float 0.5 range=0.25:2:0.25
# @param trailing_lock_profit_pct float 0.0015 range=0:0.01:0.0005


UNIVERSE = [
    "Crypto:BTC/USDT@swap", "Crypto:ETH/USDT@swap", "Crypto:SOL/USDT@swap",
    "Crypto:BNB/USDT@swap", "Crypto:XRP/USDT@swap", "Crypto:DOGE/USDT@swap",
    "Crypto:ADA/USDT@swap", "Crypto:AVAX/USDT@swap", "Crypto:LINK/USDT@swap",
    "Crypto:BCH/USDT@swap",
]


def initialize(context):
    g.last_bar = {}
    g.last_signal = {}
    context.set_universe(UNIVERSE)
    context.subscribe(frequency="5m", fields=["open", "high", "low", "close", "volume"])
    context.set_metadata(
        direction_mode="one_way",
        strategy_family="TRIPLE_EMA_STOCHRSI_ATR",
        position_manager="ATR_STOP_RR_TARGET",
    )
    context.set_warmup(180)
    context.allow_leverage(max_leverage=5)


def _ema(values, length):
    length = max(1, int(length))
    alpha = 2.0 / (length + 1.0)
    current = float(values[0])
    result = [current]
    for value in values[1:]:
        current = alpha * float(value) + (1.0 - alpha) * current
        result.append(current)
    return result


def _rsi_series(closes, length):
    length = max(2, int(length))
    result = [50.0 for _ in closes]
    if len(closes) <= length:
        return result
    gains = []
    losses = []
    for index in range(1, len(closes)):
        change = float(closes[index]) - float(closes[index - 1])
        gains.append(max(0.0, change))
        losses.append(max(0.0, -change))
    avg_gain = sum(gains[:length]) / length
    avg_loss = sum(losses[:length]) / length
    result[length] = 100.0 if avg_loss <= 0 else 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))
    for index in range(length + 1, len(closes)):
        offset = index - 1
        avg_gain = ((avg_gain * (length - 1)) + gains[offset]) / length
        avg_loss = ((avg_loss * (length - 1)) + losses[offset]) / length
        result[index] = 100.0 if avg_loss <= 0 else 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))
    return result


def _stoch_rsi(closes, rsi_length, stoch_length):
    rsi = _rsi_series(closes, rsi_length)
    length = max(2, int(stoch_length))
    result = [0.5 for _ in closes]
    for index in range(length, len(closes)):
        window = rsi[index - length + 1:index + 1]
        lowest = min(window)
        highest = max(window)
        result[index] = (rsi[index] - lowest) / (highest - lowest) if highest > lowest else 0.5
    return result


def _atr(bars, length):
    length = max(1, int(length))
    values = []
    for index in range(1, len(bars)):
        high = float(bars["high"].iloc[index])
        low = float(bars["low"].iloc[index])
        previous = float(bars["close"].iloc[index - 1])
        values.append(max(high - low, abs(high - previous), abs(low - previous)))
    if not values:
        return 0.0
    current = sum(values[:length]) / min(length, len(values))
    for value in values[length:]:
        current = ((current * (length - 1)) + value) / length
    return current


def _number(value):
    return str(round(float(value), 8))


def _reason(direction, entry, stop, target, rr, stoch, bar_time):
    return (
        "TRIPLE_EMA_STOCHRSI_ATR|intent=entry|direction="
        + ("LONG" if direction > 0 else "SHORT")
        + "|reference_entry=" + _number(entry)
        + "|stop=" + _number(stop)
        + "|target=" + _number(target)
        + "|reward_risk=" + _number(rr)
        + "|stop_pct=" + _number(abs(entry - stop) / entry)
        + "|stochrsi=" + _number(stoch)
        + "|signal_age=0|evidence=ema8_14_50_alignment+stochrsi_cross"
        + "|bar=" + str(bar_time)
    )


def _trade(symbol, direction, entry, stop, target, rr, stoch, bar_time, position_pct, time_limit_bars, profit_lock_activation_r, profit_lock_trail_r, trailing_lock_profit_pct):
    amount = float(get_position(symbol).amount or 0.0)
    if direction > 0 and amount < -1e-12:
        order_target_percent(symbol, 0.0, reason="TRIPLE_EMA_STOCHRSI_ATR|intent=close_opposite|direction=LONG")
        return True
    if direction < 0 and amount > 1e-12:
        order_target_percent(symbol, 0.0, reason="TRIPLE_EMA_STOCHRSI_ATR|intent=close_opposite|direction=SHORT")
        return True
    if (direction > 0 and amount > 1e-12) or (direction < 0 and amount < -1e-12):
        return False
    side = "long" if direction > 0 else "short"
    client_id = "triple-ema-stochrsi-" + side + "-" + str(symbol) + "-" + str(bar_time).replace(" ", "T").replace(":", "")
    stop_pct = abs(entry - stop) / entry
    reason = _reason(direction, entry, stop, target, rr, stoch, bar_time)
    reason += "|profit_lock_activation_r=" + _number(profit_lock_activation_r)
    reason += "|profit_lock_trail_r=" + _number(profit_lock_trail_r)
    reason += "|trailing_lock_profit_pct=" + _number(trailing_lock_profit_pct)
    reason += "|position_pct=" + _number(position_pct)
    order_target_percent(
        symbol,
        position_pct if direction > 0 else -position_pct,
        reason=reason,
        stop_loss_pct=stop_pct,
        take_profit_pct=abs(target - entry) / entry,
        time_limit_seconds=max(300, int(time_limit_bars) * 300),
        trailing_stop_pct=stop_pct * max(0.0, profit_lock_trail_r),
        trailing_activation_pct=stop_pct * max(0.0, profit_lock_activation_r),
        trailing_lock_profit_pct=trailing_lock_profit_pct,
        client_order_id=client_id,
    )
    return True


def handle_data(context, data):
    fast_length = int(context.params.get("fast_ema_length", 8))
    mid_length = int(context.params.get("mid_ema_length", 14))
    slow_length = int(context.params.get("slow_ema_length", 50))
    rsi_length = int(context.params.get("rsi_length", 14))
    stoch_length = int(context.params.get("stoch_length", 14))
    signal_level = float(context.params.get("signal_level", 0.2))
    atr_length = int(context.params.get("atr_length", 14))
    stop_multiplier = float(context.params.get("stop_multiplier", 1.8))
    reward_risk = float(context.params.get("reward_risk", 2.0))
    max_stop_pct = float(context.params.get("max_stop_pct", 0.04))
    target_pct = float(context.params.get("target_pct", 0.1))
    risk_per_trade_pct = max(0.0001, float(context.params.get("risk_per_trade_pct", 0.005)))
    execution_leverage = max(1.0, float(context.leverage))
    min_ema_spread_atr = max(0.0, float(context.params.get("min_ema_spread_atr", 0.25)))
    time_limit_bars = max(12, int(context.params.get("time_limit_bars", 288)))
    profit_lock_activation_r = max(0.0, float(context.params.get("profit_lock_activation_r", 0.5)))
    profit_lock_trail_r = max(0.0, float(context.params.get("profit_lock_trail_r", 0.5)))
    trailing_lock_profit_pct = max(0.0, float(context.params.get("trailing_lock_profit_pct", 0.0015)))
    count = max(slow_length * 3, rsi_length + stoch_length + 30, atr_length * 4, 100) + 8

    for symbol in UNIVERSE:
        bars = get_history(count, "5m", ["open", "high", "low", "close", "volume"], symbol)
        if len(bars) < max(slow_length + 5, rsi_length + stoch_length + 3, atr_length + 8):
            continue
        bar_time = str(bars.index[-1])
        if g.last_bar.get(symbol) == bar_time:
            continue
        g.last_bar[symbol] = bar_time
        closes = [float(value) for value in bars["close"].to_numpy()]
        fast = _ema(closes, fast_length)
        mid = _ema(closes, mid_length)
        slow = _ema(closes, slow_length)
        stoch = _stoch_rsi(closes, rsi_length, stoch_length)
        current = stoch[-1]
        previous = stoch[-2]
        long_trend = (
            fast[-1] > mid[-1] > slow[-1]
            and slow[-1] > slow[-6]
            and closes[-1] > fast[-1]
        )
        short_trend = (
            fast[-1] < mid[-1] < slow[-1]
            and slow[-1] < slow[-6]
            and closes[-1] < fast[-1]
        )
        direction = 1 if long_trend and previous <= signal_level and current > signal_level else 0
        if short_trend and previous >= 1.0 - signal_level and current < 1.0 - signal_level:
            direction = -1
        if direction == 0:
            continue
        signal_key = str(direction) + "|" + bar_time
        if g.last_signal.get(symbol) == signal_key:
            continue
        entry = closes[-1]
        atr = _atr(bars, atr_length)
        if entry <= 0 or atr <= 0:
            continue
        if abs(fast[-1] - slow[-1]) / atr < min_ema_spread_atr:
            continue
        stop_pct = min(max_stop_pct, max(0.0005, stop_multiplier * atr / entry))
        stop = entry * (1.0 - stop_pct) if direction > 0 else entry * (1.0 + stop_pct)
        target = entry * (1.0 + stop_pct * reward_risk) if direction > 0 else entry * (1.0 - stop_pct * reward_risk)
        position_pct = min(target_pct, risk_per_trade_pct / max(1e-9, execution_leverage * stop_pct))
        if position_pct <= 0:
            continue
        _trade(symbol, direction, entry, stop, target, reward_risk, current, bar_time, position_pct, time_limit_bars, profit_lock_activation_r, profit_lock_trail_r, trailing_lock_profit_pct)
        g.last_signal[symbol] = signal_key
