"""Hourly failed-breakout reversal strategy.

A completed channel breakout arms a setup but does not immediately trade.
If price closes back through that breakout level within a bounded number of
completed bars, the failed breakout is traded in the reversal direction,
subject to the completed 4h EMA regime.  This is intentionally independent
of the immediate-breakout and breakout-retest entry families.
"""

PERSIST_RUNTIME_STATE = True

# @param channel_length int 24 range=24:96:24
# @param exit_channel_length int 20 range=10:40:10
# @param regime_ema_length int 100 range=50:200:25
# @param atr_length int 14 range=5:50:1
# @param stop_multiplier float 2.0 range=0.5:4:0.25
# @param max_stop_pct float 0.10 range=0.02:0.20:0.01
# @param target_pct float 0.10 range=0:0.50:0.01
# @param risk_per_trade_pct float 0.005 range=0:0.02:0.0005
# @param estimated_round_trip_cost_pct float 0.002 range=0:0.02:0.0005
# @param max_target_pct float 0.10 range=0.01:0.50:0.01
# @param allow_long int 1 range=0:1:1
# @param allow_short int 1 range=0:1:1
# @param failure_window_bars int 4 range=2:10:1
# @param failure_tolerance_atr float 0.0 range=0:1:0.05
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
    g.pending_breakout = {}
    context.set_universe(UNIVERSE)
    context.subscribe(frequency="1h", fields=["open", "high", "low", "close", "volume"])
    context.subscribe(frequency="4h", fields=["open", "high", "low", "close", "volume"])
    context.set_metadata(
        direction_mode="one_way",
        strategy_family="FAILED_BREAKOUT_REVERSAL",
        entry="completed_breakout_then_failed_reclaim_reversal",
        regime="completed_4h_ema100",
        exit="opposite_1h_channel_close",
        position_manager="atr_initial_stop_plus_profit_activation_trailing_lock",
    )
    context.set_warmup(220)
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


def _close_position(symbol, side, bar_time, level):
    return order_target_percent(
        symbol,
        0.0,
        reason=(
            "FAILED_BREAKOUT_REVERSAL|intent=EXIT|direction="
            + ("LONG" if side > 0 else "SHORT")
            + "|exit=opposite_channel_close|level=" + _number(level)
            + "|bar=" + str(bar_time)
        ),
        client_order_id=(
            "failed-breakout-exit-" + str(symbol) + "-"
            + str(bar_time).replace(" ", "T").replace(":", "")
        ),
    )


def _open_position(
    symbol,
    direction,
    entry,
    stop,
    atr,
    channel_length,
    bar_time,
    target_pct,
    profit_lock_activation_r,
    profit_lock_trail_r,
    trailing_lock_profit_pct,
    breakout_direction,
    breakout_level,
    wait_bars,
):
    stop_pct = abs(entry - stop) / entry if entry > 0 else 0.0
    reason = (
        "FAILED_BREAKOUT_REVERSAL|intent=ENTRY|direction="
        + ("LONG" if direction > 0 else "SHORT")
        + "|reference_entry=" + _number(entry)
        + "|stop=" + _number(stop)
        + "|target=none|reward_risk=runner"
        + "|stop_pct=" + _number(stop_pct)
        + "|atr=" + _number(atr)
        + "|channel_length=" + str(channel_length)
        + "|failed_breakout_direction=" + ("LONG" if breakout_direction > 0 else "SHORT")
        + "|breakout_level=" + _number(breakout_level)
        + "|failure_wait_bars=" + str(wait_bars)
        + "|regime=4h_ema100"
        + "|evidence=completed_breakout+failed_breakout_reversal+completed_4h_regime"
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
            "failed-breakout-entry-" + ("long-" if direction > 0 else "short-")
            + str(symbol) + "-" + str(bar_time).replace(" ", "T").replace(":", "")
        ),
    )


def handle_data(context, data):
    channel_length = max(24, int(context.params.get("channel_length", 24)))
    exit_channel_length = max(10, int(context.params.get("exit_channel_length", 20)))
    regime_ema_length = max(50, int(context.params.get("regime_ema_length", 100)))
    atr_length = max(5, int(context.params.get("atr_length", 14)))
    stop_multiplier = max(0.5, float(context.params.get("stop_multiplier", 2.0)))
    max_stop_pct = max(0.02, float(context.params.get("max_stop_pct", 0.10)))
    target_pct = max(0.0, float(context.params.get("target_pct", 0.10)))
    risk_per_trade_pct = max(0.0, float(context.params.get("risk_per_trade_pct", 0.005)))
    estimated_round_trip_cost_pct = max(0.0, float(context.params.get("estimated_round_trip_cost_pct", 0.002)))
    max_target_pct = max(0.0, float(context.params.get("max_target_pct", 0.10)))
    allow_long = int(context.params.get("allow_long", 1))
    allow_short = int(context.params.get("allow_short", 1))
    failure_window_bars = max(2, int(context.params.get("failure_window_bars", 4)))
    failure_tolerance_atr = max(0.0, float(context.params.get("failure_tolerance_atr", 0.0)))
    profit_lock_activation_r = max(0.0, float(context.params.get("profit_lock_activation_r", 0.75)))
    profit_lock_trail_r = max(0.0, float(context.params.get("profit_lock_trail_r", 1.0)))
    trailing_lock_profit_pct = max(0.0, float(context.params.get("trailing_lock_profit_pct", 0.001)))
    leverage = max(1.0, float(context.leverage or 1.0))
    hourly_count = max(channel_length + exit_channel_length + atr_length * 3, 120) + 8
    regime_count = max(regime_ema_length * 2, 140) + 8

    for symbol in UNIVERSE:
        bars = get_history(hourly_count, "1h", ["open", "high", "low", "close", "volume"], symbol)
        regime_bars = get_history(regime_count, "4h", ["open", "high", "low", "close", "volume"], symbol)
        if len(bars) < channel_length + exit_channel_length + atr_length + 4:
            continue
        if len(regime_bars) < regime_ema_length + 2:
            continue

        bar_time = str(bars.index[-1])
        if g.last_bar.get(symbol) == bar_time:
            continue
        g.last_bar[symbol] = bar_time
        g.sequence[symbol] = int(g.sequence.get(symbol, 0)) + 1
        sequence = g.sequence[symbol]

        closes = _values(bars, "close")
        highs = _values(bars, "high")
        lows = _values(bars, "low")
        opens = _values(bars, "open")
        entry = closes[-1]
        previous_close = closes[-2]
        atr = _atr(bars, atr_length)
        if entry <= 0 or atr <= 0:
            continue

        prior_high = max(highs[-channel_length - 1:-1])
        prior_low = min(lows[-channel_length - 1:-1])
        earlier_high = max(highs[-channel_length - 2:-2])
        earlier_low = min(lows[-channel_length - 2:-2])
        upside_breakout = allow_short > 0 and entry > prior_high and previous_close <= earlier_high
        downside_breakout = allow_long > 0 and entry < prior_low and previous_close >= earlier_low

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
            g.pending_breakout.pop(symbol, None)
            continue
        if current_side < 0 and entry > exit_high:
            _close_position(symbol, current_side, bar_time, exit_high)
            g.pending_breakout.pop(symbol, None)
            continue
        if current_side != 0:
            continue

        pending = g.pending_breakout.get(symbol)
        if pending is not None:
            wait_bars = sequence - int(pending["sequence"])
            breakout_direction = int(pending["direction"])
            level = float(pending["level"])
            reversal_direction = -breakout_direction
            regime_ok = long_regime if reversal_direction > 0 else short_regime
            if wait_bars > failure_window_bars or not regime_ok:
                g.pending_breakout.pop(symbol, None)
                pending = None
            else:
                failed = False
                if breakout_direction > 0:
                    failed = entry < level - failure_tolerance_atr * atr and entry < opens[-1]
                else:
                    failed = entry > level + failure_tolerance_atr * atr and entry > opens[-1]
                if failed:
                    stop = entry - stop_multiplier * atr if reversal_direction > 0 else entry + stop_multiplier * atr
                    stop_pct = abs(entry - stop) / entry
                    if stop_pct > 0 and stop_pct <= max_stop_pct:
                        order_target_pct = target_pct
                        if risk_per_trade_pct > 0:
                            risk_distance = stop_pct + estimated_round_trip_cost_pct
                            order_target_pct = min(max_target_pct, risk_per_trade_pct / max(leverage * risk_distance, 1e-9))
                        if order_target_pct > 0:
                            _open_position(
                                symbol, reversal_direction, entry, stop, atr, channel_length, bar_time,
                                order_target_pct, profit_lock_activation_r, profit_lock_trail_r,
                                trailing_lock_profit_pct, breakout_direction, level, wait_bars,
                            )
                            g.pending_breakout.pop(symbol, None)
                            continue

        if pending is None and upside_breakout:
            g.pending_breakout[symbol] = {"direction": 1, "level": prior_high, "sequence": sequence}
        elif pending is None and downside_breakout:
            g.pending_breakout[symbol] = {"direction": -1, "level": prior_low, "sequence": sequence}
