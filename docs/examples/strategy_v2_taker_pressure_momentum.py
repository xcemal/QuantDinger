"""TAKER_PRESSURE_MOMENTUM

Research-only Strategy API V2 implementation of the Binance USD-M futures
taker-buy pressure momentum hypothesis.  It intentionally does not use Jev,
live deployment hooks, or any production execution-specific state.

The handler runs after the current driving candle is complete.  QuantDinger's
backtest runner queues the resulting order for the next bar, so the close of
the signal candle is never used as its fill price.
"""

# @param ma_period int 15 range=5:30:5
# @param confirm_bars int 3 range=2:4:1
# @param threshold_high float 0.62 range=0.58:0.68:0.02
# @param atr_period int 14 range=14:14:1
# @param hold_bars int 8 range=8:16:8
# @param stop_loss_pct float 0.01 range=0.01:0.02:0.01
# @param take_profit_pct float 0.02 range=0.02:0.035:0.015
# @param target_pct float 0.10 range=0.01:0.25:0.01


UNIVERSE = [
    "Crypto:BTC/USDT@binance:swap", "Crypto:ETH/USDT@binance:swap",
    "Crypto:SOL/USDT@binance:swap", "Crypto:BNB/USDT@binance:swap",
    "Crypto:XRP/USDT@binance:swap", "Crypto:DOGE/USDT@binance:swap",
    "Crypto:ADA/USDT@binance:swap", "Crypto:AVAX/USDT@binance:swap",
    "Crypto:LINK/USDT@binance:swap", "Crypto:BCH/USDT@binance:swap",
    "Crypto:LTC/USDT@binance:swap", "Crypto:DOT/USDT@binance:swap",
    "Crypto:SUI/USDT@binance:swap", "Crypto:TRX/USDT@binance:swap",
    "Crypto:AAVE/USDT@binance:swap", "Crypto:UNI/USDT@binance:swap",
    "Crypto:NEAR/USDT@binance:swap", "Crypto:APT/USDT@binance:swap",
    "Crypto:ARB/USDT@binance:swap", "Crypto:OP/USDT@binance:swap",
    "Crypto:INJ/USDT@binance:swap", "Crypto:ATOM/USDT@binance:swap",
    "Crypto:FIL/USDT@binance:swap", "Crypto:ETC/USDT@binance:swap",
    "Crypto:TON/USDT@binance:swap",
]


def initialize(context):
    g.last_bar = {}
    g.raw_long = {}
    g.raw_short = {}
    g.executed = {}
    context.set_universe(UNIVERSE)
    context.subscribe(
        frequency="5m",
        fields=[
            "open", "high", "low", "close", "volume",
            "taker_buy_volume",
        ],
    )
    context.set_metadata(
        direction_mode="one_way",
        strategy_family="TAKER_PRESSURE_MOMENTUM",
        signal_input="binance_usdm_taker_buy_base_asset_volume",
        signal_timing="completed_5m_bar_then_next_bar_fill",
        volatility_filter="ATR > rolling_50_ATR * 0.8",
        short_threshold="1 - threshold_high",
        sizing_model="fixed_target_percent",
    )
    context.set_warmup(80)
    context.allow_leverage(max_leverage=5)


def _number(value):
    return str(round(float(value), 8))


def _atr(bars, period):
    highs = [float(value) for value in bars["high"].to_numpy()]
    lows = [float(value) for value in bars["low"].to_numpy()]
    closes = [float(value) for value in bars["close"].to_numpy()]
    true_ranges = []
    for index in range(len(closes)):
        previous_close = closes[index - 1] if index else closes[index]
        true_ranges.append(max(
            highs[index] - lows[index],
            abs(highs[index] - previous_close),
            abs(lows[index] - previous_close),
        ))
    values = []
    alpha = 2.0 / (max(1, int(period)) + 1.0)
    current = 0.0
    for value in true_ranges:
        current = value if current <= 0 else alpha * value + (1.0 - alpha) * current
        values.append(current)
    return values


def _buy_ratios(bars):
    ratios = []
    for volume, taker_buy in zip(
        bars["volume"].to_numpy(),
        bars["taker_buy_volume"].to_numpy(),
    ):
        total = float(volume or 0.0)
        taker = float(taker_buy or 0.0)
        ratios.append(taker / total if total > 0 else 0.5)
    return ratios


def _pressure_reason(
    direction,
    bar_time,
    buy_ratio,
    buy_ratio_ma,
    confirm_bars,
    threshold_high,
    atr,
    atr_ma_50,
    target_pct,
    stop_loss_pct,
    take_profit_pct,
):
    side = "LONG" if direction > 0 else "SHORT"
    return (
        "TAKER_PRESSURE_MOMENTUM"
        + "|direction=" + side
        + "|buy_ratio=" + _number(buy_ratio)
        + "|buy_ratio_ma=" + _number(buy_ratio_ma)
        + "|confirm_bars=" + str(int(confirm_bars))
        + "|threshold_high=" + _number(threshold_high)
        + "|threshold_low=" + _number(1.0 - threshold_high)
        + "|atr=" + _number(atr)
        + "|atr_ma_50=" + _number(atr_ma_50)
        + "|atr_ratio=" + _number(atr / max(atr_ma_50, 1e-12))
        + "|entry_reference=completed_bar_close"
        + "|fill_policy=next_bar_open"
        + "|stop_loss_pct=" + _number(stop_loss_pct)
        + "|take_profit_pct=" + _number(take_profit_pct)
        + "|target_pct=" + _number(target_pct)
        + "|bar=" + str(bar_time)
    )


def handle_data(context, data):
    ma_period = max(1, int(context.params.get("ma_period", 15)))
    confirm_bars = max(1, int(context.params.get("confirm_bars", 3)))
    threshold_high = float(context.params.get("threshold_high", 0.62))
    atr_period = max(1, int(context.params.get("atr_period", 14)))
    hold_bars = max(1, int(context.params.get("hold_bars", 8)))
    stop_loss_pct = max(0.0, float(context.params.get("stop_loss_pct", 0.01)))
    take_profit_pct = max(0.0, float(context.params.get("take_profit_pct", 0.02)))
    target_pct = max(0.0, float(context.params.get("target_pct", 0.10)))
    count = max(80, ma_period + confirm_bars + atr_period + 55)

    for symbol in UNIVERSE:
        bars = get_history(
            count,
            "5m",
            ["open", "high", "low", "close", "volume", "taker_buy_volume"],
            symbol,
        )
        if "taker_buy_volume" not in bars.columns:
            # A missing field is a data-readiness failure, never an OHLCV
            # proxy.  Keeping the symbol silent prevents a false edge.
            continue
        minimum = max(ma_period, confirm_bars, atr_period, 52)
        if len(bars) < minimum:
            continue
        bar_time = str(bars.index[-1])
        if g.last_bar.get(symbol) == bar_time:
            continue
        g.last_bar[symbol] = bar_time

        ratios = _buy_ratios(bars)
        atr_values = _atr(bars, atr_period)
        if len(ratios) < ma_period or len(atr_values) < 52:
            continue
        buy_ratio = ratios[-1]
        buy_ratio_ma = sum(ratios[-ma_period:]) / float(ma_period)
        atr = atr_values[-1]
        atr_ma_50 = sum(atr_values[-50:]) / 50.0
        if atr <= 0 or atr_ma_50 <= 0:
            continue
        volatility_ok = atr > atr_ma_50 * 0.8
        confirm_window = ratios[-confirm_bars:]
        long_raw = (
            buy_ratio_ma > threshold_high
            and all(value > 0.50 for value in confirm_window)
            and volatility_ok
        )
        short_raw = (
            buy_ratio_ma < 1.0 - threshold_high
            and all(value < 0.50 for value in confirm_window)
            and volatility_ok
        )
        if long_raw:
            g.raw_long[symbol] = int(g.raw_long.get(symbol, 0)) + 1
        if short_raw:
            g.raw_short[symbol] = int(g.raw_short.get(symbol, 0)) + 1
        if not long_raw and not short_raw:
            continue

        direction = 1 if long_raw else -1
        position = get_position(symbol)
        amount = float(position.amount or 0.0)
        if abs(amount) > 1e-12:
            continue

        reason = _pressure_reason(
            direction,
            bar_time,
            buy_ratio,
            buy_ratio_ma,
            confirm_bars,
            threshold_high,
            atr,
            atr_ma_50,
            target_pct,
            stop_loss_pct,
            take_profit_pct,
        )
        order_target_percent(
            symbol,
            target_pct if direction > 0 else -target_pct,
            reason=reason,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            time_limit_seconds=hold_bars * 300,
            client_order_id=(
                "taker-pressure-" + ("long" if direction > 0 else "short")
                + "-" + str(symbol) + "-" + bar_time.replace(" ", "T").replace(":", "")
            ),
        )
        g.executed[symbol] = int(g.executed.get(symbol, 0)) + 1

