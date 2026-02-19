#!/usr/bin/env python3
"""
QuickApply — one-command launcher

Usage:
    python run.py              # start on port 5000
    python run.py --port 8080  # custom port
    python run.py --no-browser # don't open browser automatically
"""
import argparse
import os
import subprocess
import sys
import webbrowser
from pathlib import Path
from threading import Timer


ROOT = Path(__file__).parent


def check_python() -> None:
    major, minor = sys.version_info[:2]
    if (major, minor) < (3, 10):
        print(f"[run] Python 3.10+ is required (you have {major}.{minor}). Aborting.")
        sys.exit(1)


def install_deps() -> None:
    req = ROOT / "requirements.txt"
    if not req.exists():
        print("[run] requirements.txt not found — skipping dependency install.")
        return
    print("[run] Installing/verifying dependencies…")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(req), "-q"],
        check=False,
    )
    if result.returncode != 0:
        print("[run] pip install reported errors — continuing anyway.")


def load_dotenv() -> None:
    """Minimal .env loader — sets variables that aren't already in the environment."""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)
    print("[run] Loaded .env")


def check_config() -> None:
    config = ROOT / "config.json"
    if not config.exists():
        print(
            "\n[run] WARNING: config.json not found.\n"
            "         Copy .env.example to .env and fill in your API keys, OR\n"
            "         create config.json manually. The app will start but LLM\n"
            "         features will not work without a valid config.\n"
        )
    else:
        print("[run] config.json found.")


def check_resume() -> None:
    resume = ROOT / "input" / "resume.yml"
    if not resume.exists():
        print(
            "\n[run] WARNING: input/resume.yml not found.\n"
            "         Generation features need your resume. Create input/resume.yml\n"
            "         based on the sample in the README.\n"
        )
    else:
        print("[run] input/resume.yml found.")


def open_browser(url: str, delay: float = 1.5) -> None:
    def _open() -> None:
        webbrowser.open(url)
    Timer(delay, _open).start()


def main() -> None:
    parser = argparse.ArgumentParser(description="QuickApply launcher")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--skip-install", action="store_true",
                        help="Skip pip install (faster restart if deps are already installed)")
    args = parser.parse_args()

    print("=" * 55)
    print("  QuickApply — AI Career Agent")
    print("=" * 55)

    check_python()
    load_dotenv()

    if not args.skip_install:
        install_deps()

    check_config()
    check_resume()

    url = f"http://{args.host}:{args.port}"
    print(f"\n[run] Starting server at {url}")
    print("[run] Press Ctrl+C to stop\n")

    if not args.no_browser:
        open_browser(url)

    # Import and run Flask app
    os.chdir(ROOT)  # ensure relative paths work
    from web_app import app
    app.run(debug=False, host=args.host, port=args.port, use_reloader=False)


if __name__ == "__main__":
    main()
