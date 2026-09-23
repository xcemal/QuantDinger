"""Qullamagi-style EMA breakout/pullback strategy for crypto swaps.

The implementation keeps the open-source idea small and testable: aligned
fast/mid/slow EMAs, a confirmed range breakout or a post-breakout EMA reclaim,
relative-volume confirmation, and native ATR stop/target protection.
"""

import math

# @param fast_ema_length int 8 range=3:30:1
# @param mid_ema_length int 21 range=5:80:1
# @param slow_ema_length int 55 range=20:200:5
# @param breakout_lookback int 20 range=5:100:1
# @param pullback_bars int 24 range=3:80:1
# @param atr_length int 14 range=5:50:1
# @param min_relative_volume float 1.2 range=0.5:5:0.1
# @param stop_multiplier float 1.8 range=0.5:6:0.1
# @param reward_risk float 2.0 range=0.5:5:0.25
# @param max_stop_pct float 0.04 range=0.005:0.15:0.005
# @param max_entry_atr_pct float 0.015 range=0.002:0.1:0.001
# target_pct is a per-symbol cap before the selected futures leverage multiplier;
# risk_per_trade_pct reduces it when the ATR stop is wider.
# @param target_pct float 0.1 range=0.05:0.2:0.05
# @param risk_per_trade_pct float 0.005 range=0.001:0.02:0.001
# @param time_limit_bars int 288 range=12:576:12
# @param profit_lock_activation_r float 0.5 range=0.25:2:0.25
# @param profit_lock_trail_r float 0.5 range=0.25:2:0.25
# @param trailing_lock_profit_pct float 0.0015 range=0:0.01:0.0005
# @param use_pullback int 1 range=0:1:1


UNIVERSE = [
    "Crypto:BTC/USDT@swap", "Crypto:ETH/USDT@swap", "Crypto:SOL/USDT@swap",
    "Crypto:BNB/USDT@swap", "Crypto:XRP/USDT@swap", "Crypto:DOGE/USDT@swap",
    "Crypto:ADA/USDT@swap", "Crypto:AVAX/USDT@swap", "Crypto:LINK/USDT@swap",
    "Crypto:BCH/USDT@swap",
]


def initialize(context):
    g.last_bar = {}
    g.bar_number = {}
    g.breakout = {}
    g.last_setup = {}
    context.set_universe(UNIVERSE)
    context.subscribe(frequency="5m", fields=["open", "high", "low", "close", "volume"])
    context.set_metadata(
        direction_mode="one_way",
        strategy_family="QULLAMAGI_EMA_BREAKOUT",
        position_manager="ATR_STOP_RR_TARGET",
    )
    context.set_warmup(180)
    context.allow_leverage(max_leverage=5)


def _ema(values, length):
    length = max(1, int(length))
    if not values:
        return []
    alpha = 2.0 / (length + 1.0)
    current = float(values[0])
    result = [current]
    for value in values[1:]:
        current = alpha * float(value) + (1.0 - alpha) * current
        result.append(current)
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


def _relative_volume(bars, lookback):
    lookback = max(2, int(lookback))
    if len(bars) < lookback + 1:
        return 0.0
    baseline = float(bars["volume"].iloc[-lookback - 1:-1].mean())
    current = float(bars["volume"].iloc[-1])
    return current / baseline if baseline > 0 else 0.0


def _number(value):
    return str(round(float(value), 8))


def _reason(mode, direction, entry, stop, target, rr, volume_ratio, bar_time):
    return (
        "QULLAMAGI_EMA_BREAKOUT|intent=entry|mode=" + mode
        + "|direction=" + ("LONG" if direction > 0 else "SHORT")
        + "|reference_entry=" + _number(entry)
        + "|stop=" + _number(stop)
        + "|target=" + _number(target)
        + "|reward_risk=" + _number(rr)
        + "|stop_pct=" + _number(abs(entry - stop) / entry)
        + "|volume_ratio=" + _number(volume_ratio)
        + "|signal_age=0|evidence=ema_alignment+confirmed_breakout_or_reclaim"
        + "|bar=" + str(bar_time)
    )


def _trade(symbol, direction, entry, stop, target, rr, volume_ratio, mode, bar_time, position_pct, time_limit_bars, profit_lock_activation_r, profit_lock_trail_r, trailing_lock_profit_pct):
    amount = float(get_position(symbol).amount or 0.0)
    if direction > 0 and amount < -1e-12:
        order_target_percent(symbol, 0.0, reason="QULLAMAGI_EMA_BREAKOUT|intent=close_opposite|direction=LONG")
        return True
    if direction < 0 and amount > 1e-12:
        order_target_percent(symbol, 0.0, reason="QULLAMAGI_EMA_BREAKOUT|intent=close_opposite|direction=SHORT")
        return True
    if (direction > 0 and amount > 1e-12) or (direction < 0 and amount < -1e-12):
        return False
    side = "long" if direction > 0 else "short"
    client_id = "qullamagi-" + mode + "-" + side + "-" + str(symbol) + "-" + str(bar_time).replace(" ", "T").replace(":", "")
    stop_pct = abs(entry - stop) / entry
    reason = _reason(mode, direction, entry, stop, target, rr, volume_ratio, bar_time)
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
    mid_length = int(context.params.get("mid_ema_length", 21))
    slow_length = int(context.params.get("slow_ema_length", 55))
    lookback = int(context.params.get("breakout_lookback", 20))
    pullback_bars = int(context.params.get("pullback_bars", 24))
    atr_length = int(context.params.get("atr_length", 14))
    min_relative_volume = float(context.params.get("min_relative_volume", 1.2))
    stop_multiplier = float(context.params.get("stop_multiplier", 1.8))
    reward_risk = float(context.params.get("reward_risk", 2.0))
    max_stop_pct = float(context.params.get("max_stop_pct", 0.04))
    max_entry_atr_pct = float(context.params.get("max_entry_atr_pct", 0.015))
    target_pct = float(context.params.get("target_pct", 0.1))
    risk_per_trade_pct = max(0.0001, float(context.params.get("risk_per_trade_pct", 0.005)))
    execution_leverage = max(1.0, float(context.leverage))
    time_limit_bars = max(12, int(context.params.get("time_limit_bars", 288)))
    profit_lock_activation_r = max(0.0, float(context.params.get("profit_lock_activation_r", 0.5)))
    profit_lock_trail_r = max(0.0, float(context.params.get("profit_lock_trail_r", 0.5)))
    trailing_lock_profit_pct = max(0.0, float(context.params.get("trailing_lock_profit_pct", 0.0015)))
    use_pullback = int(context.params.get("use_pullback", 1))
    count = max(slow_length * 3, lookback + 40, atr_length * 4, 100) + 8

    for symbol in UNIVERSE:
        bars = get_history(count, "5m", ["open", "high", "low", "close", "volume"], symbol)
        if len(bars) < max(slow_length + 5, lookback + 3, atr_length + 8):
            continue
        bar_time = str(bars.index[-1])
        if g.last_bar.get(symbol) == bar_time:
            continue
        g.last_bar[symbol] = bar_time
        g.bar_number[symbol] = int(g.bar_number.get(symbol, 0)) + 1

        closes = [float(value) for value in bars["close"].to_numpy()]
        highs = [float(value) for value in bars["high"].to_numpy()]
        lows = [float(value) for value in bars["low"].to_numpy()]
        fast = _ema(closes, fast_length)
        mid = _ema(closes, mid_length)
        slow = _ema(closes, slow_length)
        atr = _atr(bars, atr_length)
        entry = closes[-1]
        if entry <= 0 or atr <= 0:
            continue
        volume_ratio = _relative_volume(bars, max(10, lookback))
        long_trend = fast[-1] > mid[-1] > slow[-1] and slow[-1] > slow[-6]
        short_trend = fast[-1] < mid[-1] < slow[-1] and slow[-1] < slow[-6]
        prior_high = max(highs[-lookback - 1:-1])
        prior_low = min(lows[-lookback - 1:-1])
        previous_high = max(highs[-lookback - 2:-2])
        previous_low = min(lows[-lookback - 2:-2])
        breakout_direction = 0
        if long_trend and volume_ratio >= min_relative_volume and entry > prior_high and closes[-2] <= previous_high:
            if (entry - prior_high) / entry <= max_entry_atr_pct:
                breakout_direction = 1
        elif short_trend and volume_ratio >= min_relative_volume and entry < prior_low and closes[-2] >= previous_low:
            if (prior_low - entry) / entry <= max_entry_atr_pct:
                breakout_direction = -1
        if breakout_direction:
            g.breakout[symbol] = (breakout_direction, g.bar_number[symbol])

        direction = breakout_direction
        mode = "breakout"
        if direction == 0 and use_pullback:
            setup = g.breakout.get(symbol)
            if setup and g.bar_number[symbol] - int(setup[1]) <= max(1, pullback_bars):
                reclaim_long = long_trend and lows[-2] <= fast[-2] and entry > fast[-1] and closes[-2] <= fast[-2]
                reclaim_short = short_trend and highs[-2] >= fast[-2] and entry < fast[-1] and closes[-2] >= fast[-2]
                if setup[0] > 0 and reclaim_long:
                    direction = 1
                    mode = "pullback_reclaim"
                elif setup[0] < 0 and reclaim_short:
                    direction = -1
                    mode = "pullback_reclaim"
        if direction == 0:
            continue
        setup_key = mode + "|" + str(direction) + "|" + bar_time
        if g.last_setup.get(symbol) == setup_key:
            continue
        stop_pct = min(max_stop_pct, max(0.0005, stop_multiplier * atr / entry))
        stop = entry * (1.0 - stop_pct) if direction > 0 else entry * (1.0 + stop_pct)
        target = entry * (1.0 + stop_pct * reward_risk) if direction > 0 else entry * (1.0 - stop_pct * reward_risk)
        position_pct = min(target_pct, risk_per_trade_pct / max(1e-9, execution_leverage * stop_pct))
        if position_pct <= 0:
            continue
        if _trade(symbol, direction, entry, stop, target, reward_risk, volume_ratio, mode, bar_time, position_pct, time_limit_bars, profit_lock_activation_r, profit_lock_trail_r, trailing_lock_profit_pct):
            g.breakout[symbol] = None
        g.last_setup[symbol] = setup_key
