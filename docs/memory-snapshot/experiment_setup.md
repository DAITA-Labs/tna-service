---
name: TNA parser experiment setup (Python venv + deps)
description: Python venv location, dependency tracking, and how to run scripts for the TNA parser experiments
type: project
originSessionId: 659793e3-6c58-46b7-bff9-b72ea49f6602
---
Experiments run in Python with a venv at `F:\DAITA\ARENA\TNA\.venv`. Dependencies tracked in `F:\DAITA\ARENA\TNA\requirements.txt`. On Windows, invoke scripts with `.venv\Scripts\python.exe` rather than activating the venv.

**Why:** Project chose Python for M0/M1 because the agent-framework ecosystem (LangGraph, Pydantic AI, smolagents, etc.) is richest there. Production stack is Go (daita-tna-engine, excelize), but the port is post-experiment and not blocking M0/M1.

**How to apply:**
- Run scripts: `.venv\Scripts\python.exe path\to\script.py`
- Add deps: `.venv\Scripts\python.exe -m pip install <pkg>` then refresh `requirements.txt` with `pip freeze`
- Currently installed (as of 2026-05-07): openpyxl 3.1.5, et_xmlfile 2.0.0
