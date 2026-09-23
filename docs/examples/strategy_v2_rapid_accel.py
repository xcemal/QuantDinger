"""Native Strategy API V2 example: HA reversal followed by accelerating candles.

This source is intentionally self-contained because Strategy API V2 programs are
compiled in the user strategy sandbox.  It emits signed one-way crypto-swap
orders and keeps the full signal rationale in the native order ``reason``.
"""

# @param adx_length int 14 range=5:40:1
# @param adx_min float 20 range=5:50:1
# @param wick_tolerance float 0.15 range=0.02:0.5:0.01
# @param atr_length int 14 range=5:50:1
# @param stop_multiplier float 1.8 range=0.5:6:0.1
# @param reward_risk float 2.0 range=0.5:5:0.25
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
    context.subscribe(frequency="1m", fields=["open", "high", "low", "close", "volume"])
    context.set_metadata(direction_mode="one_way", strategy_family="RAPID_ACCEL")
    context.set_warmup(180)
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
    if len(true_ranges) < length:
        return 0.0
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


def _ha_values(bars):
    opens = []
    closes = []
    for index in range(len(bars)):
        raw_open = float(bars["open"].iloc[index])
        raw_high = float(bars["high"].iloc[index])
        raw_low = float(bars["low"].iloc[index])
        raw_close = float(bars["close"].iloc[index])
        ha_close = (raw_open + raw_high + raw_low + raw_close) / 4.0
        ha_open = (raw_open + raw_close) / 2.0 if index == 0 else (opens[-1] + closes[-1]) / 2.0
        opens.append(ha_open)
        closes.append(ha_close)
    return opens, closes


def _near_wickless(bars, index, direction, tolerance):
    raw_open = float(bars["open"].iloc[index])
    raw_high = float(bars["high"].iloc[index])
    raw_low = float(bars["low"].iloc[index])
    raw_close = float(bars["close"].iloc[index])
    body = abs(raw_close - raw_open)
    if body <= 0:
        return False
    directional_wick = min(raw_open, raw_close) - raw_low if direction > 0 else raw_high - max(raw_open, raw_close)
    return directional_wick <= body * max(0.0, tolerance)


def _number(value):
    return str(round(float(value), 8))


def _signal_reason(direction, entry, stop, target, rr, adx, body_ratio, bar_time):
    direction_name = "LONG" if direction > 0 else "SHORT"
    return (
        "RAPID_ACCEL|direction=" + direction_name
        + "|reference_entry=" + _number(entry)
        + "|stop=" + _number(stop)
        + "|target=" + _number(target)
        + "|reward_risk=" + _number(rr)
        + "|signal_age=0|adx=" + _number(adx)
        + "|ha_body_acceleration=" + _number(body_ratio)
        + "|evidence=ha_reversal+3_body_increase+near_wickless"
        + "|bar=" + str(bar_time)
    )


def _trade(context, symbol, direction, entry, stop, target, rr, adx, body_ratio, bar_time, target_pct):
    amount = float(get_position(symbol).amount or 0.0)
    if direction > 0 and amount < -1e-12:
        order_target_percent(symbol, 0.0, reason="RAPID_ACCEL|close_opposite|direction=LONG")
        return
    if direction < 0 and amount > 1e-12:
        order_target_percent(symbol, 0.0, reason="RAPID_ACCEL|close_opposite|direction=SHORT")
        return
    if (direction > 0 and amount > 1e-12) or (direction < 0 and amount < -1e-12):
        return
    reason = _signal_reason(direction, entry, stop, target, rr, adx, body_ratio, bar_time)
    side = "long" if direction > 0 else "short"
    client_id = "rapid-accel-" + side + "-" + str(symbol) + "-" + str(bar_time).replace(" ", "T").replace(":", "")
    order_target_percent(
        symbol,
        target_pct if direction > 0 else -target_pct,
        reason=reason,
        stop_loss_pct=abs(entry - stop) / entry,
        take_profit_pct=abs(target - entry) / entry,
        client_order_id=client_id,
    )


def handle_data(context, data):
    adx_length = int(context.params.get("adx_length", 14))
    adx_min = float(context.params.get("adx_min", 20.0))
    wick_tolerance = float(context.params.get("wick_tolerance", 0.15))
    atr_length = int(context.params.get("atr_length", 14))
    stop_multiplier = float(context.params.get("stop_multiplier", 1.8))
    reward_risk = float(context.params.get("reward_risk", 2.0))
    target_pct = float(context.params.get("target_pct", 0.25))
    count = max(atr_length * 3, adx_length * 3, 60) + 8
    for symbol in UNIVERSE:
        bars = get_history(count, "1m", ["open", "high", "low", "close", "volume"], symbol)
        if len(bars) < max(adx_length * 2 + 4, atr_length + 8, 12):
            continue
        bar_time = str(bars.index[-1])
        if g.last_signal.get(symbol) == bar_time:
            continue
        ha_open, ha_close = _ha_values(bars)
        colors = [1 if ha_close[index] > ha_open[index] else -1 for index in range(len(bars))]
        if len(colors) < 5:
            continue
        direction = 1 if colors[-4:] == [-1, 1, 1, 1] else -1 if colors[-4:] == [1, -1, -1, -1] else 0
        if direction == 0:
            continue
        if not all(_near_wickless(bars, index, direction, wick_tolerance) for index in range(len(bars) - 3, len(bars))):
            continue
        bodies = [abs(ha_close[index] - ha_open[index]) for index in range(len(bars))]
        if not (bodies[-3] > bodies[-4] and bodies[-2] > bodies[-3] and bodies[-1] > bodies[-2]):
            continue
        adx = _adx(bars, adx_length)
        if adx < adx_min:
            continue
        entry = float(bars["close"].iloc[-1])
        atr = _atr(bars, atr_length)
        if entry <= 0 or atr <= 0:
            continue
        stop = entry - stop_multiplier * atr if direction > 0 else entry + stop_multiplier * atr
        target = entry + reward_risk * (entry - stop) if direction > 0 else entry - reward_risk * (stop - entry)
        body_ratio = bodies[-1] / bodies[-2] if bodies[-2] > 0 else 0.0
        _trade(context, symbol, direction, entry, stop, target, reward_risk, adx, body_ratio, bar_time, target_pct)
        g.last_signal[symbol] = bar_time
