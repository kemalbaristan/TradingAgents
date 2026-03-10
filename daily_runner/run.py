#!/usr/bin/env python3
"""Daily stock recommendation runner.

Usage:
    # Run with defaults (reads daily_runner/watchlist.yaml)
    python -m daily_runner.run

    # Override watchlist config
    python -m daily_runner.run --config path/to/watchlist.yaml

    # Analyse specific tickers only (ignores watchlist file)
    python -m daily_runner.run --tickers AAPL MSFT NVDA

    # Override the analysis date (default: today)
    python -m daily_runner.run --date 2026-03-10
"""

import argparse
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import yaml
from dotenv import load_dotenv

# Ensure project root is on sys.path so imports work when invoked directly
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph

from daily_runner.report_formatter import format_daily_report, save_report
from daily_runner.notifier import send_email_report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_watchlist_config(config_path: str) -> Dict[str, Any]:
    """Load and return the YAML watchlist config."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def build_ta_config(wl_cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Merge watchlist YAML overrides into the TradingAgents DEFAULT_CONFIG."""
    config = DEFAULT_CONFIG.copy()

    llm = wl_cfg.get("llm", {})
    if llm.get("provider"):
        config["llm_provider"] = llm["provider"]
    if llm.get("deep_think_model"):
        config["deep_think_llm"] = llm["deep_think_model"]
    if llm.get("quick_think_model"):
        config["quick_think_llm"] = llm["quick_think_model"]
    if llm.get("backend_url"):
        config["backend_url"] = llm["backend_url"]

    analysis = wl_cfg.get("analysis", {})
    if analysis.get("max_debate_rounds") is not None:
        config["max_debate_rounds"] = analysis["max_debate_rounds"]
    if analysis.get("max_risk_discuss_rounds") is not None:
        config["max_risk_discuss_rounds"] = analysis["max_risk_discuss_rounds"]

    vendors = wl_cfg.get("data_vendors", {})
    if vendors:
        config["data_vendors"] = {**config["data_vendors"], **vendors}

    return config


def analyse_ticker(
    ta: TradingAgentsGraph,
    ticker: str,
    trade_date: str,
) -> Dict[str, Any]:
    """Run the full TradingAgents pipeline for one ticker.

    Returns a dict with keys: ticker, state, decision, error.
    """
    try:
        state, decision = ta.propagate(ticker, trade_date)
        return {"ticker": ticker, "state": state, "decision": decision}
    except Exception as exc:
        tb = traceback.format_exc()
        return {"ticker": ticker, "state": {}, "decision": "", "error": f"{exc}\n{tb}"}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Daily stock recommendation runner")
    parser.add_argument(
        "--config",
        default=str(Path(__file__).resolve().parent / "watchlist.yaml"),
        help="Path to watchlist YAML config (default: daily_runner/watchlist.yaml)",
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        help="Override: analyse only these tickers",
    )
    parser.add_argument(
        "--date",
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Trade date in YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode (verbose LLM output)",
    )
    args = parser.parse_args()

    # Load env vars (.env file at project root)
    load_dotenv(Path(_PROJECT_ROOT) / ".env")

    # Load config
    wl_cfg = load_watchlist_config(args.config)
    ta_config = build_ta_config(wl_cfg)
    selected_analysts = wl_cfg.get("analysis", {}).get(
        "selected_analysts", ["market", "social", "news", "fundamentals"]
    )

    tickers = args.tickers or wl_cfg.get("watchlist", [])
    if not tickers:
        print("No tickers specified. Add them to watchlist.yaml or pass --tickers.")
        sys.exit(1)

    trade_date = args.date
    print(f"\n=== Daily Stock Recommender — {trade_date} ===")
    print(f"Tickers: {', '.join(tickers)}")
    print(f"LLM: {ta_config['llm_provider']} / {ta_config['deep_think_llm']}\n")

    # Initialise the graph once, reuse across tickers
    ta = TradingAgentsGraph(
        selected_analysts=selected_analysts,
        debug=args.debug,
        config=ta_config,
    )

    results: List[Dict[str, Any]] = []
    for i, ticker in enumerate(tickers, 1):
        print(f"[{i}/{len(tickers)}] Analysing {ticker} …")
        result = analyse_ticker(ta, ticker, trade_date)
        results.append(result)

        if result.get("error"):
            print(f"  ERROR: {result['error'][:120]}")
        else:
            print(f"  Recommendation: {result['decision'].strip().upper()}")

    # Build report
    report = format_daily_report(results, trade_date)

    # Print to console
    print(report)

    # Save to disk
    output_cfg = wl_cfg.get("output", {})
    reports_dir = output_cfg.get("reports_dir", "./daily_reports")
    saved = save_report(
        report,
        results,
        trade_date,
        reports_dir,
        save_json=output_cfg.get("save_json", True),
        save_text=output_cfg.get("save_text", True),
    )
    for kind, path in saved.items():
        print(f"  Saved {kind} report: {path}")

    # Email notification
    email_cfg = wl_cfg.get("email", {})
    if email_cfg.get("enabled") and email_cfg.get("smtp_server"):
        try:
            send_email_report(report, trade_date, email_cfg)
            print("  Email sent successfully.")
        except Exception as exc:
            print(f"  Email failed: {exc}")

    print("\nDone.")


if __name__ == "__main__":
    main()
