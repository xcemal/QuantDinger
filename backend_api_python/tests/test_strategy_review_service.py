from app.services import strategy_review as module


def test_ai_review_accepts_custom_provider_without_api_key(monkeypatch):
    class Provider:
        value = "custom"

    class LocalLLM:
        provider = Provider()

        def get_default_model(self, provider=None):
            return "codex-local"

        def get_api_key(self, provider=None):
            return ""

        def is_configured(self, provider=None):
            return True

        def safe_call_llm(self, **kwargs):
            return {
                "summary": "Local review completed.",
                "diagnosis": ["The local provider returned a structured result."],
                "recommendations": ["Keep the review evidence-based."],
                "cautions": ["Review does not change strategy parameters."],
                "report": "Local review completed.",
            }

    monkeypatch.setattr(module, "LLMService", LocalLLM)
    service = module.StrategyReviewService()

    result = service._build_ai_review(
        base_report={
            "strategy": {"id": 7, "name": "Trend Flip"},
            "metrics": {},
            "diagnostics": [],
            "recommendations": [],
        },
        language="en-US",
    )

    assert result["status"] == "ok"
    assert result["source"] == "llm"
    assert result["provider"] == "custom"
    assert result["model"] == "codex-local"
    assert result["error"] == ""


def test_review_evidence_keeps_symbol_side_reason_and_jev_fields():
    service = module.StrategyReviewService()
    evidence = service._build_review_evidence(
        trades=[
            {"symbol": "DOGE/USDT", "type": "open_short", "profit": None},
            {"symbol": "DOGE/USDT", "type": "close_short", "profit": -12.5, "close_reason": "server_stop_loss"},
        ],
        positions=[],
        ai_decisions=[
            {
                "id": 9,
                "symbol": "DOGE/USDT",
                "action": "open_short",
                "provider": "jev",
                "model": "~typesafe/jev-latest",
                "decision": "reject",
                "allowed": False,
                "confidence": 0.47,
                "reason": "jev_entry_rejected:confidence_below_threshold",
                "fallback_reason": "threshold=0.550",
                "latency_ms": 700,
                "created_at": 0,
                "probabilities_json": {"pass": 0.74, "reject": 0.26},
                "checks_json": [{"name": "entry_decision", "result": "pass", "confidence": 0.47}],
                "request_snapshot": {
                    "action": "open_short",
                    "symbol": "DOGE/USDT",
                    "reference_price": 0.09,
                    "signal_reason": "TREND_FLIP|direction=SHORT|reward_risk=2.0",
                    "context": {
                        "order_budget": {"side": "short"},
                        "protection": {"stop_loss_pct": 0.01, "take_profit_pct": 0.02},
                        "market_evidence": {
                            "data_quality": "partial",
                            "primary_timeframe": "5m",
                            "timeframes": {"5m": {"trend": "downtrend", "atr14_pct": 0.6}},
                        },
                    },
                },
            }
        ],
        strategy_source={"name": "Trend Flip", "code": "signal()"},
    )

    symbol = evidence["by_symbol"][0]
    assert symbol["symbol"] == "DOGE/USDT"
    assert symbol["losses"] == 1
    assert symbol["stop_loss_exits"] == 1
    assert evidence["ai_summary"]["jev_rejected"] == 1
    assert evidence["ai_decisions"][0]["signal_reason"].startswith("TREND_FLIP|")
    assert evidence["ai_decisions"][0]["market"]["atr_pct"] == 0.6


def test_rule_review_supports_turkish_output():
    service = module.StrategyReviewService()
    diagnostics, recommendations = service._build_rule_review(
        metrics={
            "closed_trades_with_pnl": 1,
            "window_net_pnl": -10,
            "performance_total_return_pct": -1,
            "open_position_count": 0,
        },
        strategy={},
        trading_config={},
        bot_type="",
        language="tr-TR",
    )

    assert diagnostics[0]["title"] == "Örneklem hâlâ küçük"
    assert recommendations[0]["title"] == "Daha fazla kapanmış işlem biriktirin"
