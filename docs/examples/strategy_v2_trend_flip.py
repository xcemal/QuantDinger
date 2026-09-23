"""Native Strategy API V2 example: event-only SuperTrend flips."""

import math

# @param st_atr_length int 10 range=5:50:1
# @param st_factor float 3.0 range=1:8:0.25
# @param adx_length int 14 range=5:40:1
# @param adx_min float 20 range=5:50:1
# @param chop_length int 14 range=5:50:1
# @param chop_max float 61.8 range=40:75:0.5
# @param stop_multiplier float 2.0 range=0.5:6:0.25
# @param reward_risk float 2.0 range=0.5:5:0.25
# @param max_stop_pct float 0.04 range=0.005:0.15:0.005
# @param target_pct float 0.25 range=0.05:1:0.05


UNIVERSE = [
    "Crypto:BTC/USDT@swap", "Crypto:ETH/USDT@swap", "Crypto:SOL/USDT@swap",
    "Crypto:BNB/USDT@swap", "Crypto:XRP/USDT@swap", "Crypto:DOGE/USDT@swap",
    "Crypto:ADA/USDT@swap", "Crypto:AVAX/USDT@swap", "Crypto:LINK/USDT@swap",
    "Crypto:BCH/USDT@swap", "Crypto:LTC/USDT@swap", "Crypto:DOT/USDT@swap",
    "Crypto:SUI/USDT@swap", "Crypto:TRX/USDT@swap", "Crypto:AAVE/USDT@swap",
    "Crypto:UNI/USDT@swap", "Crypto:NEAR/USDT@swap", "Crypto:APT/USDT@swap",
    "Crypto:ARB/USDT@swap", "Crypto:OP/USDT@swap", "Crypto:INJ/USDT@swap",
    "Crypto:ATOM/USDT@swap", "Crypto:FIL/USDT@swap", "Crypto:ETC/USDT@swap",
    "Crypto:TON/USDT@swap",
]


def initialize(context):
    g.last_signal = {}
    context.set_universe(UNIVERSE)
    context.subscribe(frequency="5m", fields=["open", "high", "low", "close", "volume"])
    context.set_metadata(direction_mode="one_way", strategy_family="TREND_FLIP")
    context.set_warmup(220)
    context.allow_leverage(max_leverage=3)


def _true_ranges(bars):
    values = []
    for index in range(1, len(bars)):
        high = float(bars["high"].iloc[index])
        low = float(bars["low"].iloc[index])
        previous_close = float(bars["close"].iloc[index - 1])
        values.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
    return values


def _atr(bars, length):
    values = _true_ranges(bars)
    if not values:
        return 0.0
    length = max(1, int(length))
    if len(values) <= length:
        return sum(values) / len(values)
    current = sum(values[:length]) / length
    for value in values[length:]:
        current = ((current * (length - 1)) + value) / length
    return current


def _adx(bars, length):
    length = max(2, int(length))
    if len(bars) < length * 2 + 2:
        return 0.0
    true_ranges = []
    plus_moves = []
    minus_moves = []
    for index in range(1, len(bars)):
        high = float(bars["high"].iloc[index])
        low = float(bars["low"].iloc[index])
        previous_high = float(bars["high"].iloc[index - 1])
        previous_low = float(bars["low"].iloc[index - 1])
        previous_close = float(bars["close"].iloc[index - 1])
        true_ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
        up = high - previous_high
        down = previous_low - low
        plus_moves.append(up if up > down and up > 0 else 0.0)
        minus_moves.append(down if down > up and down > 0 else 0.0)
    smoothed_tr = sum(true_ranges[:length])
    smoothed_plus = sum(plus_moves[:length])
    smoothed_minus = sum(minus_moves[:length])
    dx_values = []
    for index in range(length - 1, len(true_ranges)):
        if index >= length:
            smoothed_tr = smoothed_tr - (smoothed_tr / length) + true_ranges[index]
            smoothed_plus = smoothed_plus - (smoothed_plus / length) + plus_moves[index]
            smoothed_minus = smoothed_minus - (smoothed_minus / length) + minus_moves[index]
        if smoothed_tr <= 0:
            continue
        plus_di = 100.0 * smoothed_plus / smoothed_tr
        minus_di = 100.0 * smoothed_minus / smoothed_tr
        denominator = plus_di + minus_di
        dx_values.append(100.0 * abs(plus_di - minus_di) / denominator if denominator > 0 else 0.0)
    if len(dx_values) < length:
        return sum(dx_values) / len(dx_values) if dx_values else 0.0
    current = sum(dx_values[:length]) / length
    for value in dx_values[length:]:
        current = ((current * (length - 1)) + value) / length
    return current


def _supertrend_directions(bars, length, factor):
    true_ranges = _true_ranges(bars)
    atr_values = [0.0 for _ in range(len(bars))]
    if len(true_ranges) < length:
        return atr_values, [0 for _ in range(len(bars))]
    current_atr = sum(true_ranges[:length]) / length
    atr_values[length] = current_atr
    for index in range(length + 1, len(bars)):
        current_atr = ((current_atr * (length - 1)) + true_ranges[index - 1]) / length
        atr_values[index] = current_atr
    upper = 0.0
    lower = 0.0
    directions = [0 for _ in range(len(bars))]
    for index in range(length, len(bars)):
        high = float(bars["high"].iloc[index])
        low = float(bars["low"].iloc[index])
        close = float(bars["close"].iloc[index])
        previous_close = float(bars["close"].iloc[index - 1])
        middle = (high + low) / 2.0
        basic_upper = middle + factor * atr_values[index]
        basic_lower = middle - factor * atr_values[index]
        if index == length:
            upper = basic_upper
            lower = basic_lower
            directions[index] = 1
            continue
        upper = basic_upper if basic_upper < upper or previous_close > upper else upper
        lower = basic_lower if basic_lower > lower or previous_close < lower else lower
        previous_direction = directions[index - 1]
        if previous_direction < 0 and close > upper:
            directions[index] = 1
        elif previous_direction > 0 and close < lower:
            directions[index] = -1
        else:
            directions[index] = previous_direction
    return atr_values, directions


def _chop(bars, length):
    length = max(2, int(length))
    if len(bars) < length + 2:
        return 100.0
    start = len(bars) - length
    true_range_sum = 0.0
    highest = float(bars["high"].iloc[start])
    lowest = float(bars["low"].iloc[start])
    for index in range(start, len(bars)):
        high = float(bars["high"].iloc[index])
        low = float(bars["low"].iloc[index])
        previous_close = float(bars["close"].iloc[index - 1])
        true_range_sum += max(high - low, abs(high - previous_close), abs(low - previous_close))
        highest = max(highest, high)
        lowest = min(lowest, low)
    span = highest - lowest
    return 100.0 if span <= 0 or true_range_sum <= 0 else 100.0 * math.log10(true_range_sum / span) / math.log10(length)


def _number(value):
    return str(round(float(value), 8))


def _reason(direction, entry, stop, target, rr, adx, chop, atr_pct, bar_time):
    direction_name = "LONG" if direction > 0 else "SHORT"
    return (
        "TREND_FLIP|direction=" + direction_name
        + "|reference_entry=" + _number(entry)
        + "|stop=" + _number(stop)
        + "|target=" + _number(target)
        + "|reward_risk=" + _number(rr)
        + "|signal_age=0|adx=" + _number(adx)
        + "|chop=" + _number(chop)
        + "|atr_pct=" + _number(atr_pct)
        + "|evidence=supertrend_direction_flip+adx_gate+chop_gate"
        + "|bar=" + str(bar_time)
    )


def _trade(symbol, direction, entry, stop, target, rr, adx, chop, atr_pct, bar_time, target_pct):
    amount = float(get_position(symbol).amount or 0.0)
    if direction > 0 and amount < -1e-12:
        order_target_percent(symbol, 0.0, reason="TREND_FLIP|close_opposite|direction=LONG")
        return
    if direction < 0 and amount > 1e-12:
        order_target_percent(symbol, 0.0, reason="TREND_FLIP|close_opposite|direction=SHORT")
        return
    if (direction > 0 and amount > 1e-12) or (direction < 0 and amount < -1e-12):
        return
    side = "long" if direction > 0 else "short"
    client_id = "trend-flip-" + side + "-" + str(symbol) + "-" + str(bar_time).replace(" ", "T").replace(":", "")
    entry_reason = _reason(direction, entry, stop, target, rr, adx, chop, atr_pct, bar_time)
    order_target_percent(
        symbol,
        target_pct if direction > 0 else -target_pct,
        reason=entry_reason,
        stop_loss_pct=abs(entry - stop) / entry,
        take_profit_pct=abs(target - entry) / entry,
        client_order_id=client_id,
    )


def handle_data(context, data):
    st_atr_length = int(context.params.get("st_atr_length", 10))
    st_factor = float(context.params.get("st_factor", 3.0))
    adx_length = int(context.params.get("adx_length", 14))
    adx_min = float(context.params.get("adx_min", 20.0))
    chop_length = int(context.params.get("chop_length", 14))
    chop_max = float(context.params.get("chop_max", 61.8))
    stop_multiplier = float(context.params.get("stop_multiplier", 2.0))
    reward_risk = float(context.params.get("reward_risk", 2.0))
    max_stop_pct = float(context.params.get("max_stop_pct", 0.04))
    target_pct = float(context.params.get("target_pct", 0.25))
    count = max(st_atr_length * 4, adx_length * 3, chop_length + 20, 80) + 8
    for symbol in UNIVERSE:
        bars = get_history(count, "5m", ["open", "high", "low", "close", "volume"], symbol)
        if len(bars) < max(st_atr_length + 5, adx_length * 2 + 4, chop_length + 2):
            continue
        bar_time = str(bars.index[-1])
        if g.last_signal.get(symbol) == bar_time:
            continue
        atr_values, directions = _supertrend_directions(bars, st_atr_length, st_factor)
        if len(directions) < 2 or directions[-1] == 0 or directions[-2] == 0 or directions[-1] == directions[-2]:
            continue
        direction = directions[-1]
        adx = _adx(bars, adx_length)
        chop = _chop(bars, chop_length)
        if adx < adx_min or chop > chop_max:
            continue
        entry = float(bars["close"].iloc[-1])
        atr = float(atr_values[-1]) if atr_values[-1] > 0 else _atr(bars, st_atr_length)
        if entry <= 0 or atr <= 0:
            continue
        atr_pct = atr / entry
        stop_pct = min(max_stop_pct, max(0.0001, stop_multiplier * atr_pct))
        stop = entry * (1.0 - stop_pct) if direction > 0 else entry * (1.0 + stop_pct)
        target = entry * (1.0 + stop_pct * reward_risk) if direction > 0 else entry * (1.0 - stop_pct * reward_risk)
        _trade(symbol, direction, entry, stop, target, reward_risk, adx, chop, atr_pct, bar_time, target_pct)
        g.last_signal[symbol] = bar_time
