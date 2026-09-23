-- ===== Strategy API V2 canonical template seed =====

DELETE FROM qd_script_templates
WHERE template_key NOT IN (
    'strategy_v2_single_ma',
    'strategy_v2_double_ma',
    'strategy_v2_bullish_three_lines',
    'strategy_v2_bullish_three_lines_trend',
    'strategy_v2_turtle',
    'strategy_v2_indicator_resonance',
    'strategy_v2_macd_kdj',
    'strategy_v2_supertrend',
    'strategy_v2_market_cap_barbell',
    'strategy_v2_momentum_top_n',
    'strategy_v2_low_volatility',
    'strategy_v2_quality_growth',
    'strategy_v2_rapid_accel',
    'strategy_v2_trend_flip',
    'strategy_v2_sweep_absorption'
);

INSERT INTO qd_script_templates
(template_key, asset_type, title, description, code, param_schema, tags, icon, accent, sort_order, is_active, metadata, updated_at)
VALUES
('strategy_v2_single_ma', 'script', 'Single Moving Average', 'A parameterized SPY trend strategy using one moving average.', $single$"""
Single Moving Average
SPY trend regime driven by a configurable moving average.
"""

# @param ma_period int 50 range=2:250:1
# @param target_pct float 0.95 range=0.05:1:0.05

def initialize(context):
    g.symbol = "USStock:SPY"
    context.set_universe([g.symbol])
    context.set_benchmark(g.symbol)
    context.subscribe(frequency="1d")
    context.set_metadata(direction_mode="long_only")
    context.set_warmup(260)


def handle_data(context, data):
    ma_period = int(context.params.get("ma_period", 50))
    target_pct = float(context.params.get("target_pct", 0.95))
    bars = get_history(ma_period + 2, "1d", "close", g.symbol)
    if len(bars) < ma_period + 1:
        return
    close = bars["close"]
    average = float(close.iloc[:-1].tail(ma_period).mean())
    price = float(close.iloc[-1])
    position = get_position(g.symbol)
    is_long = float(position.amount or 0.0) > 0
    if price > average and not is_long:
        order_target_percent(g.symbol, target_pct, reason="single_ma_entry")
    elif price <= average and is_long:
        order_target_percent(g.symbol, 0.0, reason="single_ma_exit")
$single$, '{"params":[{"name":"ma_period","type":"integer","default":50,"min":2,"max":250,"step":1,"labelKey":"strategyV2.params.maPeriod","descriptionKey":"strategyV2.params.maPeriodDesc"},{"name":"target_pct","type":"percent","default":0.95,"min":0.05,"max":1,"step":0.05,"labelKey":"strategyV2.params.targetPosition","descriptionKey":"strategyV2.params.targetPositionDesc"}]}'::jsonb, '["strategy-v2","cta","moving-average","us-stock"]'::jsonb, 'line-chart', 'green', 10, TRUE, '{"source":"system_seed","version":11,"apiVersion":2}'::jsonb, NOW()),

('strategy_v2_double_ma', 'script', 'Dual Moving Average', 'A parameterized BTC perpetual dual moving-average strategy with optional leverage.', $double$"""
Dual Moving Average
BTC perpetual trend strategy with configurable long and short regimes.
"""

# @param fast_period int 20 range=2:100:1
# @param slow_period int 60 range=5:300:1
# @param target_pct float 0.95 range=0.05:1:0.05
# @param allow_short bool true

def initialize(context):
    g.symbol = "Crypto:BTC/USDT@swap"
    context.set_universe([g.symbol])
    context.set_benchmark("Crypto:BTC/USDT@spot")
    context.subscribe(frequency="4h")
    context.set_metadata(direction_mode="one_way")
    context.set_warmup(310)
    context.allow_leverage(max_leverage=20)


def handle_data(context, data):
    fast_period = int(context.params.get("fast_period", 20))
    slow_period = int(context.params.get("slow_period", 60))
    target_pct = float(context.params.get("target_pct", 0.95))
    allow_short = bool(context.params.get("allow_short", True))
    if fast_period >= slow_period:
        return
    bars = get_history(slow_period + 2, "4h", "close", g.symbol)
    if len(bars) < slow_period + 1:
        return
    close = bars["close"]
    fast = float(close.tail(fast_period).mean())
    slow = float(close.tail(slow_period).mean())
    amount = float(get_position(g.symbol).amount or 0.0)
    long_open = amount > 1e-12
    short_open = amount < -1e-12
    bullish = fast > slow
    if bullish:
        if short_open:
            order_target_percent(g.symbol, 0.0, reason="dual_ma_close_short")
        elif not long_open:
            order_target_percent(g.symbol, target_pct, reason="dual_ma_open_long")
    else:
        if long_open:
            order_target_percent(g.symbol, 0.0, reason="dual_ma_close_long")
        elif allow_short and not short_open:
            order_target_percent(g.symbol, -target_pct, reason="dual_ma_open_short")
        elif not allow_short and short_open:
            order_target_percent(g.symbol, 0.0, reason="dual_ma_close_short_disabled")
$double$, '{"params":[{"name":"fast_period","type":"integer","default":20,"min":2,"max":100,"step":1,"labelKey":"trading-assistant.templateParam.fast_period.label","descriptionKey":"trading-assistant.templateParam.fast_period.desc"},{"name":"slow_period","type":"integer","default":60,"min":5,"max":300,"step":1,"labelKey":"trading-assistant.templateParam.slow_period.label","descriptionKey":"trading-assistant.templateParam.slow_period.desc"},{"name":"target_pct","type":"percent","default":0.95,"min":0.05,"max":1,"step":0.05,"labelKey":"strategyV2.params.targetPosition","descriptionKey":"strategyV2.params.targetPositionDesc"},{"name":"allow_short","type":"boolean","default":true,"labelKey":"strategyV2.params.allowShort","descriptionKey":"strategyV2.params.allowShortDesc"}]}'::jsonb, '["strategy-v2","cta","moving-average","crypto","swap","one-way"]'::jsonb, 'swap', 'blue', 20, TRUE, '{"source":"system_seed","version":12,"apiVersion":2}'::jsonb, NOW()),

('strategy_v2_bullish_three_lines', 'script', 'Bullish Candle Through Three Averages', 'An A-share bullish candle breakout through three configurable averages.', $three$"""
Bullish Candle Through Three Averages
Daily A-share breakout through three configurable moving averages.
"""

# @param short_period int 5 range=2:60:1
# @param mid_period int 10 range=3:120:1
# @param long_period int 20 range=5:250:1
# @param min_body_pct float 0.02 range=0:0.2:0.005
# @param target_pct float 0.95 range=0.05:1:0.05

def initialize(context):
    g.symbol = "CNStock:600519.SH"
    context.set_universe([g.symbol])
    context.set_benchmark(g.symbol)
    context.subscribe(frequency="1d")
    context.set_metadata(direction_mode="long_only")
    context.set_warmup(260)


def handle_data(context, data):
    periods = [
        int(context.params.get("short_period", 5)),
        int(context.params.get("mid_period", 10)),
        int(context.params.get("long_period", 20)),
    ]
    min_body_pct = float(context.params.get("min_body_pct", 0.02))
    target_pct = float(context.params.get("target_pct", 0.95))
    if not periods[0] < periods[1] < periods[2]:
        return
    bars = get_history(periods[-1] + 3, "1d", ["open", "close"], g.symbol)
    if len(bars) < periods[-1] + 1:
        return
    close = bars["close"]
    current = bars.iloc[-1]
    averages = [float(close.iloc[:-1].tail(period).mean()) for period in periods]
    open_price = float(current["open"])
    close_price = float(current["close"])
    body_pct = (close_price - open_price) / open_price if open_price > 0 else 0.0
    crossed = body_pct >= min_body_pct and open_price <= min(averages) and close_price >= max(averages)
    position = get_position(g.symbol)
    is_long = float(position.amount or 0.0) > 0
    if crossed and not is_long:
        order_target_percent(g.symbol, target_pct, reason="bullish_three_lines_entry")
    elif is_long and close_price < averages[-1]:
        order_target_percent(g.symbol, 0.0, reason="bullish_three_lines_exit")
$three$, '{"params":[{"name":"short_period","type":"integer","default":5,"min":2,"max":60,"step":1,"labelKey":"strategyV2.params.shortPeriod","descriptionKey":"strategyV2.params.shortPeriodDesc"},{"name":"mid_period","type":"integer","default":10,"min":3,"max":120,"step":1,"labelKey":"strategyV2.params.midPeriod","descriptionKey":"strategyV2.params.midPeriodDesc"},{"name":"long_period","type":"integer","default":20,"min":5,"max":250,"step":1,"labelKey":"strategyV2.params.longPeriod","descriptionKey":"strategyV2.params.longPeriodDesc"},{"name":"min_body_pct","type":"percent","default":0.02,"min":0,"max":0.2,"step":0.005,"labelKey":"strategyV2.params.minBodyPct","descriptionKey":"strategyV2.params.minBodyPctDesc"},{"name":"target_pct","type":"percent","default":0.95,"min":0.05,"max":1,"step":0.05,"labelKey":"strategyV2.params.targetPosition","descriptionKey":"strategyV2.params.targetPositionDesc"}]}'::jsonb, '["strategy-v2","cta","candlestick","a-share"]'::jsonb, 'rise', 'red', 30, TRUE, '{"source":"system_seed","version":11,"apiVersion":2}'::jsonb, NOW()),

('strategy_v2_bullish_three_lines_trend', 'script', 'Bullish Three Averages With Trend Filter', 'The three-average breakout combined with a configurable rising trend filter.', $threetrend$"""
Bullish Three Averages With Trend Filter
Daily A-share breakout with a configurable rising trend filter.
"""

# @param short_period int 5 range=2:60:1
# @param mid_period int 10 range=3:120:1
# @param long_period int 20 range=5:250:1
# @param trend_period int 60 range=20:300:1
# @param trend_slope_bars int 5 range=1:30:1
# @param min_body_pct float 0.02 range=0:0.2:0.005
# @param target_pct float 0.95 range=0.05:1:0.05

def initialize(context):
    g.symbol = "CNStock:600519.SH"
    context.set_universe([g.symbol])
    context.set_benchmark(g.symbol)
    context.subscribe(frequency="1d")
    context.set_metadata(direction_mode="long_only")
    context.set_warmup(340)


def handle_data(context, data):
    periods = [int(context.params.get("short_period", 5)), int(context.params.get("mid_period", 10)), int(context.params.get("long_period", 20))]
    trend_period = int(context.params.get("trend_period", 60))
    slope_bars = int(context.params.get("trend_slope_bars", 5))
    min_body_pct = float(context.params.get("min_body_pct", 0.02))
    target_pct = float(context.params.get("target_pct", 0.95))
    required = max(periods[-1], trend_period) + slope_bars + 2
    bars = get_history(required, "1d", ["open", "close"], g.symbol)
    if len(bars) < required - 1 or not periods[0] < periods[1] < periods[2]:
        return
    close = bars["close"]
    current = bars.iloc[-1]
    averages = [float(close.iloc[:-1].tail(period).mean()) for period in periods]
    trend_now = float(close.iloc[:-1].tail(trend_period).mean())
    trend_before = float(close.iloc[:-1 - slope_bars].tail(trend_period).mean())
    open_price = float(current["open"])
    close_price = float(current["close"])
    body_pct = (close_price - open_price) / open_price if open_price > 0 else 0.0
    crossed = body_pct >= min_body_pct and open_price <= min(averages) and close_price >= max(averages)
    trend_ok = close_price > trend_now and trend_now > trend_before
    position = get_position(g.symbol)
    is_long = float(position.amount or 0.0) > 0
    if crossed and trend_ok and not is_long:
        order_target_percent(g.symbol, target_pct, reason="bullish_three_lines_trend_entry")
    elif is_long and (close_price < averages[-1] or not trend_ok):
        order_target_percent(g.symbol, 0.0, reason="bullish_three_lines_trend_exit")
$threetrend$, '{"params":[{"name":"short_period","type":"integer","default":5,"min":2,"max":60,"step":1,"labelKey":"strategyV2.params.shortPeriod"},{"name":"mid_period","type":"integer","default":10,"min":3,"max":120,"step":1,"labelKey":"strategyV2.params.midPeriod"},{"name":"long_period","type":"integer","default":20,"min":5,"max":250,"step":1,"labelKey":"strategyV2.params.longPeriod"},{"name":"trend_period","type":"integer","default":60,"min":20,"max":300,"step":1,"labelKey":"strategyV2.params.trendPeriod"},{"name":"trend_slope_bars","type":"integer","default":5,"min":1,"max":30,"step":1,"labelKey":"strategyV2.params.trendSlopeBars"},{"name":"min_body_pct","type":"percent","default":0.02,"min":0,"max":0.2,"step":0.005,"labelKey":"strategyV2.params.minBodyPct"},{"name":"target_pct","type":"percent","default":0.95,"min":0.05,"max":1,"step":0.05,"labelKey":"strategyV2.params.targetPosition"}]}'::jsonb, '["strategy-v2","cta","candlestick","trend","a-share"]'::jsonb, 'area-chart', 'orange', 40, TRUE, '{"source":"system_seed","version":11,"apiVersion":2}'::jsonb, NOW()),

('strategy_v2_turtle', 'script', 'Turtle Trading', 'A configurable Donchian breakout, channel exit, and ATR stop strategy on SPY.', $turtle$"""
Turtle Trading
Configurable Donchian breakout, channel exit, and ATR risk stop.
"""

# @param entry_period int 20 range=5:120:1
# @param exit_period int 10 range=2:60:1
# @param atr_period int 14 range=2:100:1
# @param atr_stop_mult float 2 range=0.5:10:0.25
# @param target_pct float 0.95 range=0.05:1:0.05

def initialize(context):
    g.symbol = "USStock:SPY"
    context.set_universe([g.symbol])
    context.set_benchmark(g.symbol)
    context.subscribe(frequency="1d")
    context.set_metadata(direction_mode="long_only")
    context.set_warmup(140)


def handle_data(context, data):
    entry_period = int(context.params.get("entry_period", 20))
    exit_period = int(context.params.get("exit_period", 10))
    atr_period = int(context.params.get("atr_period", 14))
    atr_stop_mult = float(context.params.get("atr_stop_mult", 2.0))
    target_pct = float(context.params.get("target_pct", 0.95))
    required = max(entry_period, exit_period, atr_period) + 2
    bars = get_history(required, "1d", ["high", "low", "close"], g.symbol)
    atr = indicator("ATR", g.symbol, timeperiod=atr_period)
    if len(bars) < required - 1 or len(atr) < 2:
        return
    close = float(bars["close"].iloc[-1])
    entry_high = float(bars["high"].iloc[-entry_period - 1:-1].max())
    exit_low = float(bars["low"].iloc[-exit_period - 1:-1].min())
    atr_value = float(atr.iloc[-1])
    position = get_position(g.symbol)
    is_long = float(position.amount or 0.0) > 0
    if not is_long and close > entry_high:
        order_target_percent(g.symbol, target_pct, reason="turtle_breakout")
    elif is_long:
        entry_price = float(position.avg_cost or close)
        stop_price = entry_price - atr_stop_mult * atr_value
        if close < exit_low or close < stop_price:
            order_target_percent(g.symbol, 0.0, reason="turtle_exit")
$turtle$, '{"params":[{"name":"entry_period","type":"integer","default":20,"min":5,"max":120,"step":1,"labelKey":"strategyV2.params.entryPeriod"},{"name":"exit_period","type":"integer","default":10,"min":2,"max":60,"step":1,"labelKey":"strategyV2.params.exitPeriod"},{"name":"atr_period","type":"integer","default":14,"min":2,"max":100,"step":1,"labelKey":"strategyV2.params.atrPeriod"},{"name":"atr_stop_mult","type":"number","default":2,"min":0.5,"max":10,"step":0.25,"labelKey":"strategyV2.params.atrStopMult"},{"name":"target_pct","type":"percent","default":0.95,"min":0.05,"max":1,"step":0.05,"labelKey":"strategyV2.params.targetPosition"}]}'::jsonb, '["strategy-v2","cta","breakout","turtle","us-stock"]'::jsonb, 'flag', 'cyan', 50, TRUE, '{"source":"system_seed","version":11,"apiVersion":2}'::jsonb, NOW()),

('strategy_v2_indicator_resonance', 'script', 'Indicator Resonance', 'A parameterized QQQ strategy requiring MACD, RSI, and ADX confirmation.', $resonance$"""
Indicator Resonance
MACD, RSI, and ADX confirm the same bullish regime.
"""

# @param fast_period int 12 range=2:100:1
# @param slow_period int 26 range=3:200:1
# @param signal_period int 9 range=2:100:1
# @param rsi_period int 14 range=2:100:1
# @param rsi_min float 50 range=0:100:1
# @param rsi_max float 75 range=0:100:1
# @param adx_period int 14 range=2:100:1
# @param adx_min float 20 range=0:100:1
# @param target_pct float 0.95 range=0.05:1:0.05

def initialize(context):
    g.symbol = "USStock:QQQ"
    context.set_universe([g.symbol])
    context.set_benchmark(g.symbol)
    context.subscribe(frequency="1d")
    context.set_metadata(direction_mode="long_only")
    context.set_warmup(210)


def handle_data(context, data):
    fast_period = int(context.params.get("fast_period", 12))
    slow_period = int(context.params.get("slow_period", 26))
    signal_period = int(context.params.get("signal_period", 9))
    rsi_period = int(context.params.get("rsi_period", 14))
    rsi_min = float(context.params.get("rsi_min", 50))
    rsi_max = float(context.params.get("rsi_max", 75))
    adx_period = int(context.params.get("adx_period", 14))
    adx_min = float(context.params.get("adx_min", 20))
    target_pct = float(context.params.get("target_pct", 0.95))
    macd = indicator("MACD", g.symbol, fastperiod=fast_period, slowperiod=slow_period, signalperiod=signal_period)
    rsi = indicator("RSI", g.symbol, timeperiod=rsi_period)
    adx = indicator("ADX", g.symbol, timeperiod=adx_period)
    if len(macd) < 2 or len(rsi) < 2 or len(adx) < 2:
        return
    histogram = float(macd["macdhist"].iloc[-1])
    rsi_value = float(rsi.iloc[-1])
    adx_value = float(adx.iloc[-1])
    if not all(value == value for value in (histogram, rsi_value, adx_value)):
        return
    bullish = histogram > 0 and rsi_min < rsi_value < rsi_max and adx_value > adx_min
    position = get_position(g.symbol)
    is_long = float(position.amount or 0.0) > 0
    if bullish and not is_long:
        order_target_percent(g.symbol, target_pct, reason="indicator_resonance_entry")
    elif not bullish and is_long:
        order_target_percent(g.symbol, 0.0, reason="indicator_resonance_exit")
$resonance$, '{"params":[{"name":"fast_period","type":"integer","default":12,"min":2,"max":100,"step":1,"labelKey":"trading-assistant.templateParam.fast_period.label"},{"name":"slow_period","type":"integer","default":26,"min":3,"max":200,"step":1,"labelKey":"trading-assistant.templateParam.slow_period.label"},{"name":"signal_period","type":"integer","default":9,"min":2,"max":100,"step":1,"labelKey":"strategyV2.params.signalPeriod"},{"name":"rsi_period","type":"integer","default":14,"min":2,"max":100,"step":1,"labelKey":"strategyV2.params.rsiPeriod"},{"name":"rsi_min","type":"number","default":50,"min":0,"max":100,"step":1,"labelKey":"strategyV2.params.rsiMin"},{"name":"rsi_max","type":"number","default":75,"min":0,"max":100,"step":1,"labelKey":"strategyV2.params.rsiMax"},{"name":"adx_period","type":"integer","default":14,"min":2,"max":100,"step":1,"labelKey":"strategyV2.params.adxPeriod"},{"name":"adx_min","type":"number","default":20,"min":0,"max":100,"step":1,"labelKey":"strategyV2.params.adxMin"},{"name":"target_pct","type":"percent","default":0.95,"min":0.05,"max":1,"step":0.05,"labelKey":"strategyV2.params.targetPosition"}]}'::jsonb, '["strategy-v2","cta","ta-lib","resonance","us-stock"]'::jsonb, 'fund', 'purple', 60, TRUE, '{"source":"system_seed","version":11,"apiVersion":2}'::jsonb, NOW()),

('strategy_v2_macd_kdj', 'script', 'MACD and KDJ Confirmation', 'A BTC perpetual strategy combining MACD momentum, stochastic KDJ confirmation, and explicit position protection.', $macdkdj$"""
MACD and KDJ Confirmation
BTC perpetual momentum with state-transition entries confirmed by MACD and stochastic KDJ.
"""

# @param fast_period int 12 range=2:100:1
# @param slow_period int 26 range=3:200:1
# @param signal_period int 9 range=2:100:1
# @param kdj_period int 9 range=2:100:1
# @param kdj_smooth_k int 3 range=1:20:1
# @param kdj_smooth_d int 3 range=1:20:1
# @param overbought float 85 range=50:100:1
# @param target_pct float 0.95 range=0.1:5:0.05
# @param stop_loss_pct float 0.02 range=0.005:0.2:0.005
# @param trailing_activation_pct float 0.05 range=0.005:0.5:0.005
# @param trailing_stop_pct float 0.01 range=0.005:0.2:0.005

def initialize(context):
    g.symbol = "Crypto:BTC/USDT@swap"
    context.set_universe([g.symbol])
    context.set_benchmark("Crypto:BTC/USDT@spot")
    context.subscribe(frequency="4h")
    context.set_metadata(direction_mode="long_only")
    context.set_warmup(210)
    context.allow_leverage(max_leverage=5)


def handle_data(context, data):
    fast_period = int(context.params.get("fast_period", 12))
    slow_period = int(context.params.get("slow_period", 26))
    signal_period = int(context.params.get("signal_period", 9))
    kdj_period = int(context.params.get("kdj_period", 9))
    kdj_smooth_k = int(context.params.get("kdj_smooth_k", 3))
    kdj_smooth_d = int(context.params.get("kdj_smooth_d", 3))
    overbought = float(context.params.get("overbought", 85))
    target_pct = float(context.params.get("target_pct", 0.95))
    stop_loss_pct = float(context.params.get("stop_loss_pct", 0.02))
    trailing_activation_pct = float(context.params.get("trailing_activation_pct", 0.05))
    trailing_stop_pct = float(context.params.get("trailing_stop_pct", 0.01))
    macd = indicator("MACD", g.symbol, fastperiod=fast_period, slowperiod=slow_period, signalperiod=signal_period)
    kdj = indicator("STOCH", g.symbol, fastk_period=kdj_period, slowk_period=kdj_smooth_k, slowd_period=kdj_smooth_d)
    if len(macd) < 2 or len(kdj) < 2:
        return
    previous_histogram = float(macd["macdhist"].iloc[-2])
    histogram = float(macd["macdhist"].iloc[-1])
    previous_k = float(kdj["slowk"].iloc[-2])
    previous_d = float(kdj["slowd"].iloc[-2])
    k_value = float(kdj["slowk"].iloc[-1])
    d_value = float(kdj["slowd"].iloc[-1])
    if not all(value == value for value in (previous_histogram, histogram, previous_k, previous_d, k_value, d_value)):
        return
    macd_cross_up = previous_histogram <= 0 < histogram
    kdj_cross_up = previous_k <= previous_d and k_value > d_value
    enter = histogram > 0 and (macd_cross_up or kdj_cross_up) and k_value < overbought
    exit_signal = histogram <= 0 or (previous_k >= previous_d and k_value < d_value)
    position = get_position(g.symbol, position_side="long")
    is_long = float(position.amount or 0.0) > 0
    if enter and not is_long:
        order_target_percent(
            g.symbol,
            target_pct,
            position_side="long",
            reason="macd_kdj_entry",
            stop_loss_pct=stop_loss_pct,
            trailing_activation_pct=trailing_activation_pct,
            trailing_stop_pct=trailing_stop_pct,
        )
    elif exit_signal and is_long:
        order_target_percent(g.symbol, 0.0, position_side="long", reason="macd_kdj_exit")
$macdkdj$, '{"params":[{"name":"fast_period","type":"integer","default":12,"min":2,"max":100,"step":1,"labelKey":"trading-assistant.templateParam.fast_period.label"},{"name":"slow_period","type":"integer","default":26,"min":3,"max":200,"step":1,"labelKey":"trading-assistant.templateParam.slow_period.label"},{"name":"signal_period","type":"integer","default":9,"min":2,"max":100,"step":1,"labelKey":"strategyV2.params.signalPeriod"},{"name":"kdj_period","type":"integer","default":9,"min":2,"max":100,"step":1,"labelKey":"strategyV2.params.kdjPeriod"},{"name":"kdj_smooth_k","type":"integer","default":3,"min":1,"max":20,"step":1,"labelKey":"strategyV2.params.kdjSmoothK"},{"name":"kdj_smooth_d","type":"integer","default":3,"min":1,"max":20,"step":1,"labelKey":"strategyV2.params.kdjSmoothD"},{"name":"overbought","type":"number","default":85,"min":50,"max":100,"step":1,"labelKey":"trading-assistant.templateParam.overbought.label"},{"name":"target_pct","type":"number","default":0.95,"min":0.1,"max":5,"step":0.05,"labelKey":"strategyV2.params.targetExposure"},{"name":"stop_loss_pct","type":"percent","default":0.02,"min":0.005,"max":0.2,"step":0.005,"labelKey":"strategyV2.params.stopLoss"},{"name":"trailing_activation_pct","type":"percent","default":0.05,"min":0.005,"max":0.5,"step":0.005,"labelKey":"strategyV2.params.trailingActivation"},{"name":"trailing_stop_pct","type":"percent","default":0.01,"min":0.005,"max":0.2,"step":0.005,"labelKey":"strategyV2.params.trailingDrawdown"}]}'::jsonb, '["strategy-v2","cta","ta-lib","macd","kdj","crypto","swap","risk"]'::jsonb, 'bar-chart', 'gold', 70, TRUE, '{"source":"system_seed","version":11,"apiVersion":2}'::jsonb, NOW()),

('strategy_v2_supertrend', 'script', 'SuperTrend', 'A configurable SPY SuperTrend strategy using ATR trailing bands.', $supertrend$"""
SuperTrend
ATR trailing bands define a stateful SPY trend regime.
"""

# @param atr_period int 10 range=2:100:1
# @param atr_multiplier float 3 range=0.5:10:0.25
# @param target_pct float 0.95 range=0.05:1:0.05

PERSIST_RUNTIME_STATE = True

def initialize(context):
    g.symbol = "USStock:SPY"
    g.trend = 0
    g.upper_band = None
    g.lower_band = None
    context.set_universe([g.symbol])
    context.set_benchmark(g.symbol)
    context.subscribe(frequency="1d")
    context.set_metadata(direction_mode="long_only")
    context.set_warmup(120)


def handle_data(context, data):
    atr_period = int(context.params.get("atr_period", 10))
    multiplier = float(context.params.get("atr_multiplier", 3.0))
    target_pct = float(context.params.get("target_pct", 0.95))
    bars = get_history(atr_period + 3, "1d", ["high", "low", "close"], g.symbol)
    atr = indicator("ATR", g.symbol, timeperiod=atr_period)
    if len(bars) < atr_period + 2 or len(atr) < 2:
        return
    high = float(bars["high"].iloc[-1])
    low = float(bars["low"].iloc[-1])
    close = float(bars["close"].iloc[-1])
    previous_close = float(bars["close"].iloc[-2])
    atr_value = float(atr.iloc[-1])
    middle = (high + low) / 2.0
    basic_upper = middle + multiplier * atr_value
    basic_lower = middle - multiplier * atr_value
    previous_upper = float(g.upper_band) if g.upper_band is not None else basic_upper
    previous_lower = float(g.lower_band) if g.lower_band is not None else basic_lower
    g.upper_band = basic_upper if basic_upper < previous_upper or previous_close > previous_upper else previous_upper
    g.lower_band = basic_lower if basic_lower > previous_lower or previous_close < previous_lower else previous_lower
    if close > previous_upper:
        g.trend = 1
    elif close < previous_lower:
        g.trend = -1
    position = get_position(g.symbol)
    is_long = float(position.amount or 0.0) > 0
    if g.trend > 0 and not is_long:
        order_target_percent(g.symbol, target_pct, reason="supertrend_entry")
    elif g.trend < 0 and is_long:
        order_target_percent(g.symbol, 0.0, reason="supertrend_exit")
$supertrend$, '{"params":[{"name":"atr_period","type":"integer","default":10,"min":2,"max":100,"step":1,"labelKey":"strategyV2.params.atrPeriod"},{"name":"atr_multiplier","type":"number","default":3,"min":0.5,"max":10,"step":0.25,"labelKey":"strategyV2.params.atrMultiplier"},{"name":"target_pct","type":"percent","default":0.95,"min":0.05,"max":1,"step":0.05,"labelKey":"strategyV2.params.targetPosition"}]}'::jsonb, '["strategy-v2","cta","supertrend","atr","us-stock"]'::jsonb, 'stock', 'lime', 80, TRUE, '{"source":"system_seed","version":11,"apiVersion":2}'::jsonb, NOW()),

('strategy_v2_market_cap_barbell', 'portfolio_strategy', 'Small and Large Cap Barbell', 'A weekly cross-sectional portfolio combining small and large eligible U.S. companies.', $marketcap$"""
Small and Large Cap Barbell
Weekly point-in-time market-cap barbell with a profitability filter.
"""

# @param per_side int 3 range=1:6:1
# @param min_roe float 0 range=-1:1:0.01
# @param max_weight float 0.2 range=0.05:1:0.05

def initialize(context):
    g.universe = [
        "USStock:AAPL", "USStock:MSFT", "USStock:NVDA", "USStock:AMZN", "USStock:META",
        "USStock:GOOGL", "USStock:AVGO", "USStock:COST", "USStock:JPM", "USStock:XOM",
    ]
    context.set_universe(g.universe)
    context.set_benchmark("USStock:SPY")
    context.subscribe(frequency="1d")
    context.set_metadata(direction_mode="long_only")
    context.set_warmup(10)
    run_weekly(rebalance, weekday=1, time="09:35")


def rebalance(context, data):
    per_side = int(context.params.get("per_side", 3))
    min_roe = float(context.params.get("min_roe", 0.0))
    max_weight = float(context.params.get("max_weight", 0.2))
    symbols = list(g.universe)
    fundamentals = get_fundamentals(["MARKET_CAP", "ROE"], symbols)
    if fundamentals.empty:
        return
    eligible = fundamentals.dropna(subset=["MARKET_CAP"])
    if "ROE" in eligible.columns:
        eligible = eligible[(eligible["ROE"].isna()) | (eligible["ROE"] >= min_roe)]
    ranking = eligible.sort_values("MARKET_CAP")
    selected = list(dict.fromkeys(list(ranking.head(per_side).index) + list(ranking.tail(per_side).index)))
    for symbol in get_positions().keys():
        if symbol not in selected:
            order_target_percent(symbol, 0.0, reason="market_cap_removed")
    weight = min(max_weight, 1.0 / len(selected)) if selected else 0.0
    for symbol in selected:
        order_target_percent(symbol, weight, reason="market_cap_barbell")
$marketcap$, '{"params":[{"name":"per_side","type":"integer","default":3,"min":1,"max":6,"step":1,"labelKey":"strategyV2.params.perSide"},{"name":"min_roe","type":"number","default":0,"min":-1,"max":1,"step":0.01,"labelKey":"strategyV2.params.minRoe"},{"name":"max_weight","type":"percent","default":0.2,"min":0.05,"max":1,"step":0.05,"labelKey":"strategyV2.params.maxWeight"}]}'::jsonb, '["strategy-v2","portfolio","cross-sectional","fundamental","market-cap"]'::jsonb, 'appstore', 'geekblue', 110, TRUE, '{"source":"system_seed","version":11,"apiVersion":2}'::jsonb, NOW()),

('strategy_v2_momentum_top_n', 'portfolio_strategy', 'Momentum Top-N Rotation', 'A weekly U.S. stock portfolio selecting the strongest trailing momentum.', $momentum$"""
Momentum Top-N Rotation
Weekly cross-sectional rotation into the strongest trailing momentum names.
"""

# @param lookback int 60 range=10:250:5
# @param top_n int 4 range=1:10:1
# @param max_weight float 0.25 range=0.05:1:0.05

def initialize(context):
    g.universe = [
        "USStock:AAPL", "USStock:MSFT", "USStock:NVDA", "USStock:AMZN", "USStock:META",
        "USStock:GOOGL", "USStock:AVGO", "USStock:COST", "USStock:JPM", "USStock:XOM",
    ]
    context.set_universe(g.universe)
    context.set_benchmark("USStock:SPY")
    context.subscribe(frequency="1d")
    context.set_metadata(direction_mode="long_only")
    context.set_warmup(260)
    run_weekly(rebalance, weekday=1, time="09:35")


def rebalance(context, data):
    lookback = int(context.params.get("lookback", 60))
    top_n = int(context.params.get("top_n", 4))
    max_weight = float(context.params.get("max_weight", 0.25))
    scores = {}
    for symbol in g.universe:
        bars = get_history(lookback + 1, "1d", "close", symbol)
        if len(bars) < lookback + 1:
            continue
        first = float(bars["close"].iloc[0])
        last = float(bars["close"].iloc[-1])
        if first > 0:
            scores[symbol] = last / first - 1.0
    selected = [symbol for symbol, score in sorted(scores.items(), key=lambda item: item[1], reverse=True)[:top_n] if score > 0]
    for symbol in get_positions().keys():
        if symbol not in selected:
            order_target_percent(symbol, 0.0, reason="momentum_removed")
    weight = min(max_weight, 1.0 / len(selected)) if selected else 0.0
    for symbol in selected:
        order_target_percent(symbol, weight, reason="momentum_top_n")
$momentum$, '{"params":[{"name":"lookback","type":"integer","default":60,"min":10,"max":250,"step":5,"labelKey":"strategyV2.params.lookback"},{"name":"top_n","type":"integer","default":4,"min":1,"max":10,"step":1,"labelKey":"strategyV2.params.topN"},{"name":"max_weight","type":"percent","default":0.25,"min":0.05,"max":1,"step":0.05,"labelKey":"strategyV2.params.maxWeight"}]}'::jsonb, '["strategy-v2","portfolio","cross-sectional","momentum","rotation"]'::jsonb, 'rocket', 'blue', 120, TRUE, '{"source":"system_seed","version":11,"apiVersion":2}'::jsonb, NOW()),

('strategy_v2_low_volatility', 'portfolio_strategy', 'Low Volatility Rotation', 'A weekly U.S. stock portfolio selecting the lowest realized volatility names.', $lowvol$"""
Low Volatility Rotation
Weekly cross-sectional rotation into the lowest realized volatility names.
"""

# @param lookback int 60 range=10:250:5
# @param top_n int 4 range=1:10:1
# @param max_weight float 0.25 range=0.05:1:0.05

def initialize(context):
    g.universe = [
        "USStock:AAPL", "USStock:MSFT", "USStock:NVDA", "USStock:AMZN", "USStock:META",
        "USStock:GOOGL", "USStock:AVGO", "USStock:COST", "USStock:JPM", "USStock:XOM",
    ]
    context.set_universe(g.universe)
    context.set_benchmark("USStock:SPY")
    context.subscribe(frequency="1d")
    context.set_metadata(direction_mode="long_only")
    context.set_warmup(260)
    run_weekly(rebalance, weekday=1, time="09:35")


def rebalance(context, data):
    lookback = int(context.params.get("lookback", 60))
    top_n = int(context.params.get("top_n", 4))
    max_weight = float(context.params.get("max_weight", 0.25))
    scores = {}
    for symbol in g.universe:
        bars = get_history(lookback + 1, "1d", "close", symbol)
        if len(bars) < lookback + 1:
            continue
        returns = bars["close"].pct_change().dropna()
        if len(returns):
            scores[symbol] = float(returns.std())
    selected = [symbol for symbol, _ in sorted(scores.items(), key=lambda item: item[1])[:top_n]]
    for symbol in get_positions().keys():
        if symbol not in selected:
            order_target_percent(symbol, 0.0, reason="low_vol_removed")
    weight = min(max_weight, 1.0 / len(selected)) if selected else 0.0
    for symbol in selected:
        order_target_percent(symbol, weight, reason="low_volatility")
$lowvol$, '{"params":[{"name":"lookback","type":"integer","default":60,"min":10,"max":250,"step":5,"labelKey":"strategyV2.params.lookback"},{"name":"top_n","type":"integer","default":4,"min":1,"max":10,"step":1,"labelKey":"strategyV2.params.topN"},{"name":"max_weight","type":"percent","default":0.25,"min":0.05,"max":1,"step":0.05,"labelKey":"strategyV2.params.maxWeight"}]}'::jsonb, '["strategy-v2","portfolio","cross-sectional","low-volatility","rotation"]'::jsonb, 'safety', 'cyan', 130, TRUE, '{"source":"system_seed","version":11,"apiVersion":2}'::jsonb, NOW()),

('strategy_v2_quality_growth', 'portfolio_strategy', 'Quality Growth Multi-Factor', 'A weekly point-in-time portfolio combining profitability, growth, and balance-sheet quality.', $quality$"""
Quality Growth Multi-Factor
Weekly point-in-time ranking by profitability, growth, and balance-sheet quality.
"""

# @param top_n int 5 range=1:10:1
# @param min_roe float 0.1 range=-1:1:0.01
# @param min_growth float 0 range=-1:5:0.01
# @param max_debt_to_equity float 2 range=0:10:0.1
# @param max_weight float 0.2 range=0.05:1:0.05

def initialize(context):
    g.universe = [
        "USStock:AAPL", "USStock:MSFT", "USStock:NVDA", "USStock:AMZN", "USStock:META",
        "USStock:GOOGL", "USStock:AVGO", "USStock:COST", "USStock:JPM", "USStock:XOM",
    ]
    context.set_universe(g.universe)
    context.set_benchmark("USStock:SPY")
    context.subscribe(frequency="1d")
    context.set_metadata(direction_mode="long_only")
    context.set_warmup(10)
    run_weekly(rebalance, weekday=1, time="09:35")


def rebalance(context, data):
    top_n = int(context.params.get("top_n", 5))
    min_roe = float(context.params.get("min_roe", 0.1))
    min_growth = float(context.params.get("min_growth", 0.0))
    max_debt = float(context.params.get("max_debt_to_equity", 2.0))
    max_weight = float(context.params.get("max_weight", 0.2))
    symbols = list(g.universe)
    factors = get_fundamentals(["ROE", "REVENUE_GROWTH", "DEBT_TO_EQUITY"], symbols)
    if factors.empty:
        return
    eligible = factors.dropna(subset=["ROE", "REVENUE_GROWTH", "DEBT_TO_EQUITY"])
    eligible = eligible[(eligible["ROE"] >= min_roe) & (eligible["REVENUE_GROWTH"] >= min_growth) & (eligible["DEBT_TO_EQUITY"] <= max_debt)]
    if eligible.empty:
        selected = []
    else:
        score = eligible["ROE"].rank(pct=True) + eligible["REVENUE_GROWTH"].rank(pct=True) - eligible["DEBT_TO_EQUITY"].rank(pct=True)
        selected = list(score.sort_values(ascending=False).head(top_n).index)
    for symbol in get_positions().keys():
        if symbol not in selected:
            order_target_percent(symbol, 0.0, reason="quality_removed")
    weight = min(max_weight, 1.0 / len(selected)) if selected else 0.0
    for symbol in selected:
        order_target_percent(symbol, weight, reason="quality_growth")
$quality$, '{"params":[{"name":"top_n","type":"integer","default":5,"min":1,"max":10,"step":1,"labelKey":"strategyV2.params.topN"},{"name":"min_roe","type":"number","default":0.1,"min":-1,"max":1,"step":0.01,"labelKey":"strategyV2.params.minRoe"},{"name":"min_growth","type":"number","default":0,"min":-1,"max":5,"step":0.01,"labelKey":"strategyV2.params.minGrowth"},{"name":"max_debt_to_equity","type":"number","default":2,"min":0,"max":10,"step":0.1,"labelKey":"strategyV2.params.maxDebtToEquity"},{"name":"max_weight","type":"percent","default":0.2,"min":0.05,"max":1,"step":0.05,"labelKey":"strategyV2.params.maxWeight"}]}'::jsonb, '["strategy-v2","portfolio","cross-sectional","fundamental","quality","growth"]'::jsonb, 'radar-chart', 'purple', 140, TRUE, '{"source":"system_seed","version":11,"apiVersion":2}'::jsonb, NOW()),
('strategy_v2_rapid_accel', 'portfolio_strategy', 'Rapid Acceleration', 'A 1m HA reversal followed by three accelerating, near-wickless crypto swap candles.', $rapidaccel$"""Native Strategy API V2 example: HA reversal followed by accelerating candles.

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
$rapidaccel$, '{"params":[{"name":"adx_length","type":"integer","default":14,"min":5,"max":40,"step":1,"labelKey":"strategyV2.params.adx_length"},{"name":"adx_min","type":"number","default":20,"min":5,"max":50,"step":1,"labelKey":"strategyV2.params.adx_min"},{"name":"wick_tolerance","type":"number","default":0.15,"min":0.02,"max":0.5,"step":0.01,"labelKey":"strategyV2.params.wick_tolerance"},{"name":"atr_length","type":"integer","default":14,"min":5,"max":50,"step":1,"labelKey":"strategyV2.params.atr_length"},{"name":"stop_multiplier","type":"number","default":1.8,"min":0.5,"max":6,"step":0.1,"labelKey":"strategyV2.params.stop_multiplier"},{"name":"reward_risk","type":"number","default":2,"min":0.5,"max":5,"step":0.25,"labelKey":"strategyV2.params.reward_risk"},{"name":"target_pct","type":"percent","default":0.25,"min":0.05,"max":1,"step":0.05,"labelKey":"strategyV2.params.target_pct"}]}'::jsonb, '["strategy-v2","cta","crypto","swap","one-way","1m","momentum"]'::jsonb, 'bolt', 'orange', 150, TRUE, '{"source":"system_seed","version":13,"apiVersion":2,"executionMode":"signal","researchStatus":"exploratory_defaults"}'::jsonb, NOW()),

('strategy_v2_trend_flip', 'portfolio_strategy', 'Trend Flip', '5m SuperTrend direction-flip events gated by ADX, Choppiness, and ATR-normalized risk.', $trendflip$"""Native Strategy API V2 example: event-only SuperTrend flips."""

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
$trendflip$, '{"params":[{"name":"st_atr_length","type":"integer","default":10,"min":5,"max":50,"step":1,"labelKey":"strategyV2.params.st_atr_length"},{"name":"st_factor","type":"number","default":3,"min":1,"max":8,"step":0.25,"labelKey":"strategyV2.params.st_factor"},{"name":"adx_length","type":"integer","default":14,"min":5,"max":40,"step":1,"labelKey":"strategyV2.params.adx_length"},{"name":"adx_min","type":"number","default":20,"min":5,"max":50,"step":1,"labelKey":"strategyV2.params.adx_min"},{"name":"chop_length","type":"integer","default":14,"min":5,"max":50,"step":1,"labelKey":"strategyV2.params.chop_length"},{"name":"chop_max","type":"number","default":61.8,"min":40,"max":75,"step":0.5,"labelKey":"strategyV2.params.chop_max"},{"name":"stop_multiplier","type":"number","default":2,"min":0.5,"max":6,"step":0.25,"labelKey":"strategyV2.params.stop_multiplier"},{"name":"reward_risk","type":"number","default":2,"min":0.5,"max":5,"step":0.25,"labelKey":"strategyV2.params.reward_risk"},{"name":"max_stop_pct","type":"percent","default":0.04,"min":0.005,"max":0.15,"step":0.005,"labelKey":"strategyV2.params.max_stop_pct"},{"name":"target_pct","type":"percent","default":0.25,"min":0.05,"max":1,"step":0.05,"labelKey":"strategyV2.params.target_pct"}]}'::jsonb, '["strategy-v2","cta","crypto","swap","one-way","5m","supertrend","adx","chop"]'::jsonb, 'fund', 'lime', 160, TRUE, '{"source":"system_seed","version":13,"apiVersion":2,"executionMode":"signal","researchStatus":"exploratory_defaults"}'::jsonb, NOW()),

('strategy_v2_sweep_absorption', 'portfolio_strategy', 'Sweep Absorption', '5m confirmed-pivot liquidity sweeps with an OHLCV rejection/absorption proxy and 1m confirmation.', $sweepabsorption$"""Native Strategy API V2 example: confirmed-pivot sweep and absorption proxy."""

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
$sweepabsorption$, '{"params":[{"name":"pivot_length","type":"integer","default":3,"min":2,"max":10,"step":1,"labelKey":"strategyV2.params.pivot_length"},{"name":"rvol_lookback","type":"integer","default":20,"min":5,"max":100,"step":1,"labelKey":"strategyV2.params.rvol_lookback"},{"name":"min_relative_volume","type":"number","default":1.5,"min":1,"max":5,"step":0.1,"labelKey":"strategyV2.params.min_relative_volume"},{"name":"min_sweep_depth_atr","type":"number","default":0.15,"min":0.05,"max":2,"step":0.05,"labelKey":"strategyV2.params.min_sweep_depth_atr"},{"name":"reclaim_threshold","type":"number","default":0.5,"min":0.1,"max":1,"step":0.05,"labelKey":"strategyV2.params.reclaim_threshold"},{"name":"atr_length","type":"integer","default":14,"min":5,"max":50,"step":1,"labelKey":"strategyV2.params.atr_length"},{"name":"atr_stop_buffer","type":"number","default":0.5,"min":0.1,"max":3,"step":0.1,"labelKey":"strategyV2.params.atr_stop_buffer"},{"name":"reward_risk","type":"number","default":2,"min":0.5,"max":5,"step":0.25,"labelKey":"strategyV2.params.reward_risk"},{"name":"target_pct","type":"percent","default":0.25,"min":0.05,"max":1,"step":0.05,"labelKey":"strategyV2.params.target_pct"}]}'::jsonb, '["strategy-v2","cta","crypto","swap","one-way","5m","1m","sweep","absorption-proxy"]'::jsonb, 'radar-chart', 'purple', 170, TRUE, '{"source":"system_seed","version":13,"apiVersion":2,"executionMode":"signal","researchStatus":"exploratory_defaults"}'::jsonb, NOW())
ON CONFLICT (template_key) DO UPDATE SET
    asset_type = EXCLUDED.asset_type,
    title = EXCLUDED.title,
    description = EXCLUDED.description,
    code = EXCLUDED.code,
    param_schema = EXCLUDED.param_schema,
    tags = EXCLUDED.tags,
    icon = EXCLUDED.icon,
    accent = EXCLUDED.accent,
    sort_order = EXCLUDED.sort_order,
    is_active = TRUE,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();
