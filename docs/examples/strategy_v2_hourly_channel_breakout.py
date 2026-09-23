"""Hourly Channel Breakout

Plan aday 1: tamamlanmış 1h Donchian kanal kırılımı, 4h EMA100 rejim filtresi
ve ATR tabanlı başlangıç stopu. Sinyal mumunun kanala dahil edilmemesi,
kanal kırılımının yalnızca gerçek geçişte üretilmesi ve karşı kanal kapanışının
trend çıkışı olarak kullanılması özellikle korunur.
"""

PERSIST_RUNTIME_STATE = True

# @param channel_length int 48 range=24:96:24
# @param exit_channel_length int 20 range=10:40:10
# @param regime_ema_length int 100 range=50:200:25
# @param atr_length int 14 range=5:50:1
# @param stop_multiplier float 2.0 range=0.5:4:0.25
# @param max_stop_pct float 0.10 range=0.02:0.20:0.01
# @param target_pct float 0.10 range=0.02:0.50:0.01


UNIVERSE = [
    "Crypto:BTC/USDT@swap", "Crypto:ETH/USDT@swap", "Crypto:SOL/USDT@swap",
    "Crypto:BNB/USDT@swap", "Crypto:XRP/USDT@swap", "Crypto:DOGE/USDT@swap",
    "Crypto:ADA/USDT@swap", "Crypto:AVAX/USDT@swap", "Crypto:LINK/USDT@swap",
    "Crypto:BCH/USDT@swap",
]


def initialize(context):
    g.last_signal_bar = {}
    g.last_bar = {}
    context.set_universe(UNIVERSE)
    context.subscribe(frequency="1h", fields=["open", "high", "low", "close", "volume"])
    context.subscribe(frequency="4h", fields=["open", "high", "low", "close", "volume"])
    context.set_metadata(
        direction_mode="one_way",
        strategy_family="HOURLY_CHANNEL_BREAKOUT",
        entry="completed_1h_channel_breakout",
        regime="completed_4h_ema100",
        exit="opposite_1h_channel_close",
        position_manager="atr_initial_stop_no_fixed_target",
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
            "HOURLY_CHANNEL_BREAKOUT|intent=EXIT|direction="
            + ("LONG" if side > 0 else "SHORT")
            + "|exit=opposite_channel_close|level=" + _number(level)
            + "|bar=" + str(bar_time)
        ),
        client_order_id=(
            "hourly-channel-exit-" + str(symbol) + "-"
            + str(bar_time).replace(" ", "T").replace(":", "")
        ),
    )


def _open_position(symbol, direction, entry, stop, atr, channel_length, bar_time, target_pct):
    stop_pct = abs(entry - stop) / entry if entry > 0 else 0.0
    reason = (
        "HOURLY_CHANNEL_BREAKOUT|intent=ENTRY|direction="
        + ("LONG" if direction > 0 else "SHORT")
        + "|reference_entry=" + _number(entry)
        + "|stop=" + _number(stop)
        + "|target=none|reward_risk=runner"
        + "|stop_pct=" + _number(stop_pct)
        + "|atr=" + _number(atr)
        + "|channel_length=" + str(channel_length)
        + "|regime=4h_ema100"
        + "|evidence=completed_channel_breakout+completed_4h_regime"
        + "|bar=" + str(bar_time)
    )
    return order_target_percent(
        symbol,
        target_pct if direction > 0 else -target_pct,
        reason=reason,
        stop_loss_pct=stop_pct,
        client_order_id=(
            "hourly-channel-entry-" + ("long-" if direction > 0 else "short-")
            + str(symbol) + "-" + str(bar_time).replace(" ", "T").replace(":", "")
        ),
    )


def handle_data(context, data):
    channel_length = max(24, int(context.params.get("channel_length", 48)))
    exit_channel_length = max(10, int(context.params.get("exit_channel_length", 20)))
    regime_ema_length = max(50, int(context.params.get("regime_ema_length", 100)))
    atr_length = max(5, int(context.params.get("atr_length", 14)))
    stop_multiplier = max(0.5, float(context.params.get("stop_multiplier", 2.0)))
    max_stop_pct = max(0.02, float(context.params.get("max_stop_pct", 0.10)))
    target_pct = max(0.02, float(context.params.get("target_pct", 0.10)))
    hourly_count = max(channel_length + exit_channel_length + atr_length * 3, 120) + 8
    regime_count = max(regime_ema_length * 2, 140) + 8

    for symbol in UNIVERSE:
        bars = get_history(
            hourly_count,
            "1h",
            ["open", "high", "low", "close", "volume"],
            symbol,
        )
        regime_bars = get_history(
            regime_count,
            "4h",
            ["open", "high", "low", "close", "volume"],
            symbol,
        )
        if len(bars) < channel_length + exit_channel_length + atr_length + 4:
            continue
        if len(regime_bars) < regime_ema_length + 2:
            continue

        bar_time = str(bars.index[-1])
        if g.last_bar.get(symbol) == bar_time:
            continue
        g.last_bar[symbol] = bar_time

        closes = _values(bars, "close")
        highs = _values(bars, "high")
        lows = _values(bars, "low")
        entry = closes[-1]
        previous_close = closes[-2]
        atr = _atr(bars, atr_length)
        if entry <= 0 or atr <= 0:
            continue

        # Both current and previous channels exclude their signal candle.
        prior_high = max(highs[-channel_length - 1:-1])
        prior_low = min(lows[-channel_length - 1:-1])
        earlier_high = max(highs[-channel_length - 2:-2])
        earlier_low = min(lows[-channel_length - 2:-2])
        long_breakout = entry > prior_high and previous_close <= earlier_high
        short_breakout = entry < prior_low and previous_close >= earlier_low

        regime_closes = _values(regime_bars, "close")
        regime_ema = _ema(regime_closes, regime_ema_length)[-1]
        regime_price = regime_closes[-1]
        long_regime = regime_price > regime_ema
        short_regime = regime_price < regime_ema

        amount = float(get_position(symbol).amount or 0.0)
        current_side = 1 if amount > 1e-12 else -1 if amount < -1e-12 else 0

        # Exit is evaluated on the completed 1h close and is never combined
        # with a fresh entry on the same bar.
        exit_high = max(highs[-exit_channel_length - 1:-1])
        exit_low = min(lows[-exit_channel_length - 1:-1])
        if current_side > 0 and entry < exit_low:
            _close_position(symbol, current_side, bar_time, exit_low)
            continue
        if current_side < 0 and entry > exit_high:
            _close_position(symbol, current_side, bar_time, exit_high)
            continue
        if current_side != 0:
            continue

        direction = 1 if long_breakout and long_regime else -1 if short_breakout and short_regime else 0
        if direction == 0:
            continue
        setup_id = ("LONG" if direction > 0 else "SHORT") + "|" + bar_time + "|" + str(channel_length)
        if g.last_signal_bar.get(symbol) == setup_id:
            continue
        stop = entry - stop_multiplier * atr if direction > 0 else entry + stop_multiplier * atr
        stop_pct = abs(entry - stop) / entry
        if stop_pct <= 0 or stop_pct > max_stop_pct:
            continue
        _open_position(symbol, direction, entry, stop, atr, channel_length, bar_time, target_pct)
        g.last_signal_bar[symbol] = setup_id
