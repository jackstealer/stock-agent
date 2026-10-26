# Stock Agent

A self-improving stock market agent built with MLOps/LLMOps practices.

## Status
Early development. Currently building: data pipeline + cost-aware backtester.

## Goals
- Honest evaluation (net of costs, walk-forward, locked test set)
- Safety first (risk layer, kill switch, paper trading before live)
- Reproducible and monitored

## Setup
    python -m venv .venv
    .venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    copy .env.example .env
