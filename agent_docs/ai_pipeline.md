# AI Pipeline Documentation

> Last updated: January 2026
> Read this when: working on AI extraction, strategy scoring, code generation

## AI Providers & Models

### Multi-Provider Architecture

The project supports multiple AI providers with automatic fallback:

```
┌─────────────────────────────────────────┐
│            AI Provider Selection         │
│                                          │
│  GLM-4.7 (Zhipu AI)  ← Primary (code)   │
│         ↓ fallback                       │
│  GPT-4o-mini (OpenAI) ← Secondary       │
│         ↓ fallback                       │
│  Claude Sonnet       ← Last resort       │
└─────────────────────────────────────────┘
```

### Model Pricing (per 1M tokens)

| Model | Input | Output | Best For |
|-------|-------|--------|----------|
| `glm-4.7` | $0.11 | $0.28 | Code generation, Pine↔Python |
| `gpt-4o-mini` | $0.15 | $0.60 | Text analysis, classification |
| `claude-3-5-sonnet` | $3.00 | $15.00 | Complex reasoning |

### API Configuration

Keys loaded from `config/secrets.yaml`:

```yaml
# OpenAI
openai_api_key: "sk-..."

# GLM (Zhipu AI) - Priority for code tasks
glm_api_key: "..."
# or
zhipu_api_key: "..."

# GLM endpoint
# https://api.z.ai/api/paas/v4 (OpenAI-compatible)
```

---

## Two-Stage Strategy Extraction Pipeline

**File:** `src/scraper/ai_extractor.py`  
**Model:** GPT-4o-mini

### Stage 1: Classification
**Cost:** ~$0.00003/post

| Category | Action | Example |
|----------|--------|---------|
| `ACTIONABLE_STRATEGY` | → Stage 2 | "Buy when RSI<30, sell RSI>70" |
| `METHODOLOGY` | → Stage 2 | "How to trade SMC" |
| `INSIGHT` | → Stage 2 | "Fed rate impact analysis" |
| `POSITION_SHARE` | Skip | "Just went long AAPL" |
| `NOISE` | Skip | "New to trading, tips?" |

### Stage 2: Extraction
**Cost:** ~$0.0002/post

**Output schema:**
```python
{
    "strategy_name": str,
    "summary": str,
    "entry_rules": str,
    "exit_rules": str,
    "indicators": [{"name": str, "params": dict}],
    "timeframe": str,
    "markets": list,
    "tp_pct": float,
    "sl_pct": float,
    "ai_score": int,  # 0-100
    "ai_notes": str
}
```

### Pre-Filter (Zero-cost)

Before AI, regex pre-filter skips obvious noise:
- Checks for valuable keywords (entry, exit, backtest, sharpe, etc.)
- Detects code blocks, backtest results
- Returns `priority_score` (0-100)

---

## Pine Script ↔ Python Converter

**File:** `src/converter/ai_pine_converter.py`  
**Model:** GLM-4.7 (default, best for code)

### Usage

```python
from src.converter.ai_pine_converter import AIPineConverter

converter = AIPineConverter(model="glm-4.7")

# Pine to Python
result = converter.pine_to_python(pine_code)
print(result.converted_code)
print(f"Cost: ${result.cost_usd:.4f}")

# Python to Pine
result = converter.python_to_pine(python_code)
```

### Features

- **Bidirectional:** Pine → Python AND Python → Pine
- **Hybrid:** Rule-based fallback when AI unavailable
- **Validation:** Syntax check for both languages
- **Auto-fix:** `fix_code()` attempts to repair broken code

### Key Methods

| Method | Purpose |
|--------|---------|
| `pine_to_python(code)` | Convert Pine Script to Python |
| `python_to_pine(code)` | Convert Python to Pine Script |
| `fix_code(code, error)` | AI-powered code fixing |
| `validate_python(code)` | Check Python syntax |
| `validate_pine(code)` | Check Pine Script syntax |
| `get_stats()` | Get token usage stats |

---

## Scoring System

**Base:** 50 points

| Criteria | Bonus |
|----------|-------|
| Entry/exit defined | +15 |
| TP/SL specified | +10 |
| Backtest results mentioned | +15 |
| Repeatable/codeable | +10 |

**Thresholds:**
- ≥30: Acceptable
- ≥50: Good  
- ≥70: Excellent

---

## Key Files

| File | Purpose |
|------|---------|
| `src/scraper/ai_extractor.py` | Strategy extraction (GPT-4o-mini) |
| `src/converter/ai_pine_converter.py` | Code conversion (GLM-4.7) |
| `src/scraper/code_generator.py` | Strategy → Python |
| `src/scraper/strategy_storage.py` | SQLite operations |
| `src/scraper/reddit_collector.py` | Reddit data collection |
