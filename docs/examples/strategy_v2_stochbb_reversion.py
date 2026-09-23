"""StochBB mean-reversion strategy for crypto swaps with ATR protection."""

import math

# @param bb_length int 20 range=5:100:1
# @param bb_stddev float 2.0 range=1:4:0.25
# @param rsi_length int 14 range=5:50:1
# @param stoch_length int 14 range=5:50:1
# @param oversold float 0.2 range=0.05:0.45:0.05
# @param overbought float 0.8 range=0.55:0.95:0.05
# @param atr_length int 14 range=5:50:1
# @param min_band_width_atr float 1.0 range=0.1:5:0.1
# @param stop_multiplier float 1.5 range=0.5:6:0.1
# @param reward_risk float 1.5 range=0.5:5:0.25
# @param max_stop_pct float 0.04 range=0.005:0.15:0.005
# target_pct is a per-symbol cap before the selected futures leverage multiplier;
# risk_per_trade_pct reduces it when the ATR stop is wider.
# @param target_pct float 0.1 range=0.05:0.2:0.05
# @param risk_per_trade_pct float 0.005 range=0.001:0.02:0.001
# @param trend_ema_length int 50 range=10:200:5
# @param trend_slope_bars int 6 range=2:24:1
# @param use_trend_filter int 1 range=0:1:1
# @param time_limit_bars int 72 range=12:288:12
# @param max_trend_slope_atr float 1.5 range=0.1:5:0.1
# @param use_mid_target int 1 range=0:1:1
# @param min_target_risk float 1.0 range=0.5:3:0.25
# @param use_market_shock_filter int 1 range=0:1:1
# @param market_shock_atr_threshold float 2.0 range=1:5:0.25
# @param profit_lock_activation_r float 0.5 range=0.25:2:0.25
# @param profit_lock_trail_r float 0.5 range=0.25:2:0.25
# @param trailing_lock_profit_pct float 0.0015 range=0:0.01:0.0005
# @param use_regime_exit int 0 range=0:1:1
# @param min_reclaim_stoch float 0.0 range=0:0.5:0.05
# @param short_max_reclaim_stoch float 1.0 range=0.5:1:0.05
# @param min_stop_pct float 0.0 range=0:0.02:0.0005


UNIVERSE = [
    "Crypto:BTC/USDT@swap", "Crypto:ETH/USDT@swap", "Crypto:SOL/USDT@swap",
    "Crypto:BNB/USDT@swap", "Crypto:XRP/USDT@swap", "Crypto:DOGE/USDT@swap",
    "Crypto:ADA/USDT@swap", "Crypto:AVAX/USDT@swap", "Crypto:LINK/USDT@swap",
    "Crypto:BCH/USDT@swap",
]


def initialize(context):
    g.last_bar = {}
    g.last_signal = {}
    g.rearmed = {}
    g.exit_pending = {}
    context.set_universe(UNIVERSE)
    context.subscribe(frequency="5m", fields=["open", "high", "low", "close", "volume"])
    context.set_metadata(
        direction_mode="one_way",
        strategy_family="STOCHBB_REVERSION",
        position_manager="ATR_STOP_RR_TARGET_RECLAIM_FILTER",
    )
    context.set_warmup(160)
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


def _bands(closes, length, deviation):
    length = max(2, int(length))
    window = closes[-length:]
    mean = sum(window) / len(window)
    variance = sum((value - mean) ** 2 for value in window) / len(window)
    spread = float(deviation) * math.sqrt(max(0.0, variance))
    return mean - spread, mean, mean + spread


def _number(value):
    return str(round(float(value), 8))


def _reason(direction, entry, stop, target, rr, stoch, band_width, bar_time):
    return (
        "STOCHBB_REVERSION|intent=entry|direction="
        + ("LONG" if direction > 0 else "SHORT")
        + "|reference_entry=" + _number(entry)
        + "|stop=" + _number(stop)
        + "|target=" + _number(target)
        + "|reward_risk=" + _number(rr)
        + "|stop_pct=" + _number(abs(entry - stop) / entry)
        + "|stochrsi=" + _number(stoch)
        + "|band_width_atr=" + _number(band_width)
        + "|signal_age=0|evidence=band_excursion+reclaim+stochrsi_cross"
        + "|bar=" + str(bar_time)
    )


def _trade(symbol, direction, entry, stop, target, rr, stoch, band_width, bar_time, position_pct, time_limit_bars, market_shock_atr, profit_lock_activation_r, profit_lock_trail_r, trailing_lock_profit_pct):
    amount = float(get_position(symbol).amount or 0.0)
    if direction > 0 and amount < -1e-12:
        order_target_percent(symbol, 0.0, reason="STOCHBB_REVERSION|intent=close_opposite|direction=LONG")
        return True
    if direction < 0 and amount > 1e-12:
        order_target_percent(symbol, 0.0, reason="STOCHBB_REVERSION|intent=close_opposite|direction=SHORT")
        return True
    if (direction > 0 and amount > 1e-12) or (direction < 0 and amount < -1e-12):
        return False
    side = "long" if direction > 0 else "short"
    client_id = "stochbb-reversion-" + side + "-" + str(symbol) + "-" + str(bar_time).replace(" ", "T").replace(":", "")
    stop_pct = abs(entry - stop) / entry
    reason = _reason(direction, entry, stop, target, rr, stoch, band_width, bar_time)
    reason += "|market_shock_atr=" + _number(market_shock_atr)
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
    bb_length = int(context.params.get("bb_length", 20))
    bb_stddev = float(context.params.get("bb_stddev", 2.0))
    rsi_length = int(context.params.get("rsi_length", 14))
    stoch_length = int(context.params.get("stoch_length", 14))
    oversold = float(context.params.get("oversold", 0.2))
    overbought = float(context.params.get("overbought", 0.8))
    atr_length = int(context.params.get("atr_length", 14))
    min_band_width_atr = float(context.params.get("min_band_width_atr", 1.0))
    stop_multiplier = float(context.params.get("stop_multiplier", 1.5))
    reward_risk = float(context.params.get("reward_risk", 1.5))
    max_stop_pct = float(context.params.get("max_stop_pct", 0.04))
    target_pct = float(context.params.get("target_pct", 0.1))
    risk_per_trade_pct = max(0.0001, float(context.params.get("risk_per_trade_pct", 0.005)))
    execution_leverage = max(1.0, float(context.leverage))
    trend_ema_length = max(5, int(context.params.get("trend_ema_length", 50)))
    trend_slope_bars = max(2, int(context.params.get("trend_slope_bars", 6)))
    use_trend_filter = int(context.params.get("use_trend_filter", 1))
    time_limit_bars = max(12, int(context.params.get("time_limit_bars", 72)))
    max_trend_slope_atr = max(0.1, float(context.params.get("max_trend_slope_atr", 1.5)))
    use_mid_target = int(context.params.get("use_mid_target", 1))
    min_target_risk = max(0.5, float(context.params.get("min_target_risk", 1.0)))
    use_market_shock_filter = int(context.params.get("use_market_shock_filter", 1))
    market_shock_atr_threshold = max(1.0, float(context.params.get("market_shock_atr_threshold", 2.0)))
    profit_lock_activation_r = max(0.0, float(context.params.get("profit_lock_activation_r", 0.5)))
    profit_lock_trail_r = max(0.0, float(context.params.get("profit_lock_trail_r", 0.5)))
    trailing_lock_profit_pct = max(0.0, float(context.params.get("trailing_lock_profit_pct", 0.0015)))
    use_regime_exit = int(context.params.get("use_regime_exit", 0))
    min_reclaim_stoch = min(0.5, max(0.0, float(context.params.get("min_reclaim_stoch", 0.0))))
    short_max_reclaim_stoch = min(1.0, max(0.5, float(context.params.get("short_max_reclaim_stoch", 1.0))))
    min_stop_pct = max(0.0, float(context.params.get("min_stop_pct", 0.0)))
    count = max(bb_length * 3, rsi_length + stoch_length + 30, atr_length * 4, 100) + 8
    market_bars = get_history(count, "5m", ["open", "high", "low", "close", "volume"], UNIVERSE[0])
    market_atr = _atr(market_bars, atr_length) if len(market_bars) >= atr_length + 8 else 0.0
    market_shock_atr = 0.0
    if market_atr > 0:
        market_shock_atr = (float(market_bars["high"].iloc[-1]) - float(market_bars["low"].iloc[-1])) / market_atr

    for symbol in UNIVERSE:
        bars = get_history(count, "5m", ["open", "high", "low", "close", "volume"], symbol)
        if len(bars) < max(bb_length + 3, rsi_length + stoch_length + 3, atr_length + 8):
            continue
        bar_time = str(bars.index[-1])
        if g.last_bar.get(symbol) == bar_time:
            continue
        g.last_bar[symbol] = bar_time
        if use_market_shock_filter and market_shock_atr >= market_shock_atr_threshold:
            continue
        closes = [float(value) for value in bars["close"].to_numpy()]
        stoch = _stoch_rsi(closes, rsi_length, stoch_length)
        current_stoch = stoch[-1]
        previous_stoch = stoch[-2]
        current_lower, current_mid, current_upper = _bands(closes, bb_length, bb_stddev)
        previous_lower, previous_mid, previous_upper = _bands(closes[:-1], bb_length, bb_stddev)
        entry = closes[-1]
        atr = _atr(bars, atr_length)
        if entry <= 0 or atr <= 0:
            continue
        trend = _ema(closes, trend_ema_length)
        if len(trend) <= trend_slope_bars:
            continue
        if not bool(g.rearmed.get(symbol, True)):
            reset_distance = max(atr * 0.5, (current_upper - current_lower) * 0.2)
            if abs(entry - current_mid) <= reset_distance:
                g.rearmed[symbol] = True
            else:
                continue
        band_width = (current_upper - current_lower) / atr
        if band_width < min_band_width_atr:
            continue
        rising_regime = trend[-1] >= trend[-1 - trend_slope_bars]
        falling_regime = trend[-1] <= trend[-1 - trend_slope_bars]
        trend_slope_atr = abs(trend[-1] - trend[-1 - trend_slope_bars]) / atr
        if trend_slope_atr > max_trend_slope_atr:
            continue
        amount = float(get_position(symbol).amount or 0.0)
        if abs(amount) <= 1e-12:
            g.exit_pending[symbol] = False
        if use_regime_exit and not g.exit_pending.get(symbol, False) and trend_slope_atr >= 0.25:
            if amount > 1e-12 and falling_regime:
                order_target_percent(
                    symbol,
                    0.0,
                    reason=(
                        "STOCHBB_REVERSION|intent=exit_regime_flip|direction=LONG"
                        + "|trend_slope_atr=" + _number(trend_slope_atr)
                        + "|evidence=ema_regime_flip|bar=" + bar_time
                    ),
                )
                g.rearmed[symbol] = True
                g.exit_pending[symbol] = True
                continue
            if amount < -1e-12 and rising_regime:
                order_target_percent(
                    symbol,
                    0.0,
                    reason=(
                        "STOCHBB_REVERSION|intent=exit_regime_flip|direction=SHORT"
                        + "|trend_slope_atr=" + _number(trend_slope_atr)
                        + "|evidence=ema_regime_flip|bar=" + bar_time
                    ),
                )
                g.rearmed[symbol] = True
                g.exit_pending[symbol] = True
                continue
        long_signal = (
            closes[-2] < previous_lower
            and entry > current_lower
            and previous_stoch <= oversold
            and current_stoch >= max(oversold, min_reclaim_stoch)
            and (not use_trend_filter or rising_regime)
        )
        short_signal = (
            closes[-2] > previous_upper
            and entry < current_upper
            and previous_stoch >= overbought
            and current_stoch <= min(overbought, short_max_reclaim_stoch)
            and (not use_trend_filter or falling_regime)
        )
        direction = 1 if long_signal else -1 if short_signal else 0
        if direction == 0:
            continue
        signal_key = str(direction) + "|" + bar_time
        if g.last_signal.get(symbol) == signal_key:
            continue
        stop_pct = min(max_stop_pct, max(0.0005, stop_multiplier * atr / entry))
        if stop_pct < min_stop_pct:
            continue
        stop = entry * (1.0 - stop_pct) if direction > 0 else entry * (1.0 + stop_pct)
        if use_mid_target:
            target = current_mid
            target_is_valid = target > entry if direction > 0 else target < entry
            if not target_is_valid:
                continue
            actual_reward_risk = abs(target - entry) / (entry * stop_pct)
            if actual_reward_risk < min_target_risk:
                continue
        else:
            actual_reward_risk = reward_risk
            target = entry * (1.0 + stop_pct * actual_reward_risk) if direction > 0 else entry * (1.0 - stop_pct * actual_reward_risk)
        position_pct = min(target_pct, risk_per_trade_pct / max(1e-9, execution_leverage * stop_pct))
        if position_pct <= 0:
            continue
        if _trade(symbol, direction, entry, stop, target, actual_reward_risk, current_stoch, band_width, bar_time, position_pct, time_limit_bars, market_shock_atr, profit_lock_activation_r, profit_lock_trail_r, trailing_lock_profit_pct):
            g.rearmed[symbol] = False
        g.last_signal[symbol] = signal_key
