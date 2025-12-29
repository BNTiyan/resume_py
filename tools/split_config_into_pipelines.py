#!/usr/bin/env python3
"""
Generate smaller per-company pipeline config JSONs from a single config.json.

Why:
  Running one giant config across many Selenium sites often hits platform timeouts.
  Splitting the config lets you run/schedule each company as a separate pipeline.

Example:
  python3 tools/split_config_into_pipelines.py --config config.json --out-dir configs/pipelines
"""

from __future__ import annotations

import argparse
import copy
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _sanitize(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "pipeline"


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _group_sites_by_company(sites: List[Any]) -> Dict[str, List[Dict[str, Any]]]:
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for s in sites:
        if not isinstance(s, dict):
            continue
        url = (s.get("url") or "").strip()
        if not url:
            continue
        company = (s.get("company") or "").strip()
        key = company if company else _sanitize(url)
        groups[key].append(s)
    return dict(groups)


def _apply_output_namespacing(cfg: Dict[str, Any], key: str) -> None:
    safe = _sanitize(key)
    out = cfg.get("output")
    if not isinstance(out, dict):
        cfg["output"] = {"dir": f"output/{safe}", "prefix": f"matches_{safe}"}
        return
    base_dir = out.get("dir") or "output"
    out["dir"] = str(Path(base_dir) / safe)
    base_prefix = out.get("prefix") or "matches"
    out["prefix"] = f"{base_prefix}_{safe}"


def build_pipeline_config(master: Dict[str, Any], company_key: str, sites: List[Dict[str, Any]]) -> Dict[str, Any]:
    cfg = copy.deepcopy(master)

    # Narrow the run to just one company/site-group to keep runtime bounded.
    cfg["companies"] = [company_key]

    selenium_options = cfg.get("selenium_options")
    if not isinstance(selenium_options, dict):
        selenium_options = {}
        cfg["selenium_options"] = selenium_options
    selenium_options["enabled"] = True
    selenium_options["sites"] = sites

    _apply_output_namespacing(cfg, company_key)
    return cfg


def main() -> int:
    ap = argparse.ArgumentParser(description="Split config.json into smaller per-company pipeline configs.")
    ap.add_argument("--config", default="config.json", help="Path to the master config.json")
    ap.add_argument("--out-dir", default="configs/pipelines", help="Output directory for generated configs")
    ap.add_argument(
        "--write-runner",
        action="store_true",
        help="Also write a simple runner script per pipeline under pipelines/generated/",
    )
    args = ap.parse_args()

    # Keep paths repo-relative when possible so generated manifest/config references
    # work both locally and in CI (GitHub Actions runner).
    config_path = Path(args.config)
    out_dir = Path(args.out_dir)

    if not config_path.exists():
        raise SystemExit(f"Config not found: {config_path}")

    master = _load_json(config_path)
    sites = master.get("selenium_options", {}).get("sites", [])
    groups = _group_sites_by_company(sites if isinstance(sites, list) else [])

    if not groups:
        raise SystemExit("No selenium_options.sites found to split.")

    manifest: List[Dict[str, Any]] = []
    for company_key, company_sites in sorted(groups.items(), key=lambda kv: _sanitize(kv[0])):
        safe = _sanitize(company_key)
        cfg = build_pipeline_config(master, company_key, company_sites)
        cfg_path = out_dir / f"{safe}.json"
        _write_json(cfg_path, cfg)

        manifest.append(
            {
                "company": company_key,
                "safe_name": safe,
                "config": cfg_path.as_posix(),
                "site_count": len(company_sites),
            }
        )

        if args.write_runner:
            runner_dir = config_path.parent / "pipelines" / "generated"
            runner_dir.mkdir(parents=True, exist_ok=True)
            sh_path = runner_dir / f"run_{safe}.sh"
            # Runner should also be repo-relative.
            rel_cfg_path = cfg_path.as_posix()
            sh_path.write_text(
                "\n".join(
                    [
                        "#!/bin/bash",
                        "set -euo pipefail",
                        "",
                        'DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/../.." && pwd )"',
                        'cd "$DIR"',
                        f'./run_pipeline.sh "{rel_cfg_path}"',
                        "",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

    _write_json(out_dir / "manifest.json", {"master_config": config_path.as_posix(), "pipelines": manifest})
    print(f"✅ Wrote {len(manifest)} pipeline configs to: {out_dir}")
    print(f"🧾 Manifest: {out_dir / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


