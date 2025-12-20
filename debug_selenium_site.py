import argparse
from pathlib import Path
from typing import Any, Dict, List

from config import load_json
from match import load_selenium_sites_from_opts
from selenium_scraper import (
    create_headless_driver,
    SELENIUM_AVAILABLE,
)
from selenium.webdriver.common.by import By  # type: ignore


def debug_single_site(site: Dict[str, Any]) -> None:
    """Open one Selenium site and print rich debug info about selectors."""
    if not SELENIUM_AVAILABLE:
        print("❌ Selenium is not available in this environment.")
        return

    url = site.get("url")
    if not url:
        print("❌ Site has no URL:", site)
        return

    print(f"\n🔍 Debugging Selenium site:")
    print(f"  company = {site.get('company')}")
    print(f"  url     = {url}")
    print(f"  list_selector   = {site.get('list_selector')}")
    print(f"  item_selector   = {site.get('item_selector')}")
    print(f"  title_selector  = {site.get('title_selector')}")
    print(f"  location_sel    = {site.get('location_selector')}")
    print(f"  link_selector   = {site.get('link_selector')}")

    driver = create_headless_driver()
    if driver is None:
        print("❌ Failed to create Selenium driver.")
        return

    try:
        print(f"\n[driver] Loading {url} ...")
        driver.get(url)
        print(f"[driver] Loaded. title='{driver.title}' current_url='{driver.current_url}'")

        # First, try the list_selector (container elements)
        list_sel = site.get("list_selector") or ""
        item_sel = site.get("item_selector") or ""
        title_sel = site.get("title_selector") or ""
        link_sel = site.get("link_selector") or "a"
        loc_sel = site.get("location_selector") or ""

        def _count(sel: str) -> int:
            if not sel:
                return 0
            try:
                return len(driver.find_elements(By.CSS_SELECTOR, sel))
            except Exception as e:  # noqa: BLE001
                print(f"  [error] CSS '{sel}' raised {e}")
                return 0

        if list_sel:
            list_count = _count(list_sel)
            print(f"[debug] list_selector '{list_sel}' → {list_count} elements")
        else:
            list_count = 0
            print("[debug] list_selector is empty")

        if item_sel:
            item_count = _count(item_sel)
            print(f"[debug] item_selector '{item_sel}' → {item_count} elements")

        # If list_selector found elements, inspect the first few for titles/links
        containers: List[Any] = []
        if list_sel:
            try:
                containers = driver.find_elements(By.CSS_SELECTOR, list_sel)
            except Exception:
                containers = []
        elif item_sel:
            try:
                containers = driver.find_elements(By.CSS_SELECTOR, item_sel)
            except Exception:
                containers = []

        print(f"[debug] Using {len(containers)} container elements for deep inspection")

        for idx, elem in enumerate(containers[:5]):
            print(f"\n  [container {idx}]")
            try:
                text_snippet = (elem.text or "").strip().replace("\n", " ")[:200]
                print(f"    text = '{text_snippet}'")
            except Exception:
                print("    text = <unavailable>")

            # Try title selector
            if title_sel:
                try:
                    titles = elem.find_elements(By.CSS_SELECTOR, title_sel)
                    print(f"    title_selector '{title_sel}' → {len(titles)} matches")
                    if titles:
                        print(f"      first title: '{titles[0].text.strip()[:200]}'")
                except Exception as e:  # noqa: BLE001
                    print(f"    [error] title_selector on container: {e}")

            # Try link selector
            if link_sel:
                try:
                    links = elem.find_elements(By.CSS_SELECTOR, link_sel)
                    print(f"    link_selector '{link_sel}' → {len(links)} matches")
                    if links:
                        href = links[0].get_attribute("href") or ""
                        print(f"      first href: '{href}'")
                except Exception as e:  # noqa: BLE001
                    print(f"    [error] link_selector on container: {e}")

            # Try location selector
            if loc_sel:
                try:
                    locs = elem.find_elements(By.CSS_SELECTOR, loc_sel)
                    print(f"    location_selector '{loc_sel}' → {len(locs)} matches")
                    if locs:
                        print(f"      first location: '{locs[0].text.strip()[:200]}'")
                except Exception as e:  # noqa: BLE001
                    print(f"    [error] location_selector on container: {e}")

    finally:
        driver.quit()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Debug Selenium selectors for a single site defined in selenium_options.sites."
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.json",
        help="Path to config JSON (default: config.json)",
    )
    parser.add_argument(
        "--company",
        type=str,
        default=None,
        help="Company slug/name to match in selenium_options.sites['company']",
    )
    parser.add_argument(
        "--url",
        type=str,
        default=None,
        help="Exact URL to match in selenium_options.sites['url']",
    )
    args = parser.parse_args()

    cfg_path = Path(args.config)
    if not cfg_path.exists():
        raise SystemExit(f"Config file not found: {cfg_path}")

    cfg = load_json(cfg_path)
    selenium_opts = cfg.get("selenium_options", {}) or {}
    sites = load_selenium_sites_from_opts(selenium_opts)

    if not sites:
        raise SystemExit("No Selenium sites configured in config.json (selenium_options.sites).")

    target_site: Dict[str, Any] | None = None

    if args.company:
        comp_lower = args.company.strip().lower()
        for s in sites:
            if not isinstance(s, dict):
                continue
            if (s.get("company") or "").strip().lower() == comp_lower:
                target_site = s
                break

    if not target_site and args.url:
        url_norm = args.url.strip().lower()
        for s in sites:
            if not isinstance(s, dict):
                continue
            if (s.get("url") or "").strip().lower() == url_norm:
                target_site = s
                break

    if not target_site:
        print("❌ Could not find matching site for the given company/url.")
        print("   Available companies/urls:")
        for s in sites:
            if not isinstance(s, dict):
                continue
            print(f"   - company={s.get('company')} url={s.get('url')}")
        raise SystemExit(1)

    debug_single_site(target_site)


if __name__ == "__main__":
    main()


