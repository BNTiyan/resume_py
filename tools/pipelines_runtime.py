#!/usr/bin/env python3
"""
Utilities for CI/runtime pipeline splitting without committing generated configs.

Commands:
  - matrix: print a GitHub Actions matrix JSON ({"include":[...]}), grouped by selenium site "company"
  - write-config: write a per-company config JSON (narrowed selenium_options.sites + namespaced output)

Examples:
  python3 tools/pipelines_runtime.py matrix --config config.json
  python3 tools/pipelines_runtime.py write-config --config config.json --company "meta" --safe-name meta --out configs/pipelines/meta.json
"""

from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any, Dict, List


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _sanitize(name: str) -> str:
    s = (name or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "pipeline"


def _sites(master: Dict[str, Any]) -> List[Dict[str, Any]]:
    sites = (master.get("selenium_options") or {}).get("sites") or []
    if not isinstance(sites, list):
        return []
    out: List[Dict[str, Any]] = []
    for s in sites:
        if not isinstance(s, dict):
            continue
        url = (s.get("url") or "").strip()
        if not url:
            continue
        out.append(s)
    return out


def cmd_matrix(config_path: Path) -> int:
    master = _load_json(config_path)
    sites = _sites(master)
    if not sites:
        raise SystemExit("No selenium_options.sites found in config.json")

    groups: Dict[str, List[Dict[str, Any]]] = {}
    for s in sites:
        company = (s.get("company") or "").strip()
        key = company if company else _sanitize(s.get("url", ""))
        groups.setdefault(key, []).append(s)

    include = [{"safe_name": _sanitize(k), "company": k} for k in sorted(groups.keys(), key=_sanitize)]
    print(json.dumps({"include": include}))
    return 0


def cmd_write_config(config_path: Path, company: str, safe_name: str, out_path: Path) -> int:
    master = _load_json(config_path)
    sites = _sites(master)

    chosen: List[Dict[str, Any]] = [s for s in sites if (s.get("company") or "").strip() == company]
    if not chosen:
        # Fallback: match by sanitized company name (handles minor casing differences)
        chosen = [s for s in sites if _sanitize((s.get("company") or "").strip()) == _sanitize(safe_name)]

    if not chosen:
        raise SystemExit(f"No selenium sites found for company={company!r} safe_name={safe_name!r}")

    cfg = copy.deepcopy(master)
    cfg["companies"] = [company]
    cfg.setdefault("selenium_options", {})
    cfg["selenium_options"]["enabled"] = True
    cfg["selenium_options"]["sites"] = chosen

    # Namespace outputs per pipeline to avoid collisions
    out_block = cfg.get("output")
    if not isinstance(out_block, dict):
        out_block = {}
        cfg["output"] = out_block
    base_dir = out_block.get("dir") or "output"
    out_block["dir"] = str(Path(base_dir) / _sanitize(safe_name))
    base_prefix = out_block.get("prefix") or "matches"
    out_block["prefix"] = f"{base_prefix}_{_sanitize(safe_name)}"

    _write_json(out_path, cfg)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate CI pipeline matrix + per-company configs from config.json")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap_matrix = sub.add_parser("matrix", help="Print matrix JSON grouped by selenium site company")
    ap_matrix.add_argument("--config", required=True, help="Path to master config.json")

    ap_write = sub.add_parser("write-config", help="Write a per-company config JSON")
    ap_write.add_argument("--config", required=True, help="Path to master config.json")
    ap_write.add_argument("--company", required=True, help="Company key/name from selenium site config")
    ap_write.add_argument("--safe-name", required=True, help="Sanitized pipeline name for filenames")
    ap_write.add_argument("--out", required=True, help="Output path for generated config JSON")

    args = ap.parse_args()
    if args.cmd == "matrix":
        return cmd_matrix(Path(args.config))
    if args.cmd == "write-config":
        return cmd_write_config(Path(args.config), args.company, args.safe_name, Path(args.out))
    raise SystemExit("Unknown command")


if __name__ == "__main__":
    raise SystemExit(main())


