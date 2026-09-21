"""Tests for godcode.spirit.SpiritEngine (spec section 7)."""

from godcode.spirit import SpiritEngine


def test_classify_returns_expected_keys():
    engine = SpiritEngine()
    result = engine.classify("Deploy smart contract")
    assert set(result) == {"intent", "confidence", "spiritual_intent", "suggestion", "keywords"}
    assert 0.0 <= result["confidence"] <= 1.0
    assert isinstance(result["keywords"], list)


def test_known_dataset_row_classifies_sanely():
    engine = SpiritEngine()
    result = engine.classify("Deploy smart contract")
    assert result["intent"] == "Deploy smart contract"
    assert result["confidence"] > 0
    assert "contract" in result["keywords"]
    assert result["spiritual_intent"] == "Manifest a redemptive contract"
    assert result["suggestion"] == "REFLECT on contract values"


def test_prophecy_row_classifies_sanely():
    engine = SpiritEngine()
    result = engine.classify("Foresee the success of a divine mission")
    assert result["intent"] == "Forecast future outcome"


def test_empty_input_falls_back_to_silent_contemplation():
    engine = SpiritEngine()
    result = engine.classify("")
    assert result == {
        "intent": "Silent contemplation",
        "confidence": 0.0,
        "spiritual_intent": "The Spirit is quiet on this matter.",
        "suggestion": "BREATHE and try again.",
        "keywords": [],
    }


def test_gibberish_input_falls_back_to_silent_contemplation():
    engine = SpiritEngine()
    result = engine.classify("xqzwk blarg zzzfnord")
    assert result["intent"] == "Silent contemplation"
    assert result["confidence"] == 0.0
    assert result["keywords"] == []


def test_prophesy_returns_divine_forecast_mentioning_intent():
    engine = SpiritEngine()
    text = "Deploy smart contract\nDeploy a contract for the people\nForecast future outcome"
    forecast = engine.prophesy(text)
    assert isinstance(forecast, str) and forecast.strip()
    assert "Deploy smart contract" in forecast  # dominant intent
    assert "%" in forecast  # average confidence
    assert "REFLECT on contract values" in forecast  # top suggestion


def test_prophesy_on_empty_text_still_speaks():
    engine = SpiritEngine()
    forecast = engine.prophesy("")
    assert isinstance(forecast, str) and forecast.strip()
    assert "Silent contemplation" in forecast
