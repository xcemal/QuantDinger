"""Native Strategy API V2 example: confirmed-pivot sweep and absorption proxy."""

# The strategy deliberately labels its OHLCV-only absorption evidence in the
# order reason.  It does not claim to have exchange taker-buy/taker-sell data.

# @param pivot_length int 3 range=2:10:1
# @param rvol_lookback int 20 range=5:100:1
# @param min_relative_volume float 1.5 range=1:5:0.1
# @param min_sweep_depth_atr float 0.15 range=0.05:2:0.05
# @param reclaim_threshold float 0.5 range=0.1:1:0.05
# @param atr_length int 14 range=5:50:1
# @param atr_stop_buffer float 0.5 range=0.1:3:0.1
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
    g.last_bar = {}
    g.last_pivot = {}
    context.set_universe(UNIVERSE)
    context.subscribe(frequency="5m", fields=["open", "high", "low", "close", "volume"])
    context.subscribe(frequency="1m", fields=["open", "high", "low", "close", "volume"])
    context.set_metadata(
        direction_mode="one_way",
        strategy_family="SWEEP_ABSORPTION",
        absorption_evidence="ohlcv_proxy",
    )
    context.set_warmup(240)
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


def _latest_confirmed_pivot(bars, length, direction):
    length = max(2, int(length))
    latest_candidate = len(bars) - length - 2
    if latest_candidate < length:
        return None
    for index in reversed(range(length, latest_candidate + 1)):
        left = index - length
        right = index + length + 1
        if direction > 0:
            value = float(bars["high"].iloc[index])
            window_max = float(bars["high"].iloc[left:right].max())
            if value >= window_max and value > float(bars["high"].iloc[index - 1]):
                return index, value, str(bars.index[index])
        else:
            value = float(bars["low"].iloc[index])
            window_min = float(bars["low"].iloc[left:right].min())
            if value <= window_min and value < float(bars["low"].iloc[index - 1]):
                return index, value, str(bars.index[index])
    return None


def _relative_volume(bars, lookback):
    lookback = max(2, int(lookback))
    if len(bars) < lookback + 1:
        return 0.0
    baseline = float(bars["volume"].iloc[-lookback - 1:-1].mean())
    current = float(bars["volume"].iloc[-1])
    return current / baseline if baseline > 0 else 0.0


def _ohlcv_rejection(bars, direction):
    high = float(bars["high"].iloc[-1])
    low = float(bars["low"].iloc[-1])
    close = float(bars["close"].iloc[-1])
    span = high - low
    if span <= 0:
        return False
    close_location = (close - low) / span
    return close_location <= 0.4 if direction < 0 else close_location >= 0.6


def _lower_timeframe_rejection(symbol, direction):
    lower = get_history(5, "1m", ["open", "high", "low", "close", "volume"], symbol)
    if len(lower) < 3:
        return False
    matches = 0
    for index in range(len(lower)):
        high = float(lower["high"].iloc[index])
        low = float(lower["low"].iloc[index])
        close = float(lower["close"].iloc[index])
        span = high - low
        if span <= 0:
            continue
        location = (close - low) / span
        if (direction < 0 and location <= 0.45) or (direction > 0 and location >= 0.55):
            matches += 1
    return matches >= max(2, len(lower) // 2)


def _number(value):
    return str(round(float(value), 8))


def _reason(direction, entry, stop, target, rr, rvol, depth_atr, pivot, absorption, bar_time):
    direction_name = "LONG" if direction > 0 else "SHORT"
    return (
        "SWEEP_ABSORPTION|direction=" + direction_name
        + "|reference_entry=" + _number(entry)
        + "|stop=" + _number(stop)
        + "|target=" + _number(target)
        + "|reward_risk=" + _number(rr)
        + "|signal_age=0|rvol=" + _number(rvol)
        + "|sweep_depth_atr=" + _number(depth_atr)
        + "|pivot=" + _number(pivot)
        + "|absorption_proxy=ohlcv"
        + ("+1m_rejection" if absorption else "")
        + "|evidence=confirmed_pivot+sweep_reclaim+elevated_rvol+rejection"
        + "|bar=" + str(bar_time)
    )


def _trade(symbol, direction, entry, stop, target, rr, rvol, depth_atr, pivot, absorption, bar_time, target_pct):
    amount = float(get_position(symbol).amount or 0.0)
    if direction > 0 and amount < -1e-12:
        order_target_percent(symbol, 0.0, reason="SWEEP_ABSORPTION|close_opposite|direction=LONG")
        return
    if direction < 0 and amount > 1e-12:
        order_target_percent(symbol, 0.0, reason="SWEEP_ABSORPTION|close_opposite|direction=SHORT")
        return
    if (direction > 0 and amount > 1e-12) or (direction < 0 and amount < -1e-12):
        return
    side = "long" if direction > 0 else "short"
    client_id = "sweep-absorption-" + side + "-" + str(symbol) + "-" + str(bar_time).replace(" ", "T").replace(":", "")
    reason = _reason(direction, entry, stop, target, rr, rvol, depth_atr, pivot, absorption, bar_time)
    order_target_percent(
        symbol,
        target_pct if direction > 0 else -target_pct,
        reason=reason,
        stop_loss_pct=abs(entry - stop) / entry,
        take_profit_pct=abs(target - entry) / entry,
        client_order_id=client_id,
    )


def handle_data(context, data):
    pivot_length = int(context.params.get("pivot_length", 3))
    rvol_lookback = int(context.params.get("rvol_lookback", 20))
    min_relative_volume = float(context.params.get("min_relative_volume", 1.5))
    min_sweep_depth_atr = float(context.params.get("min_sweep_depth_atr", 0.15))
    reclaim_threshold = float(context.params.get("reclaim_threshold", 0.5))
    atr_length = int(context.params.get("atr_length", 14))
    atr_stop_buffer = float(context.params.get("atr_stop_buffer", 0.5))
    reward_risk = float(context.params.get("reward_risk", 2.0))
    target_pct = float(context.params.get("target_pct", 0.25))
    count = max(atr_length * 3, rvol_lookback + pivot_length * 2 + 8, 80) + 8
    for symbol in UNIVERSE:
        bars = get_history(count, "5m", ["open", "high", "low", "close", "volume"], symbol)
        if len(bars) < max(rvol_lookback + 2, pivot_length * 3 + 4, atr_length + 8):
            continue
        bar_time = str(bars.index[-1])
        if g.last_bar.get(symbol) == bar_time:
            continue
        g.last_bar[symbol] = bar_time
        atr = _atr(bars, atr_length)
        if atr <= 0:
            continue
        rvol = _relative_volume(bars, rvol_lookback)
        if rvol < min_relative_volume:
            continue
        entry = float(bars["close"].iloc[-1])
        high = float(bars["high"].iloc[-1])
        low = float(bars["low"].iloc[-1])
        high_pivot = _latest_confirmed_pivot(bars, pivot_length, 1)
        low_pivot = _latest_confirmed_pivot(bars, pivot_length, -1)
        direction = 0
        pivot = 0.0
        sweep_depth = 0.0
        pivot_key = ""
        if high_pivot is not None:
            pivot = high_pivot[1]
            sweep_depth = (high - pivot) / atr
            reclaim = (pivot - entry) / max(high - pivot, atr * 0.0001)
            if high > pivot and sweep_depth >= min_sweep_depth_atr and entry < pivot and reclaim >= reclaim_threshold and _ohlcv_rejection(bars, -1):
                direction = -1
                pivot_key = high_pivot[2]
        if direction == 0 and low_pivot is not None:
            pivot = low_pivot[1]
            sweep_depth = (pivot - low) / atr
            reclaim = (entry - pivot) / max(pivot - low, atr * 0.0001)
            if low < pivot and sweep_depth >= min_sweep_depth_atr and entry > pivot and reclaim >= reclaim_threshold and _ohlcv_rejection(bars, 1):
                direction = 1
                pivot_key = low_pivot[2]
        if direction == 0 or g.last_pivot.get(symbol) == pivot_key:
            continue
        lower_absorption = _lower_timeframe_rejection(symbol, direction)
        stop = high + atr * atr_stop_buffer if direction < 0 else low - atr * atr_stop_buffer
        target = entry - reward_risk * (stop - entry) if direction < 0 else entry + reward_risk * (entry - stop)
        _trade(symbol, direction, entry, stop, target, reward_risk, rvol, sweep_depth, pivot, lower_absorption, bar_time, target_pct)
        g.last_pivot[symbol] = pivot_key
