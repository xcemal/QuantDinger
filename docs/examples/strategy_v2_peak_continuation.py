"""Native Strategy API V2 example: multi-signal peak capture and continuation.

This is intentionally a separate strategy from TREND_FLIP.  It combines three
independent entry families (trend pullback/reclaim, volatility breakout and a
confirmed sweep/absorption proxy) with one deterministic position manager:

* initial hard stop
* ATR-normalized trailing stop activated after a favorable R move
* no fixed take-profit, so a runner can continue
* bounded same-direction re-entry after a profitable trailing exit

Jev remains an entry/re-entry gate in live execution.  Protective exits do not
wait for Jev.
"""

import math


PERSIST_RUNTIME_STATE = True

# @param fast_ema_length int 20 range=5:50:1
# @param slow_ema_length int 50 range=20:200:5
# @param adx_length int 14 range=5:40:1
# @param adx_min float 25 range=5:50:1
# @param atr_length int 14 range=5:50:1
# @param stop_multiplier float 2.0 range=0.5:6:0.25
# @param activation_r float 1.0 range=0.25:4:0.25
# @param trail_multiplier float 1.25 range=0.5:4:0.25
# @param trailing_lock_profit_pct float 0.0015 range=0:0.01:0.0005
# @param max_stop_pct float 0.04 range=0.005:0.15:0.005
# @param max_trail_pct float 0.05 range=0.005:0.15:0.005
# @param breakout_lookback int 12 range=4:50:1
# @param breakout_atr_buffer float 0.2 range=0.05:2:0.05
# @param pullback_window int 3 range=2:10:1
# @param min_pullback_depth_atr float 0.50 range=0:2:0.05
# @param max_entry_extension_atr float 0.25 range=0.25:4:0.25
# @param max_entry_atr_pct float 0.012 range=0:0.1:0.001
# @param reclaim_buffer_atr float 0.10 range=0:1:0.05
# @param min_body_atr float 0.25 range=0.05:2:0.05
# @param pivot_length int 3 range=2:10:1
# @param rvol_lookback int 20 range=5:100:1
# @param min_relative_volume float 1.5 range=1:5:0.1
# @param min_sweep_depth_atr float 0.15 range=0.05:2:0.05
# @param take_profit_r float 0 range=0:5:0.25
# @param target_pct float 0.025 range=0.02:0.5:0.005
# @param max_open_positions int 1 range=1:24:1
# @param cooldown_bars int 2 range=1:12:1
# @param max_reentries int 1 range=0:3:1
# @param use_pullback int 1 range=0:1:1
# @param use_breakout int 0 range=0:1:1
# @param use_rapid_accel int 0 range=0:1:1
# @param use_sweep_absorption int 0 range=0:1:1
# @param use_htf_filter int 1 range=0:1:1
# @param htf_fast_length int 20 range=5:50:1
# @param htf_slow_length int 50 range=20:200:5
# @param use_market_regime_filter int 1 range=0:1:1
# @param block_after_stop_until_market_flip int 0 range=0:1:1
# @param use_structure_hold int 1 range=0:1:1
# @param max_pullback_beyond_slow_atr float 0.25 range=0:2:0.05
# @param use_volume_confirmation int 0 range=0:1:1
# @param use_candle_confirmation int 1 range=0:1:1
# @param use_donchian_retest int 0 range=0:1:1
# @param donchian_length int 20 range=5:100:1
# @param donchian_retest_bars int 4 range=1:10:1
# @param donchian_breakout_buffer_atr float 0.1 range=0:2:0.05
# @param donchian_retest_tolerance_atr float 0.2 range=0:2:0.05
# @param donchian_reclaim_buffer_atr float 0.05 range=0:1:0.05
# @param donchian_max_extension_atr float 0.75 range=0.25:4:0.25
# @param donchian_min_body_atr float 0.5 range=0.05:2:0.05
# @param donchian_min_relative_volume float 1.2 range=1:5:0.1
# @param use_vwap_reclaim int 0 range=0:1:1
# @param vwap_length int 48 range=12:200:1
# @param vwap_touch_atr float 0.15 range=0:2:0.05
# @param vwap_reclaim_buffer_atr float 0.1 range=0:1:0.05
# @param vwap_min_range_atr float 0.8 range=0.1:4:0.1
# @param vwap_min_relative_volume float 1.5 range=1:5:0.1
# @param universe_limit int 25 range=1:25:1


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
    g.last_action_bar = {}
    g.cooldown = {}
    g.reentry_count = {}
    g.position_side = {}
    g.peak_price = {}
    g.last_exit_side = {}
    g.last_exit_peak = {}
    g.last_exit_reason = {}
    g.last_exit_bar = {}
    g.last_setup_id = {}
    g.loss_block_market_direction = {}
    g.pending_entry = {}
    g.pending_entry_side = {}
    g.pending_entry_reentry = {}
    context.set_universe(UNIVERSE)
    context.subscribe(frequency="5m", fields=["open", "high", "low", "close", "volume"])
    # This is an independently loaded, completed-bar-only regime filter.  It
    # is declared even when disabled so backtest/live parameter overrides do
    # not change the compiled contract.
    context.subscribe(frequency="1h", fields=["open", "high", "low", "close", "volume"])
    context.set_metadata(
        direction_mode="one_way",
        strategy_family="PEAK_CONTINUATION",
        signal_families="TREND_PULLBACK+BREAKOUT+RAPID_ACCEL+SWEEP_ABSORPTION",
        position_manager="ATR_HWM_TRAILING_WITH_BOUNDED_REENTRY",
    )
    context.set_warmup(240)
    context.allow_leverage(max_leverage=5)


def _column(bars, name):
    return [float(value) for value in bars[name].to_numpy()]


def _true_ranges(bars):
    highs = _column(bars, "high")
    lows = _column(bars, "low")
    closes = _column(bars, "close")
    values = []
    for index in range(1, len(closes)):
        high = highs[index]
        low = lows[index]
        previous_close = closes[index - 1]
        values.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
    return values


def _atr(bars, length):
    values = _true_ranges(bars)
    length = max(1, int(length))
    if not values:
        return 0.0
    if len(values) <= length:
        return sum(values) / len(values)
    current = sum(values[:length]) / length
    for value in values[length:]:
        current = ((current * (length - 1)) + value) / length
    return current


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


def _adx(bars, length):
    length = max(2, int(length))
    if len(bars) < length * 2 + 2:
        return 0.0
    highs = _column(bars, "high")
    lows = _column(bars, "low")
    closes = _column(bars, "close")
    true_ranges = []
    plus_moves = []
    minus_moves = []
    for index in range(1, len(bars)):
        high = highs[index]
        low = lows[index]
        previous_high = highs[index - 1]
        previous_low = lows[index - 1]
        previous_close = closes[index - 1]
        true_ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
        up = high - previous_high
        down = previous_low - low
        plus_moves.append(up if up > down and up > 0 else 0.0)
        minus_moves.append(down if down > up and down > 0 else 0.0)
    if len(true_ranges) < length:
        return 0.0
    smooth_tr = sum(true_ranges[:length])
    smooth_plus = sum(plus_moves[:length])
    smooth_minus = sum(minus_moves[:length])
    dx_values = []
    for index in range(length - 1, len(true_ranges)):
        if index >= length:
            smooth_tr = smooth_tr - (smooth_tr / length) + true_ranges[index]
            smooth_plus = smooth_plus - (smooth_plus / length) + plus_moves[index]
            smooth_minus = smooth_minus - (smooth_minus / length) + minus_moves[index]
        if smooth_tr <= 0:
            continue
        plus_di = 100.0 * smooth_plus / smooth_tr
        minus_di = 100.0 * smooth_minus / smooth_tr
        denominator = plus_di + minus_di
        dx_values.append(100.0 * abs(plus_di - minus_di) / denominator if denominator > 0 else 0.0)
    if not dx_values:
        return 0.0
    if len(dx_values) <= length:
        return sum(dx_values) / len(dx_values)
    current = sum(dx_values[:length]) / length
    for value in dx_values[length:]:
        current = ((current * (length - 1)) + value) / length
    return current


def _trend_direction(bars, fast_length, slow_length):
    closes = _column(bars, "close")
    fast = _ema(closes, fast_length)
    slow = _ema(closes, slow_length)
    if len(fast) < 6 or len(slow) < 6:
        return 0, fast, slow
    if fast[-1] > slow[-1] and slow[-1] > slow[-6] and closes[-1] > fast[-1]:
        return 1, fast, slow
    if fast[-1] < slow[-1] and slow[-1] < slow[-6] and closes[-1] < fast[-1]:
        return -1, fast, slow
    return 0, fast, slow


def _relative_volume(bars, lookback):
    lookback = max(2, int(lookback))
    if len(bars) < lookback + 1:
        return 0.0
    volumes = _column(bars, "volume")
    baseline_values = volumes[-lookback - 1:-1]
    baseline = sum(baseline_values) / len(baseline_values) if baseline_values else 0.0
    current = volumes[-1]
    return current / baseline if baseline > 0 else 0.0


def _rolling_vwap(bars, length):
    length = max(2, int(length))
    highs = _column(bars, "high")
    lows = _column(bars, "low")
    closes = _column(bars, "close")
    volumes = _column(bars, "volume")

    def value_at(end_index):
        start = max(0, end_index - length + 1)
        weighted = 0.0
        volume_sum = 0.0
        for index in range(start, end_index + 1):
            typical = (highs[index] + lows[index] + closes[index]) / 3.0
            weighted += typical * volumes[index]
            volume_sum += volumes[index]
        return weighted / volume_sum if volume_sum > 0 else closes[end_index]

    if len(bars) < length + 2:
        return 0.0, 0.0
    return value_at(len(bars) - 2), value_at(len(bars) - 1)


def _confirmed_pivot(bars, length, direction):
    length = max(2, int(length))
    latest = len(bars) - length - 1
    if latest < length:
        return None
    values = _column(bars, "high" if direction > 0 else "low")
    for index in reversed(range(length, latest + 1)):
        left = index - length
        right = index + length + 1
        if direction > 0:
            value = values[index]
            if value >= max(values[left:right]):
                return value, str(bars.index[index])
        else:
            value = values[index]
            if value <= min(values[left:right]):
                return value, str(bars.index[index])
    return None


def _rejection(bars, direction):
    high = _column(bars, "high")[-1]
    low = _column(bars, "low")[-1]
    close = _column(bars, "close")[-1]
    span = high - low
    if span <= 0:
        return False
    location = (close - low) / span
    return location >= 0.6 if direction > 0 else location <= 0.4


def _body_acceleration(bars, direction, atr, minimum_body_atr):
    if len(bars) < 4 or atr <= 0:
        return False, 0.0
    opens = _column(bars, "open")
    closes = _column(bars, "close")
    bodies = []
    colors = []
    for index in range(len(bars) - 4, len(bars)):
        open_ = opens[index]
        close = closes[index]
        bodies.append(abs(close - open_))
        colors.append(1 if close > open_ else -1)
    if any(color != direction for color in colors[-3:]):
        return False, 0.0
    if not (bodies[-3] > bodies[-4] and bodies[-2] > bodies[-3] and bodies[-1] > bodies[-2]):
        return False, 0.0
    ratio = bodies[-1] / max(bodies[-2], 1e-12)
    return bodies[-1] >= atr * minimum_body_atr, ratio


def _candidate(bars, params, htf_bars=None, market_bars=None):
    atr = _atr(bars, params["atr_length"])
    if atr <= 0:
        return None
    highs = _column(bars, "high")
    lows = _column(bars, "low")
    closes = _column(bars, "close")
    entry = closes[-1]
    if entry <= 0:
        return None
    trend, fast, slow = _trend_direction(
        bars,
        params["fast_ema_length"],
        params["slow_ema_length"],
    )
    adx = _adx(bars, params["adx_length"])
    if adx < params["adx_min"]:
        return None
    htf_direction = 0
    if params["use_htf_filter"]:
        if htf_bars is None or len(htf_bars) < params["htf_slow_length"] + 8:
            return None
        htf_direction, _, _ = _trend_direction(
            htf_bars,
            params["htf_fast_length"],
            params["htf_slow_length"],
        )
        if not htf_direction or (trend and htf_direction != trend):
            return None
    market_direction = 0
    if params["use_market_regime_filter"]:
        if market_bars is None or len(market_bars) < params["htf_slow_length"] + 8:
            return None
        market_direction, _, _ = _trend_direction(
            market_bars,
            params["htf_fast_length"],
            params["htf_slow_length"],
        )
        if not market_direction or (trend and market_direction != trend):
            return None
    rvol = _relative_volume(bars, params["rvol_lookback"])
    body = abs(float(_column(bars, "close")[-1]) - float(_column(bars, "open")[-1]))
    candle_span = max(highs[-1] - lows[-1], 1e-12)
    close_location = (entry - lows[-1]) / candle_span
    confirmation_ok = True
    if params["use_volume_confirmation"]:
        confirmation_ok = confirmation_ok and rvol >= params["min_relative_volume"]
    if params["use_candle_confirmation"]:
        confirmation_ok = confirmation_ok and body >= params["min_body_atr"] * atr
        confirmation_ok = confirmation_ok and (
            (trend > 0 and close_location >= 0.65)
            or (trend < 0 and close_location <= 0.35)
        )
    if not confirmation_ok:
        return None
    atr_pct = atr / entry
    max_entry_atr_pct = float(params.get("max_entry_atr_pct", 0.0) or 0.0)
    if max_entry_atr_pct > 0 and atr_pct > max_entry_atr_pct:
        return None
    candidates = []

    # 1) Trend pullback/reclaim: entry is not tied to a direction flip.
    window = max(2, params["pullback_window"])
    if params["use_pullback"] and trend and len(bars) > window + 2:
        previous_high = highs[-2]
        previous_low = lows[-2]
        recent_lows = lows[-window - 1:-1]
        recent_highs = highs[-window - 1:-1]
        pullback_depth = (
            (fast[-1] - min(recent_lows)) / atr
            if trend > 0 and recent_lows else
            (max(recent_highs) - fast[-1]) / atr
            if trend < 0 and recent_highs else 0.0
        )
        not_extended = (
            entry <= fast[-1] + params["max_entry_extension_atr"] * atr
            if trend > 0 else
            entry >= fast[-1] - params["max_entry_extension_atr"] * atr
        )
        touched = any(
            lows[index] <= fast[index]
            for index in range(len(bars) - window - 1, len(bars) - 1)
        ) if trend > 0 else any(
            highs[index] >= fast[index]
            for index in range(len(bars) - window - 1, len(bars) - 1)
        )
        reclaimed = (
            entry > previous_high + params["reclaim_buffer_atr"] * atr
            if trend > 0 else
            entry < previous_low - params["reclaim_buffer_atr"] * atr
        )
        structure_hold = True
        if params["use_structure_hold"]:
            structure_hold = (
                min(recent_lows) >= slow[-1] - params["max_pullback_beyond_slow_atr"] * atr
                if trend > 0 else
                max(recent_highs) <= slow[-1] + params["max_pullback_beyond_slow_atr"] * atr
            )
        if touched and reclaimed and pullback_depth >= params["min_pullback_depth_atr"] and not_extended and structure_hold:
            evidence = "ema_trend+controlled_pullback+reclaim"
            if params["use_htf_filter"]:
                evidence += "+htf_bias=" + ("LONG" if htf_direction > 0 else "SHORT")
            if params["use_market_regime_filter"]:
                evidence += "+market_bias=" + ("LONG" if market_direction > 0 else "SHORT")
            if params["use_structure_hold"]:
                evidence += "+structure_hold"
            if params["use_volume_confirmation"]:
                evidence += "+rvol=" + _number(rvol)
            if params["use_candle_confirmation"]:
                evidence += "+body_atr=" + _number(body / atr) + "+close_location=" + _number(close_location)
            candidates.append((4, trend, "PULLBACK_RECLAIM", evidence, "pullback|" + str(bars.index[-1])))

    # 2) Donchian breakout followed by a bounded retest/reclaim.  The
    # breakout channel is strictly pre-breakout and the signal is emitted on
    # the later completed retest bar, so neither the channel nor the trigger
    # uses future rows.
    if params["use_donchian_retest"] and trend:
        channel_length = max(5, params["donchian_length"])
        max_retest_bars = max(1, params["donchian_retest_bars"])
        first_breakout = max(channel_length, len(bars) - max_retest_bars - 1)
        last_breakout = len(bars) - 2
        for breakout_index in reversed(range(first_breakout, last_breakout + 1)):
            channel_start = breakout_index - channel_length
            if channel_start < 0:
                continue
            channel_high = max(highs[channel_start:breakout_index])
            channel_low = min(lows[channel_start:breakout_index])
            breakout_close = closes[breakout_index]
            if trend > 0:
                breakout_ok = breakout_close > channel_high + params["donchian_breakout_buffer_atr"] * atr
                level = channel_high
                retest_ok = (
                    lows[-1] <= level + params["donchian_retest_tolerance_atr"] * atr
                    and entry > level + params["donchian_reclaim_buffer_atr"] * atr
                    and entry <= level + params["donchian_max_extension_atr"] * atr
                )
            else:
                breakout_ok = breakout_close < channel_low - params["donchian_breakout_buffer_atr"] * atr
                level = channel_low
                retest_ok = (
                    highs[-1] >= level - params["donchian_retest_tolerance_atr"] * atr
                    and entry < level - params["donchian_reclaim_buffer_atr"] * atr
                    and entry >= level - params["donchian_max_extension_atr"] * atr
                )
            bars_since_breakout = len(bars) - 1 - breakout_index
            breakout_body = abs(closes[breakout_index] - _column(bars, "open")[breakout_index])
            if (
                breakout_ok
                and 1 <= bars_since_breakout <= max_retest_bars
                and retest_ok
                and breakout_body >= params["donchian_min_body_atr"] * atr
                and rvol >= params["donchian_min_relative_volume"]
            ):
                candidates.append((4, trend, "DONCHIAN_RETEST", "ema_trend+donchian_breakout_retest+level=" + _number(level) + "+bars_since_breakout=" + str(bars_since_breakout) + "+rvol=" + _number(rvol), "donchian|" + str(bars.index[breakout_index]) + "|" + ("LONG" if trend > 0 else "SHORT")))
                break

    # 3) Rolling VWAP reclaim with range and volume expansion.  Rolling VWAP
    # avoids session-boundary ambiguity for 24/7 crypto while retaining a
    # completed-bar-only reclaim event.
    if params["use_vwap_reclaim"] and trend:
        previous_vwap, current_vwap = _rolling_vwap(bars, params["vwap_length"])
        current_range = highs[-1] - lows[-1]
        vwap_rvol = _relative_volume(bars, params["rvol_lookback"])
        if previous_vwap > 0 and current_vwap > 0:
            previous_close = closes[-2]
            vwap_long = (
                trend > 0
                and previous_close <= previous_vwap + params["vwap_touch_atr"] * atr
                and entry > current_vwap + params["vwap_reclaim_buffer_atr"] * atr
                and current_vwap >= previous_vwap
                and current_range >= params["vwap_min_range_atr"] * atr
                and vwap_rvol >= params["vwap_min_relative_volume"]
                and close_location >= 0.70
            )
            vwap_short = (
                trend < 0
                and previous_close >= previous_vwap - params["vwap_touch_atr"] * atr
                and entry < current_vwap - params["vwap_reclaim_buffer_atr"] * atr
                and current_vwap <= previous_vwap
                and current_range >= params["vwap_min_range_atr"] * atr
                and vwap_rvol >= params["vwap_min_relative_volume"]
                and close_location <= 0.30
            )
            if vwap_long or vwap_short:
                direction = 1 if vwap_long else -1
                candidates.append((4, direction, "VWAP_RECLAIM", "ema_trend+rolling_vwap_reclaim+range_atr=" + _number(current_range / atr) + "+rvol=" + _number(vwap_rvol), "vwap|" + str(bars.index[-1]) + "|" + ("LONG" if direction > 0 else "SHORT")))

    # 4) New extreme breakout continuation.
    lookback = max(3, params["breakout_lookback"])
    if params["use_breakout"] and trend and len(bars) > lookback + 2:
        prior_high = max(highs[-lookback - 1:-1])
        prior_low = min(lows[-lookback - 1:-1])
        if trend > 0 and entry > prior_high + params["breakout_atr_buffer"] * atr:
            candidates.append((3, 1, "BREAKOUT_CONTINUATION", "ema_trend+range_extreme_break", "breakout|" + str(bars.index[-1])))
        if trend < 0 and entry < prior_low - params["breakout_atr_buffer"] * atr:
            candidates.append((3, -1, "BREAKOUT_CONTINUATION", "ema_trend+range_extreme_break", "breakout|" + str(bars.index[-1])))

    # 5) Acceleration, but only in an established directional regime.
    if params["use_rapid_accel"] and trend:
        accelerated, ratio = _body_acceleration(
            bars,
            trend,
            atr,
            params["min_body_atr"],
        )
        if accelerated:
            candidates.append((2, trend, "RAPID_ACCEL", "ema_trend+three_bar_body_acceleration+body_ratio=" + _number(ratio), "rapid|" + str(bars.index[-1])))

    # 6) Confirmed pivot sweep/reclaim.  This is OHLCV evidence, not order flow.
    if params["use_sweep_absorption"] and rvol >= params["min_relative_volume"]:
        high_pivot = _confirmed_pivot(bars, params["pivot_length"], 1)
        low_pivot = _confirmed_pivot(bars, params["pivot_length"], -1)
        high = highs[-1]
        low = lows[-1]
        if high_pivot is not None:
            pivot = high_pivot[0]
            depth = (high - pivot) / atr
            if high > pivot and entry < pivot and depth >= params["min_sweep_depth_atr"] and _rejection(bars, -1):
                if trend in {0, -1}:
                    candidates.append((3, -1, "SWEEP_ABSORPTION", "confirmed_high_pivot+sweep_reclaim+rvol=" + _number(rvol), "sweep|high|" + str(high_pivot[1])) )
        if low_pivot is not None:
            pivot = low_pivot[0]
            depth = (pivot - low) / atr
            if low < pivot and entry > pivot and depth >= params["min_sweep_depth_atr"] and _rejection(bars, 1):
                if trend in {0, 1}:
                    candidates.append((3, 1, "SWEEP_ABSORPTION", "confirmed_low_pivot+sweep_reclaim+rvol=" + _number(rvol), "sweep|low|" + str(low_pivot[1])))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    score, direction, mode, evidence, setup_id = candidates[0]
    stop_pct = min(params["max_stop_pct"], max(0.0001, params["stop_multiplier"] * atr_pct))
    activation_pct = stop_pct * params["activation_r"]
    trail_pct = min(params["max_trail_pct"], max(0.0001, params["trail_multiplier"] * atr_pct))
    stop = entry * (1.0 - stop_pct) if direction > 0 else entry * (1.0 + stop_pct)
    return {
        "direction": direction,
        "mode": mode,
        "evidence": evidence,
        "score": score,
        "entry": entry,
        "stop": stop,
        "atr": atr,
        "atr_pct": atr_pct,
        "adx": adx,
        "stop_pct": stop_pct,
        "activation_pct": activation_pct,
        "trail_pct": trail_pct,
        "htf_direction": htf_direction,
        "market_direction": market_direction,
        "relative_volume": rvol,
        "body_atr": body / atr,
        "close_location": close_location,
        "setup_id": setup_id,
    }


def _number(value):
    return str(round(float(value), 8))


def _active_position_count(symbols=None):
    count = 0
    for symbol in symbols or UNIVERSE:
        try:
            if abs(float(get_position(symbol).amount or 0.0)) > 1e-12:
                count += 1
        except Exception:
            continue
    return count


def _is_profitable_exit(reason):
    return str(reason or "").strip().lower() in {"trailing_stop", "take_profit"}


def _is_working_status(status):
    return str(status or "").strip().lower() in {
        "unknown", "queued", "deferred", "submitted", "open", "partial",
    }


def _is_terminal_failure(status):
    return str(status or "").strip().lower() in {
        "rejected", "failed", "cancelled", "canceled", "expired",
    }


def _trade(symbol, candidate, bar_time, is_reentry, target_pct, take_profit_r, trailing_lock_profit_pct):
    direction = int(candidate["direction"])
    side = "long" if direction > 0 else "short"
    mode = str(candidate["mode"])
    suffix = "reentry" if is_reentry else "entry"
    take_profit_pct = min(5.0, max(0.0, candidate["stop_pct"] * max(0.0, take_profit_r)))
    reason = (
        "PEAK_CONTINUATION"
        + "|intent=" + suffix
        + "|mode=" + mode
        + "|direction=" + ("LONG" if direction > 0 else "SHORT")
        + "|reference_entry=" + _number(candidate["entry"])
        + "|stop=" + _number(candidate["stop"])
        + "|target=" + ("none" if take_profit_pct <= 0 else _number(take_profit_pct))
        + "|reward_risk=" + ("runner" if take_profit_pct <= 0 else _number(take_profit_r))
        + "|stop_pct=" + _number(candidate["stop_pct"])
        + "|trail_pct=" + _number(candidate["trail_pct"])
        + "|activation_pct=" + _number(candidate["activation_pct"])
        + "|trailing_lock_profit_pct=" + _number(trailing_lock_profit_pct)
        + "|atr_pct=" + _number(candidate["atr_pct"])
        + "|adx=" + _number(candidate["adx"])
        + "|score=" + str(candidate["score"])
        + "|evidence=" + candidate["evidence"]
        + "|bar=" + str(bar_time)
    )
    client_id = "peak-continuation-" + suffix + "-" + side + "-" + str(symbol) + "-" + str(bar_time).replace(" ", "T").replace(":", "")
    return order_target_percent(
        symbol,
        target_pct if direction > 0 else -target_pct,
        reason=reason,
        stop_loss_pct=candidate["stop_pct"],
        take_profit_pct=take_profit_pct,
        trailing_stop_pct=candidate["trail_pct"],
        trailing_activation_pct=candidate["activation_pct"],
        trailing_lock_profit_pct=trailing_lock_profit_pct,
        client_order_id=client_id,
    )


def handle_data(context, data):
    params = {
        "fast_ema_length": int(context.params.get("fast_ema_length", 20)),
        "slow_ema_length": int(context.params.get("slow_ema_length", 50)),
        "adx_length": int(context.params.get("adx_length", 14)),
        "adx_min": float(context.params.get("adx_min", 25.0)),
        "atr_length": int(context.params.get("atr_length", 14)),
        "stop_multiplier": float(context.params.get("stop_multiplier", 2.0)),
        "activation_r": float(context.params.get("activation_r", 1.0)),
        "trail_multiplier": float(context.params.get("trail_multiplier", 1.25)),
        "max_stop_pct": float(context.params.get("max_stop_pct", 0.04)),
        "max_trail_pct": float(context.params.get("max_trail_pct", 0.05)),
        "breakout_lookback": int(context.params.get("breakout_lookback", 12)),
        "breakout_atr_buffer": float(context.params.get("breakout_atr_buffer", 0.2)),
        "pullback_window": int(context.params.get("pullback_window", 3)),
        "min_pullback_depth_atr": float(context.params.get("min_pullback_depth_atr", 0.50)),
        "max_entry_extension_atr": float(context.params.get("max_entry_extension_atr", 0.25)),
        "max_entry_atr_pct": float(context.params.get("max_entry_atr_pct", 0.012)),
        "reclaim_buffer_atr": float(context.params.get("reclaim_buffer_atr", 0.10)),
        "min_body_atr": float(context.params.get("min_body_atr", 0.25)),
        "pivot_length": int(context.params.get("pivot_length", 3)),
        "rvol_lookback": int(context.params.get("rvol_lookback", 20)),
        "min_relative_volume": float(context.params.get("min_relative_volume", 1.5)),
        "min_sweep_depth_atr": float(context.params.get("min_sweep_depth_atr", 0.15)),
        "use_pullback": int(context.params.get("use_pullback", 1)),
        "use_breakout": int(context.params.get("use_breakout", 0)),
        "use_rapid_accel": int(context.params.get("use_rapid_accel", 0)),
        "use_sweep_absorption": int(context.params.get("use_sweep_absorption", 0)),
        "use_htf_filter": int(context.params.get("use_htf_filter", 1)),
        "htf_fast_length": int(context.params.get("htf_fast_length", 20)),
        "htf_slow_length": int(context.params.get("htf_slow_length", 50)),
        "use_market_regime_filter": int(context.params.get("use_market_regime_filter", 1)),
        "block_after_stop_until_market_flip": int(context.params.get("block_after_stop_until_market_flip", 0)),
        "use_structure_hold": int(context.params.get("use_structure_hold", 1)),
        "max_pullback_beyond_slow_atr": float(context.params.get("max_pullback_beyond_slow_atr", 0.25)),
        "use_volume_confirmation": int(context.params.get("use_volume_confirmation", 0)),
        "use_candle_confirmation": int(context.params.get("use_candle_confirmation", 1)),
        "use_donchian_retest": int(context.params.get("use_donchian_retest", 0)),
        "donchian_length": int(context.params.get("donchian_length", 20)),
        "donchian_retest_bars": int(context.params.get("donchian_retest_bars", 4)),
        "donchian_breakout_buffer_atr": float(context.params.get("donchian_breakout_buffer_atr", 0.1)),
        "donchian_retest_tolerance_atr": float(context.params.get("donchian_retest_tolerance_atr", 0.2)),
        "donchian_reclaim_buffer_atr": float(context.params.get("donchian_reclaim_buffer_atr", 0.05)),
        "donchian_max_extension_atr": float(context.params.get("donchian_max_extension_atr", 0.75)),
        "donchian_min_body_atr": float(context.params.get("donchian_min_body_atr", 0.5)),
        "donchian_min_relative_volume": float(context.params.get("donchian_min_relative_volume", 1.2)),
        "use_vwap_reclaim": int(context.params.get("use_vwap_reclaim", 0)),
        "vwap_length": int(context.params.get("vwap_length", 48)),
        "vwap_touch_atr": float(context.params.get("vwap_touch_atr", 0.15)),
        "vwap_reclaim_buffer_atr": float(context.params.get("vwap_reclaim_buffer_atr", 0.1)),
        "vwap_min_range_atr": float(context.params.get("vwap_min_range_atr", 0.8)),
        "vwap_min_relative_volume": float(context.params.get("vwap_min_relative_volume", 1.5)),
    }
    target_pct = float(context.params.get("target_pct", 0.025))
    take_profit_r = float(context.params.get("take_profit_r", 0.0))
    trailing_lock_profit_pct = max(
        0.0,
        float(context.params.get("trailing_lock_profit_pct", 0.0015)),
    )
    max_open_positions = max(1, int(context.params.get("max_open_positions", 1)))
    cooldown_bars = max(1, int(context.params.get("cooldown_bars", 2)))
    max_reentries = max(0, int(context.params.get("max_reentries", 1)))
    universe_limit = min(len(UNIVERSE), max(1, int(context.params.get("universe_limit", len(UNIVERSE)))))
    active_universe = UNIVERSE[:universe_limit]
    count = max(params["slow_ema_length"] * 3, params["rvol_lookback"] + 20, 120) + 8
    htf_count = max(params["htf_slow_length"] * 3, 120) + 8
    market_bars = None
    if params["use_market_regime_filter"]:
        market_bars = get_history(htf_count, "1h", ["open", "high", "low", "close", "volume"], UNIVERSE[0])
    market_direction = 0
    if market_bars is not None and len(market_bars) >= params["htf_slow_length"] + 8:
        market_direction, _, _ = _trend_direction(
            market_bars,
            params["htf_fast_length"],
            params["htf_slow_length"],
        )

    filled_slots = 0
    reserved_slots = 0
    for reserved_symbol in active_universe:
        reserved_ref = g.pending_entry.get(reserved_symbol)
        reserved_status = get_order_status(reserved_ref).get("status") if reserved_ref else ""
        if _is_working_status(reserved_status):
            reserved_slots += 1
        try:
            if abs(float(get_position(reserved_symbol).amount or 0.0)) > 1e-12:
                filled_slots += 1
        except Exception:
            continue

    for symbol in active_universe:
        bars = get_history(count, "5m", ["open", "high", "low", "close", "volume"], symbol)
        if len(bars) < max(params["slow_ema_length"] + 8, params["atr_length"] + 8, 40):
            continue
        htf_bars = None
        if params["use_htf_filter"]:
            htf_bars = get_history(htf_count, "1h", ["open", "high", "low", "close", "volume"], symbol)
        bar_time = str(bars.index[-1])
        amount = float(get_position(symbol).amount or 0.0)
        current_side = 1 if amount > 1e-12 else -1 if amount < -1e-12 else 0
        previous_side = int(g.position_side.get(symbol, 0))
        exit_reason = consume_last_exit_reason(symbol)
        pending_ref = str(g.pending_entry.get(symbol) or "")
        pending_side = int(g.pending_entry_side.get(symbol, 0))
        pending_reentry = bool(g.pending_entry_reentry.get(symbol, False))
        pending_status = get_order_status(pending_ref).get("status") if pending_ref else ""

        if pending_ref and _is_terminal_failure(pending_status):
            g.pending_entry.pop(symbol, None)
            g.pending_entry_side.pop(symbol, None)
            g.pending_entry_reentry.pop(symbol, None)
            if not current_side:
                g.cooldown[symbol] = max(int(g.cooldown.get(symbol, 0)), cooldown_bars)
            pending_ref = ""
            pending_side = 0
        elif pending_ref and pending_status == "filled" and current_side:
            if pending_reentry:
                g.reentry_count[symbol] = int(g.reentry_count.get(symbol, 0)) + 1
            g.pending_entry.pop(symbol, None)
            g.pending_entry_side.pop(symbol, None)
            g.pending_entry_reentry.pop(symbol, None)
            pending_ref = ""
            pending_side = 0
        elif pending_ref and pending_status == "filled" and not current_side and exit_reason:
            # An entry can fill and hit protection on the same bar before the
            # next strategy callback observes a non-zero position.
            g.pending_entry.pop(symbol, None)
            g.pending_entry_side.pop(symbol, None)
            g.pending_entry_reentry.pop(symbol, None)
            pending_ref = ""

        observed_exit_side = previous_side or (pending_side if exit_reason else 0)
        if observed_exit_side and not current_side and exit_reason:
            g.last_exit_side[symbol] = observed_exit_side
            previous_peak = float(g.peak_price.get(symbol, 0.0) or 0.0)
            current_high = float(bars["high"].to_numpy()[-1])
            current_low = float(bars["low"].to_numpy()[-1])
            if observed_exit_side > 0:
                g.last_exit_peak[symbol] = max(previous_peak, current_high)
            else:
                g.last_exit_peak[symbol] = min(previous_peak or current_low, current_low)
            g.last_exit_bar[symbol] = bar_time
            g.last_exit_reason[symbol] = str(exit_reason or "unknown")
            if (
                params["block_after_stop_until_market_flip"]
                and str(exit_reason or "").strip().lower() == "stop_loss"
                and market_direction
            ):
                g.loss_block_market_direction[symbol] = market_direction
            if _is_profitable_exit(exit_reason):
                g.cooldown[symbol] = cooldown_bars
                g.reentry_count[symbol] = int(g.reentry_count.get(symbol, 0))
            else:
                g.cooldown[symbol] = max(cooldown_bars, 4)
                g.reentry_count[symbol] = 0

        if current_side:
            previous_peak = float(g.peak_price.get(symbol, 0.0) or 0.0)
            current_high = float(bars["high"].to_numpy()[-1])
            current_low = float(bars["low"].to_numpy()[-1])
            g.peak_price[symbol] = max(previous_peak, current_high) if current_side > 0 else min(previous_peak or current_low, current_low)
            g.position_side[symbol] = current_side
            continue
        if pending_ref and _is_working_status(pending_status):
            continue
        if pending_ref and pending_status == "filled" and not exit_reason:
            # The fill is known but the synchronized position has not arrived.
            # Do not create a second intent during that reconciliation gap.
            continue
        g.position_side[symbol] = 0

        if g.cooldown.get(symbol, 0) > 0:
            g.cooldown[symbol] = int(g.cooldown[symbol]) - 1
            continue
        if g.last_action_bar.get(symbol) == bar_time:
            continue
        blocked_market_direction = int(g.loss_block_market_direction.get(symbol, 0) or 0)
        if blocked_market_direction:
            if market_direction == blocked_market_direction or not market_direction:
                continue
            g.loss_block_market_direction.pop(symbol, None)

        candidate = _candidate(bars, params, htf_bars, market_bars)
        if candidate is None:
            continue
        if candidate["mode"] == "DONCHIAN_RETEST" and g.last_setup_id.get(symbol) == candidate["setup_id"]:
            continue
        direction = int(candidate["direction"])
        last_exit_side = int(g.last_exit_side.get(symbol, 0))
        is_reentry = last_exit_side == direction and bool(g.last_exit_reason.get(symbol))
        if is_reentry:
            if not _is_profitable_exit(g.last_exit_reason.get(symbol)):
                continue
            if int(g.reentry_count.get(symbol, 0)) >= max_reentries:
                continue
            peak = float(g.last_exit_peak.get(symbol, 0.0) or 0.0)
            # Breakout re-entry must make a new extreme. Pullback reclaim may
            # re-enter after the cooldown because it is a fresh bar event.
            if candidate["mode"] == "BREAKOUT_CONTINUATION" and peak > 0:
                buffer = candidate["atr"] * 0.2
                if (direction > 0 and candidate["entry"] <= peak + buffer) or (direction < 0 and candidate["entry"] >= peak - buffer):
                    continue
        if filled_slots + reserved_slots >= max_open_positions:
            continue

        reference = _trade(
            symbol,
            candidate,
            bar_time,
            is_reentry,
            target_pct,
            take_profit_r,
            trailing_lock_profit_pct,
        )
        if not reference:
            continue
        g.pending_entry[symbol] = str(reference)
        g.pending_entry_side[symbol] = direction
        g.pending_entry_reentry[symbol] = is_reentry
        g.last_setup_id[symbol] = candidate["setup_id"]
        reserved_slots += 1
        g.last_action_bar[symbol] = bar_time
