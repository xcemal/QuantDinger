"""Confirmed-pivot liquidity sweep reversal.

This candidate converts the failed-breakout idea into a non-repainting swing
level model.  A pivot is usable only after its right-side confirmation bars
have closed.  A sweep must pierce that confirmed level, close back inside it,
and then receive a later directional confirmation before entry.
"""

PERSIST_RUNTIME_STATE = True

# @param exit_channel_length int 20 range=10:40:10
# @param regime_ema_length int 100 range=50:200:25
# @param atr_length int 14 range=5:50:1
# @param pivot_left_bars int 3 range=2:10:1
# @param pivot_right_bars int 3 range=2:10:1
# @param pivot_lookback_bars int 100 range=40:220:20
# @param max_sweep_depth_atr float 1.5 range=0.25:3:0.25
# @param min_wick_ratio float 0.35 range=0.1:0.8:0.05
# @param min_relative_volume float 1.2 range=0.0:3:0.1
# @param confirmation_window_bars int 2 range=1:5:1
# @param stop_buffer_atr float 0.25 range=0.0:1:0.05
# @param max_stop_pct float 0.10 range=0.02:0.20:0.01
# @param target_pct float 0.10 range=0:0.50:0.01
# @param risk_per_trade_pct float 0.005 range=0:0.02:0.0005
# @param estimated_round_trip_cost_pct float 0.002 range=0:0.02:0.0005
# @param max_target_pct float 0.10 range=0.01:0.50:0.01
# @param allow_long int 1 range=0:1:1
# @param allow_short int 1 range=0:1:1
# @param profit_lock_activation_r float 0.75 range=0:2:0.25
# @param profit_lock_trail_r float 1.0 range=0.25:2:0.25
# @param trailing_lock_profit_pct float 0.001 range=0:0.01:0.0005


UNIVERSE = [
    "Crypto:BTC/USDT@swap", "Crypto:ETH/USDT@swap", "Crypto:SOL/USDT@swap",
    "Crypto:BNB/USDT@swap", "Crypto:XRP/USDT@swap", "Crypto:DOGE/USDT@swap",
    "Crypto:ADA/USDT@swap", "Crypto:AVAX/USDT@swap", "Crypto:LINK/USDT@swap",
    "Crypto:BCH/USDT@swap",
]


def initialize(context):
    g.last_bar = {}
    g.sequence = {}
    g.pending_sweep = {}
    context.set_universe(UNIVERSE)
    context.subscribe(frequency="1h", fields=["open", "high", "low", "close", "volume"])
    context.subscribe(frequency="4h", fields=["open", "high", "low", "close", "volume"])
    context.set_metadata(
        direction_mode="one_way",
        strategy_family="CONFIRMED_PIVOT_SWEEP_REVERSAL",
        entry="confirmed_pivot_sweep_plus_next_bar_reclaim",
        regime="completed_4h_ema100",
        exit="opposite_1h_channel_close",
        position_manager="sweep_wick_stop_plus_profit_activation_trailing_lock",
    )
    context.set_warmup(260)
    context.allow_leverage(max_leverage=5)


def _values(bars, field):
    return [float(value) for value in bars[field].to_numpy()]


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
    highs = _values(bars, "high")
    lows = _values(bars, "low")
    closes = _values(bars, "close")
    if len(closes) < 2:
        return 0.0
    ranges = []
    for index in range(1, len(closes)):
        ranges.append(max(
            highs[index] - lows[index],
            abs(highs[index] - closes[index - 1]),
            abs(lows[index] - closes[index - 1]),
        ))
    length = max(1, int(length))
    if len(ranges) <= length:
        return sum(ranges) / len(ranges) if ranges else 0.0
    current = sum(ranges[:length]) / length
    for value in ranges[length:]:
        current = ((current * (length - 1)) + value) / length
    return current


def _number(value):
    return str(round(float(value), 8))


def _latest_confirmed_pivot(values, left, right, lookback):
    end = len(values) - right
    start = max(left, end - lookback)
    latest = None
    for index in range(start, end):
        center = float(values[index])
        left_values = values[index - left:index]
        right_values = values[index + 1:index + right + 1]
        if not left_values or not right_values:
            continue
        if center >= max(left_values) and center >= max(right_values):
            if center > max(left_values + right_values):
                latest = (center, index)
    return latest


def _close_position(symbol, side, bar_time, level):
    return order_target_percent(
        symbol,
        0.0,
        reason=(
            "CONFIRMED_PIVOT_SWEEP|intent=EXIT|direction="
            + ("LONG" if side > 0 else "SHORT")
            + "|exit=opposite_channel_close|level=" + _number(level)
            + "|bar=" + str(bar_time)
        ),
        client_order_id=(
            "confirmed-sweep-exit-" + str(symbol) + "-"
            + str(bar_time).replace(" ", "T").replace(":", "")
        ),
    )


def _open_position(
    symbol,
    direction,
    entry,
    stop,
    atr,
    level,
    pivot_index,
    sweep_depth,
    relative_volume,
    wait_bars,
    bar_time,
    target_pct,
    profit_lock_activation_r,
    profit_lock_trail_r,
    trailing_lock_profit_pct,
):
    stop_pct = abs(entry - stop) / entry if entry > 0 else 0.0
    reason = (
        "CONFIRMED_PIVOT_SWEEP|intent=ENTRY|direction="
        + ("LONG" if direction > 0 else "SHORT")
        + "|reference_entry=" + _number(entry)
        + "|stop=" + _number(stop)
        + "|target=none|reward_risk=runner"
        + "|stop_pct=" + _number(stop_pct)
        + "|atr=" + _number(atr)
        + "|pivot_level=" + _number(level)
        + "|pivot_index=" + str(pivot_index)
        + "|sweep_depth_atr=" + _number(sweep_depth)
        + "|relative_volume=" + _number(relative_volume)
        + "|confirmation_wait_bars=" + str(wait_bars)
        + "|regime=4h_ema100"
        + "|evidence=confirmed_pivot+wick_sweep+close_back_inside+next_bar_reclaim+completed_4h_regime"
        + "|profit_lock_activation_r=" + _number(profit_lock_activation_r)
        + "|profit_lock_trail_r=" + _number(profit_lock_trail_r)
        + "|trailing_lock_profit_pct=" + _number(trailing_lock_profit_pct)
        + "|bar=" + str(bar_time)
    )
    return order_target_percent(
        symbol,
        target_pct if direction > 0 else -target_pct,
        reason=reason,
        stop_loss_pct=stop_pct,
        trailing_stop_pct=stop_pct * max(0.0, profit_lock_trail_r),
        trailing_activation_pct=stop_pct * max(0.0, profit_lock_activation_r),
        trailing_lock_profit_pct=max(0.0, trailing_lock_profit_pct),
        client_order_id=(
            "confirmed-sweep-entry-" + ("long-" if direction > 0 else "short-")
            + str(symbol) + "-" + str(bar_time).replace(" ", "T").replace(":", "")
        ),
    )


def handle_data(context, data):
    exit_channel_length = max(10, int(context.params.get("exit_channel_length", 20)))
    regime_ema_length = max(50, int(context.params.get("regime_ema_length", 100)))
    atr_length = max(5, int(context.params.get("atr_length", 14)))
    pivot_left_bars = max(2, int(context.params.get("pivot_left_bars", 3)))
    pivot_right_bars = max(2, int(context.params.get("pivot_right_bars", 3)))
    pivot_lookback_bars = max(40, int(context.params.get("pivot_lookback_bars", 100)))
    max_sweep_depth_atr = max(0.25, float(context.params.get("max_sweep_depth_atr", 1.5)))
    min_wick_ratio = max(0.1, float(context.params.get("min_wick_ratio", 0.35)))
    min_relative_volume = max(0.0, float(context.params.get("min_relative_volume", 1.2)))
    confirmation_window_bars = max(1, int(context.params.get("confirmation_window_bars", 2)))
    stop_buffer_atr = max(0.0, float(context.params.get("stop_buffer_atr", 0.25)))
    max_stop_pct = max(0.02, float(context.params.get("max_stop_pct", 0.10)))
    target_pct = max(0.0, float(context.params.get("target_pct", 0.10)))
    risk_per_trade_pct = max(0.0, float(context.params.get("risk_per_trade_pct", 0.005)))
    estimated_round_trip_cost_pct = max(0.0, float(context.params.get("estimated_round_trip_cost_pct", 0.002)))
    max_target_pct = max(0.0, float(context.params.get("max_target_pct", 0.10)))
    allow_long = int(context.params.get("allow_long", 1))
    allow_short = int(context.params.get("allow_short", 1))
    profit_lock_activation_r = max(0.0, float(context.params.get("profit_lock_activation_r", 0.75)))
    profit_lock_trail_r = max(0.0, float(context.params.get("profit_lock_trail_r", 1.0)))
    trailing_lock_profit_pct = max(0.0, float(context.params.get("trailing_lock_profit_pct", 0.001)))
    leverage = max(1.0, float(context.leverage or 1.0))
    hourly_count = max(pivot_lookback_bars + pivot_right_bars + atr_length * 3, 180) + 8
    regime_count = max(regime_ema_length * 2, 140) + 8

    for symbol in UNIVERSE:
        bars = get_history(hourly_count, "1h", ["open", "high", "low", "close", "volume"], symbol)
        regime_bars = get_history(regime_count, "4h", ["open", "high", "low", "close", "volume"], symbol)
        if len(bars) < pivot_lookback_bars + pivot_right_bars + 5:
            continue
        if len(regime_bars) < regime_ema_length + 2:
            continue

        bar_time = str(bars.index[-1])
        if g.last_bar.get(symbol) == bar_time:
            continue
        g.last_bar[symbol] = bar_time
        g.sequence[symbol] = int(g.sequence.get(symbol, 0)) + 1
        sequence = g.sequence[symbol]

        opens = _values(bars, "open")
        highs = _values(bars, "high")
        lows = _values(bars, "low")
        closes = _values(bars, "close")
        volumes = _values(bars, "volume")
        entry = closes[-1]
        atr = _atr(bars, atr_length)
        if entry <= 0 or atr <= 0:
            continue

        regime_closes = _values(regime_bars, "close")
        regime_ema = _ema(regime_closes, regime_ema_length)[-1]
        regime_price = regime_closes[-1]
        long_regime = regime_price > regime_ema
        short_regime = regime_price < regime_ema

        amount = float(get_position(symbol).amount or 0.0)
        current_side = 1 if amount > 1e-12 else -1 if amount < -1e-12 else 0
        exit_high = max(highs[-exit_channel_length - 1:-1])
        exit_low = min(lows[-exit_channel_length - 1:-1])
        if current_side > 0 and entry < exit_low:
            _close_position(symbol, current_side, bar_time, exit_low)
            g.pending_sweep.pop(symbol, None)
            continue
        if current_side < 0 and entry > exit_high:
            _close_position(symbol, current_side, bar_time, exit_high)
            g.pending_sweep.pop(symbol, None)
            continue
        if current_side != 0:
            continue

        pivot_high = _latest_confirmed_pivot(highs, pivot_left_bars, pivot_right_bars, pivot_lookback_bars)
        pivot_low = _latest_confirmed_pivot(lows, pivot_left_bars, pivot_right_bars, pivot_lookback_bars)
        volume_window = volumes[-21:-1]
        average_volume = sum(volume_window) / len(volume_window) if volume_window else 0.0
        relative_volume = volumes[-1] / average_volume if average_volume > 0 else 0.0
        total_range = max(highs[-1] - lows[-1], 1e-12)
        lower_wick_ratio = (min(opens[-1], closes[-1]) - lows[-1]) / total_range
        upper_wick_ratio = (highs[-1] - max(opens[-1], closes[-1])) / total_range

        pending = g.pending_sweep.get(symbol)
        if pending is not None:
            wait_bars = sequence - int(pending["sequence"])
            direction = int(pending["direction"])
            level = float(pending["level"])
            regime_ok = long_regime if direction > 0 else short_regime
            if wait_bars > confirmation_window_bars or not regime_ok:
                g.pending_sweep.pop(symbol, None)
                pending = None
            else:
                confirmed = (
                    direction > 0
                    and closes[-1] > level
                    and closes[-1] > opens[-1]
                    and closes[-1] > float(pending["sweep_close"])
                ) or (
                    direction < 0
                    and closes[-1] < level
                    and closes[-1] < opens[-1]
                    and closes[-1] < float(pending["sweep_close"])
                )
                if confirmed:
                    sweep_extreme = float(pending["extreme"])
                    stop = sweep_extreme - stop_buffer_atr * atr if direction > 0 else sweep_extreme + stop_buffer_atr * atr
                    stop_pct = abs(entry - stop) / entry
                    if stop_pct > 0 and stop_pct <= max_stop_pct:
                        order_target_pct = target_pct
                        if risk_per_trade_pct > 0:
                            risk_distance = stop_pct + estimated_round_trip_cost_pct
                            order_target_pct = min(max_target_pct, risk_per_trade_pct / max(leverage * risk_distance, 1e-9))
                        if order_target_pct > 0:
                            _open_position(
                                symbol, direction, entry, stop, atr, level,
                                int(pending["pivot_index"]), float(pending["sweep_depth"]),
                                float(pending["relative_volume"]), wait_bars, bar_time,
                                order_target_pct, profit_lock_activation_r, profit_lock_trail_r,
                                trailing_lock_profit_pct,
                            )
                            g.pending_sweep.pop(symbol, None)
                            continue

        if pending is None and min_relative_volume > 0 and relative_volume < min_relative_volume:
            continue
        if pending is None and pivot_low is not None and allow_long > 0:
            level, pivot_index = pivot_low
            depth = (level - lows[-1]) / atr
            if lows[-1] < level and closes[-1] > level and depth <= max_sweep_depth_atr and lower_wick_ratio >= min_wick_ratio:
                g.pending_sweep[symbol] = {
                    "direction": 1, "level": level, "pivot_index": pivot_index,
                    "extreme": lows[-1], "sweep_depth": depth,
                    "relative_volume": relative_volume, "sweep_close": closes[-1],
                    "sequence": sequence,
                }
        elif pending is None and pivot_high is not None and allow_short > 0:
            level, pivot_index = pivot_high
            depth = (highs[-1] - level) / atr
            if highs[-1] > level and closes[-1] < level and depth <= max_sweep_depth_atr and upper_wick_ratio >= min_wick_ratio:
                g.pending_sweep[symbol] = {
                    "direction": -1, "level": level, "pivot_index": pivot_index,
                    "extreme": highs[-1], "sweep_depth": depth,
                    "relative_volume": relative_volume, "sweep_close": closes[-1],
                    "sequence": sequence,
                }
