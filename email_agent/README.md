# Email Agent

This module provides AI-powered email grading and response generation for the BYU-Pathway Worldwide email etiquette training simulator.

## Origin

This code is adapted from [tjkerby/email_agent](https://github.com/tjkerby/email_agent), modified for production deployment on Google Cloud Functions.

## Intentional Deviations from Original

| Change | Reason |
|--------|--------|
| `ChatOpenAI` instead of `OllamaLLM` | Production uses cloud-hosted GPT-4o (no local Ollama server) |
| Added `api_key` parameter to `EmailAgent.__init__` | Required for OpenAI API authentication |
| Package in `email_agent/` subdirectory | Cleaner separation for Cloud Function deployment |
| Renamed `scenarios.py` → `scenario_models.py` | Avoids collision with `scenarios/` directory |

## Key Files

- `email_agent.py` - Main agent class with LLM chains
- `scenario_models.py` - Scenario dataclass definition  
- `rubric.py` - Rubric items and global default rubric
- `scenario_loader.py` / `rubric_loader.py` - JSON file loaders
- `scenarios/` - Pre-built training scenarios (JSON)
- `rubrics/` - Grading rubric definitions (JSON)
