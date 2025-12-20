import time
import requests
from typing import Any
from urllib.parse import urljoin, urlparse

import os

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
except Exception:
    SELENIUM_AVAILABLE = False

# webdriver-manager is optional; Selenium 4.6+ can use Selenium Manager automatically.
try:
    from webdriver_manager.chrome import ChromeDriverManager  # type: ignore
    _WDM_AVAILABLE = True
except Exception:
    ChromeDriverManager = None  # type: ignore
    _WDM_AVAILABLE = False

try:
    from llm_job_list_extractor import LLMJobListExtractor
    LLM_JOB_LIST_EXTRACTOR_AVAILABLE = True
except Exception:
    LLM_JOB_LIST_EXTRACTOR_AVAILABLE = False
    LLMJobListExtractor = None


def create_chrome_driver(headless: bool = True, window_size: str = "1920,1080") -> Any:
    if not SELENIUM_AVAILABLE:
        return None
    # Ensure webdriver-manager cache stays inside the repo/workspace (avoids permission issues on macOS/Homebrew Python).
    try:
        repo_root = os.path.dirname(os.path.abspath(__file__))
        wdm_dir = os.path.join(repo_root, ".wdm")
        se_cache_dir = os.path.join(repo_root, ".selenium-cache")
        os.makedirs(wdm_dir, exist_ok=True)
        os.makedirs(se_cache_dir, exist_ok=True)
        os.environ.setdefault("WDM_CACHE_DIR", wdm_dir)
        os.environ.setdefault("WDM_LOCAL", "1")
        # Selenium Manager cache location (avoids trying to write to ~/.cache/selenium)
        os.environ.setdefault("SE_CACHE_PATH", se_cache_dir)
        # Some environments respect XDG cache home
        os.environ.setdefault("XDG_CACHE_HOME", se_cache_dir)
    except Exception:
        pass
    chrome_options = ChromeOptions()
    if headless:
        chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    if window_size:
        chrome_options.add_argument(f"--window-size={window_size}")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36")
    # Prefer webdriver-manager if installed; otherwise rely on Selenium Manager (Selenium 4.6+).
    if _WDM_AVAILABLE and ChromeDriverManager is not None:
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
    else:
        # Selenium Manager will resolve the driver automatically when no Service is provided.
        driver = webdriver.Chrome(options=chrome_options)
    driver.implicitly_wait(5)
    return driver


def create_headless_driver() -> Any:
    return create_chrome_driver(headless=True)


def fetch_selenium_sites(sites: list[Any], fetch_limit: int) -> list[dict[str, Any]]:
    if not SELENIUM_AVAILABLE:
        return []
    driver = create_headless_driver()
    if driver is None:
        return []
    results: list[dict[str, Any]] = []
    # Normalize sites to dict entries even if provided as plain URLs
    normalized: list[dict[str, Any]] = []
    for site in sites or []:
        if isinstance(site, str):
            try:
                p = urlparse(site)
                absolute_base = f"{p.scheme}://{p.netloc}" if p.scheme and p.netloc else site
                normalized.append({
                    "url": site,
                    "list_selector": "a[href*='job'], a[href*='/jobs/'], a[href*='/careers/']",
                    "title_selector": "",
                    "location_selector": "",
                    "link_selector": "a",
                    "company": "",
                    "source": f"selenium:{p.netloc or 'site'}",
                    "careers_url": site,
                    "domain_filter": "",
                    "require_path_contains": "",
                    "absolute_base": absolute_base,
                    "open_roles_text": ["open roles", "view all jobs", "see all openings", "current openings", "job openings", "find open roles"],
                    "search_patterns": ["search for open roles", "search roles", "search jobs", "find jobs", "job search", "search openings", "start job search"]
                })
            except Exception:
                continue
        elif isinstance(site, dict):
            normalized.append(site)
    sites = normalized
    try:
        for site in sites or []:
            url = site.get("url")
            if not url:
                continue
            list_sel = site.get("list_selector") or ""
            item_sel = site.get("item_selector") or ""
            title_sel = site.get("title_selector") or ""
            loc_sel = site.get("location_selector") or ""
            link_sel = site.get("link_selector") or "a"
            desc_sel = site.get("description_selector") or ""
            source = site.get("source") or f"selenium:{url.split('/')[2]}"
            careers_url = site.get("careers_url") or url
            domain_filter = site.get("domain_filter") or ""
            require_path_contains = site.get("require_path_contains") or ""
            absolute_base = site.get("absolute_base") or url

            try:
                print(f"[selenium] loading: {url} source={source} company={site.get('company')}")
            except Exception:
                pass
            driver.get(url)

            # Optional explicit wait for dynamic pages
            wait_sel = site.get("wait_selector")
            try:
                if wait_sel:
                    WebDriverWait(driver, 12).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, wait_sel))
                    )
            except Exception:
                pass

            # Optional sleep for heavy JS pages
            try:
                sleep_seconds = float(site.get("sleep_seconds") or 0)
                if sleep_seconds > 0:
                    time.sleep(sleep_seconds)
            except Exception:
                pass
            
            # Try to find "open roles" or similar text and click it
            open_roles_patterns = site.get("open_roles_text") or []
            search_patterns = site.get("search_patterns") or []
            all_patterns = open_roles_patterns + search_patterns
            
            if all_patterns:
                try:
                    page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
                    
                    # First try to find and click search-related buttons
                    for pattern in all_patterns:
                        if pattern.lower() in page_text:
                            # Try multiple ways to find clickable elements
                            clickable_selectors = [
                                # XPath for text content
                                (By.XPATH, f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{pattern.lower()}')]"),
                                # Common button/link classes and IDs for search
                                (By.CSS_SELECTOR, "button[class*='search'], a[class*='search']"),
                                (By.CSS_SELECTOR, "button[id*='search'], a[id*='search']"),
                                (By.CSS_SELECTOR, "a[href*='search'], a[href*='jobs']"),
                                # Generic buttons/links near search text
                                (By.XPATH, f"//button[contains(., '{pattern}')]"),
                                (By.XPATH, f"//a[contains(., '{pattern}')]"),
                            ]
                            
                            for by, selector in clickable_selectors:
                                try:
                                    elements = driver.find_elements(by, selector)
                                    if elements:
                                        # Try to click the first matching element
                                        elem = elements[0]
                                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
                                        time.sleep(0.5)
                                        elem.click()
                                        # Wait longer after clicking for content to load
                                        wait_after_click = max(sleep_seconds, 3)  # At least 3 seconds
                                        time.sleep(wait_after_click)
                                        print(f"[selenium] clicked '{pattern}' button/link (waited {wait_after_click}s)")
                                        break
                                except Exception:
                                    continue
                            else:
                                # Continue to next pattern if click failed
                                continue
                            # Break out of pattern loop if we successfully clicked
                            break
                            
                except Exception as e:
                    print(f"[selenium] open roles/search button click failed: {e}")
            
            # Scroll down to load more jobs (many sites lazy-load)
            try:
                last_height = driver.execute_script("return document.body.scrollHeight")
                scroll_attempts = 0
                max_scrolls = 5  # Scroll down 5 times to load more jobs
                
                while scroll_attempts < max_scrolls:
                    # Scroll to bottom
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(2)  # Wait longer for content to load
                    
                    # Calculate new height and compare
                    new_height = driver.execute_script("return document.body.scrollHeight")
                    if new_height == last_height:
                        # Try one more time in case content is still loading
                        time.sleep(1)
                        new_height = driver.execute_script("return document.body.scrollHeight")
                        if new_height == last_height:
                            # No more content loaded
                            break
                    last_height = new_height
                    scroll_attempts += 1
                
                # Scroll back to top
                driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(0.5)
                
                if scroll_attempts > 0:
                    print(f"[selenium] scrolled {scroll_attempts} times to load more jobs")
            except Exception as scroll_err:
                print(f"[selenium] scroll error: {scroll_err}")
            
            items = []
            if list_sel:
                items = driver.find_elements(By.CSS_SELECTOR, list_sel)
            elif item_sel:
                items = driver.find_elements(By.CSS_SELECTOR, item_sel)
            # Fallback to page-level if no container selector
            if not items:
                items = [driver]

            # Debug: counts per site
            try:
                print(f"[selenium] {source} containers={len(items)} url={url}")
                print(f"[selenium-debug] Selectors: link='{link_sel}', title='{title_sel}', list='{list_sel}', item='{item_sel}'")
            except Exception:
                pass

            processed_count = 0
            for idx, elem in enumerate(items):
                try:
                    processed_count += 1
                    title = ""
                    location = ""
                    link = ""
                    description = ""
                    
                    # Title extraction - try multiple methods
                    # Method 1: Use title_selector
                    if title_sel:
                        try:
                            # Try each selector in the comma-separated list
                            for sel in title_sel.split(','):
                                sel = sel.strip()
                                t_nodes = elem.find_elements(By.CSS_SELECTOR, sel)
                                if t_nodes:
                                    title = t_nodes[0].text.strip()
                                    if title:
                                        print(f"  [selenium-debug] Title Method 1 ({sel}) found: {title[:50]}")
                                        break
                        except Exception as e:
                            print(f"  [selenium-debug] Title Method 1 failed: {e}")
                    
                    # Method 2: Try common title patterns if still no title
                    if not title:
                        try:
                            # Try h1-h6 tags
                            for tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                                headings = elem.find_elements(By.TAG_NAME, tag)
                                if headings:
                                    title = headings[0].text.strip()
                                    if title:
                                        print(f"  [selenium-debug] Title Method 2 ({tag}) found: {title[:50]}")
                                        break
                        except Exception:
                            pass
                    
                    # Method 3: Try aria-label or title attribute
                    if not title:
                        try:
                            title = elem.get_attribute("aria-label") or elem.get_attribute("title") or ""
                            title = title.strip()
                            if title:
                                print(f"  [selenium-debug] Title Method 3 (aria-label/title) found: {title[:50]}")
                        except Exception:
                            pass
                    
                    # Method 4: Try data attributes
                    if not title:
                        try:
                            for attr in ['data-title', 'data-job-title', 'data-name', 'data-label']:
                                title = elem.get_attribute(attr) or ""
                                title = title.strip()
                                if title:
                                    print(f"  [selenium-debug] Title Method 4 (data-{attr}) found: {title[:50]}")
                                    break
                        except Exception:
                            pass
                    
                    # Method 5: Get text from element itself (fallback)
                    if not title:
                        try:
                            txt = getattr(elem, 'text', '') or ''
                            # Get first non-empty line
                            lines = [l.strip() for l in txt.split('\n') if l.strip()]
                            if lines:
                                title = lines[0][:200]  # Limit length
                                print(f"  [selenium-debug] Title Method 5 (element text) found: {title[:50]}")
                        except Exception:
                            pass
                    
                    # Method 6: Extract from URL if still no title
                    if not title and link:
                        try:
                            # Try to extract meaningful part from URL
                            from urllib.parse import urlparse
                            parsed = urlparse(link)
                            path_parts = [p for p in parsed.path.split('/') if p and p not in ['jobs', 'job', 'careers', 'en', 'us', 'details']]
                            if path_parts:
                                # Use last meaningful part, replace dashes/underscores with spaces
                                title = path_parts[-1].replace('-', ' ').replace('_', ' ').title()
                                print(f"  [selenium-debug] Title Method 6 (from URL) found: {title[:50]}")
                        except Exception:
                            pass
                    
                    # Location
                    if loc_sel:
                        l_nodes = elem.find_elements(By.CSS_SELECTOR, loc_sel)
                        if l_nodes:
                            location = l_nodes[0].text.strip()
                    
                    # Description
                    if desc_sel:
                        d_nodes = elem.find_elements(By.CSS_SELECTOR, desc_sel)
                        if d_nodes:
                            description = d_nodes[0].text.strip()
                    
                    # Link extraction - try multiple methods
                    # Method 1: Use link_selector
                    if link_sel:
                        l_nodes = elem.find_elements(By.CSS_SELECTOR, link_sel)
                        if l_nodes:
                            link = l_nodes[0].get_attribute("href") or ""
                            if link and not link.startswith('javascript:'):
                                print(f"  [selenium-debug] Method 1 (link_sel) found: {link[:80]}")
                            elif link.startswith('javascript:'):
                                link = ""  # Reset invalid JavaScript links
                    
                    # Method 2: Check if element itself is a link
                    if not link and hasattr(elem, 'get_attribute'):
                        link = elem.get_attribute('href') or ""
                        if link and not link.startswith('javascript:'):
                            print(f"  [selenium-debug] Method 2 (elem href) found: {link[:80]}")
                        elif link.startswith('javascript:'):
                            link = ""  # Reset invalid JavaScript links
                    
                    # Method 3: Find anchor tag within element
                    if not link:
                        try:
                            anchors = elem.find_elements(By.TAG_NAME, "a")
                            if anchors:
                                for anchor in anchors:
                                    href = anchor.get_attribute("href") or ""
                                    if href and not href.startswith('javascript:'):
                                        link = href
                                        print(f"  [selenium-debug] Method 3 (anchor tag) found: {link[:80]}")
                                        break
                        except Exception as e:
                            print(f"  [selenium-debug] Method 3 failed: {e}")
                    
                    # Method 4: Check data attributes (BEFORE onclick, as they're more reliable)
                    if not link:
                        try:
                            for attr in ['data-url', 'data-href', 'data-link', 'data-job-url', 'data-jobid', 'data-id']:
                                data_url = elem.get_attribute(attr) or ""
                                if data_url:
                                    # If it's a relative path, make it absolute
                                    if data_url.startswith('/'):
                                        data_url = urljoin(absolute_base, data_url)
                                    # If it's just an ID, construct URL
                                    elif not data_url.startswith('http') and '/' not in data_url:
                                        # Try common patterns
                                        if '/jobs/' in absolute_base or '/careers/' in absolute_base:
                                            data_url = urljoin(absolute_base, f"/jobs/{data_url}")
                                        else:
                                            data_url = urljoin(absolute_base, f"/{data_url}")
                                    
                                    if data_url.startswith('http'):
                                        link = data_url
                                        print(f"  [selenium-debug] Method 4 (data-{attr}) found: {link[:80]}")
                                        break
                        except Exception:
                            pass
                    
                    # Method 5: If element is clickable, try to get URL from onclick
                    if not link:
                        try:
                            onclick = elem.get_attribute("onclick") or ""
                            if onclick and "http" in onclick:
                                import re
                                urls = re.findall(r'https?://[^\s\'"]+', onclick)
                                if urls:
                                    link = urls[0]
                                    print(f"  [selenium-debug] Method 5 (onclick) found: {link[:80]}")
                        except Exception:
                            pass
                    
                    # Method 6: Try to find job ID and construct URL
                    if not link:
                        try:
                            # Look for job ID in various attributes
                            job_id = None
                            for attr in ['id', 'data-id', 'data-job-id', 'data-jobid', 'aria-label', 'data-job-requisition-id']:
                                val = elem.get_attribute(attr) or ""
                                # Extract job ID (keep as string to avoid number truncation)
                                import re
                                # Match full alphanumeric ID (not just first digits)
                                id_match = re.search(r'(\d{10,}[-\w]*)', val)  # Match 10+ digits, optionally followed by hyphens/words
                                if id_match:
                                    job_id = id_match.group(1)  # Keep full ID as string
                                    print(f"  [selenium-debug] Extracted job ID: {job_id}")
                                    break
                            
                            if job_id:
                                # Try common URL patterns
                                base_patterns = [
                                    f"{absolute_base}/jobs/{job_id}",
                                    f"{absolute_base}/job/{job_id}",
                                    f"{absolute_base}/careers/{job_id}",
                                    f"{absolute_base}/en-us/jobs/{job_id}",
                                    f"{absolute_base}/about/careers/applications/jobs/results/{job_id}",  # Google specific
                                ]
                                for pattern in base_patterns:
                                    link = pattern
                                    print(f"  [selenium-debug] Method 6 (constructed from ID {job_id}) found: {link[:120]}")  # Show more chars
                                    break
                        except Exception as e:
                            print(f"  [selenium-debug] Method 6 failed: {e}")
                    
                    # Normalize relative links
                    if link and absolute_base and link.startswith('/'):
                        link = urljoin(absolute_base, link)
                    
                    # Domain/path filters
                    if domain_filter and link:
                        try:
                            netloc = urlparse(link).netloc
                            if domain_filter not in netloc:
                                print(f"  [selenium-debug] Skipping link (domain filter): {link[:60]}...")
                                continue
                        except Exception:
                            pass
                    
                    if require_path_contains and (require_path_contains not in (link or '')):
                        print(f"  [selenium-debug] Skipping link (path filter): {link[:60]}...")
                        continue
                    
                    # Skip only if we have neither title nor valid URL
                    if not title and not (link and link.startswith('http')):
                        print(f"  [selenium-debug] Skipping item {idx+1} (no title and no valid URL)")
                        continue
                    
                    # If we have URL but no title, create a fallback title
                    if not title and link and link.startswith('http'):
                        title = f"Job at {site.get('company', 'Company')}"
                        print(f"  [selenium-debug] Using fallback title: {title}")
                    
                    # Debug: Log URL extraction result
                    if not link:
                        print(f"  [selenium-debug] ⚠️ Item {idx+1}/{len(items)}: No URL extracted for '{title[:50]}' (company: {site.get('company', 'N/A')})")
                    else:
                        print(f"  [selenium-debug] ✅ Item {idx+1}/{len(items)}: Extracted URL: {link[:80]} for '{title[:50]}'")
                    
                    # If no description from list page, try to fetch from job detail page
                    if not description and link and site.get("fetch_description_from_link"):
                        try:
                            driver.get(link)
                            time.sleep(2)  # Wait for page load
                            detail_desc_sel = site.get("detail_description_selector") or "body"
                            desc_nodes = driver.find_elements(By.CSS_SELECTOR, detail_desc_sel)
                            if desc_nodes:
                                description = desc_nodes[0].text.strip()[:2000]  # Limit to 2000 chars
                            driver.back()
                            time.sleep(1)
                        except Exception as e:
                            print(f"  [selenium] failed to fetch description from {link}: {e}")
                    
                    # Only add if we have a valid link (don't use careers_url as fallback)
                    if not link:
                        print(f"  [selenium-debug] ⚠️ Skipping job (no URL): {title[:50]}")
                        continue
                    
                    results.append({
                        "title": title,
                        "company": site.get("company") or "",
                        "location": location,
                        "description": description,
                        "url": link,  # Use extracted link, don't fallback to careers_url
                        "careers_url": careers_url,
                        "source": source,
                    })
                    print(f"  [selenium-debug] ✅ Added job {len(results)}: {title[:50]} -> {link[:80]}")
                    if len(results) >= fetch_limit:
                        print(f"[selenium-debug] Reached fetch_limit ({fetch_limit}), stopping")
                        return results
                except Exception as e:
                    print(f"  [selenium-debug] ❌ Error processing item {idx+1}: {type(e).__name__}: {e}")
                    import traceback
                    print(f"  [selenium-debug] Traceback: {traceback.format_exc()[:200]}")
                    continue
            
            # Count jobs with valid URLs (not javascript: or empty)
            valid_url_count = sum(1 for r in results if r.get("url") and r.get("url").startswith("http"))
            jobs_with_titles = sum(1 for r in results if r.get("title") and r.get("title").strip() and not r.get("title", "").startswith("Job at"))
            print(f"[selenium-debug] Processed {processed_count} items from {len(items)} containers, extracted {len(results)} jobs ({valid_url_count} with valid URLs, {jobs_with_titles} with real titles)")
            
            # If we didn't get enough jobs with VALID URLs AND real titles, try LLM extraction as fallback
            if (valid_url_count < 3 or jobs_with_titles < 3) and LLM_JOB_LIST_EXTRACTOR_AVAILABLE:
                try:
                    openai_key = os.getenv("OPENAI_API_KEY")
                    if openai_key:
                        reason = []
                        if valid_url_count < 3:
                            reason.append(f"{valid_url_count} valid URLs")
                        if jobs_with_titles < 3:
                            reason.append(f"{jobs_with_titles} real titles")
                        print(f"[selenium-debug] ⚠️ Only found {', '.join(reason)}, trying LLM extraction...")
                        page_source = driver.page_source
                        llm_extractor = LLMJobListExtractor(openai_key)
                        llm_jobs = llm_extractor.extract_jobs_from_html(
                            page_source,
                            url,
                            site.get("company"),
                            max_jobs=30
                        )
                        
                        # Add LLM-extracted jobs that we don't already have
                        existing_urls = {r.get("url") for r in results if r.get("url") and r.get("url").startswith("http")}
                        llm_added = 0
                        for llm_job in llm_jobs:
                            llm_url = llm_job.get("url", "")
                            if llm_url and llm_url.startswith("http") and llm_url not in existing_urls:
                                results.append(llm_job)
                                existing_urls.add(llm_url)
                                llm_added += 1
                                print(f"  [selenium-debug] ✅ LLM extracted: {llm_job.get('title', 'N/A')[:50]} -> {llm_url[:80]}")
                        
                        print(f"[selenium-debug] LLM extraction added {llm_added} jobs with valid URLs, total now: {len([r for r in results if r.get('url') and r.get('url').startswith('http')])}")
                        
                        # Remove jobs without valid URLs if we got LLM results
                        if llm_added > 0:
                            results[:] = [r for r in results if r.get("url") and r.get("url").startswith("http")]
                            print(f"[selenium-debug] Cleaned up: {len(results)} jobs with valid URLs remaining")
                except Exception as e:
                    print(f"[selenium-debug] LLM extraction failed: {type(e).__name__}: {e}")
                    import traceback
                    print(f"[selenium-debug] Traceback: {traceback.format_exc()[:300]}")
    finally:
        try:
            driver.quit()
        except Exception:
            pass
    return results


def fetch_selenium_site_parallel(site: dict[str, Any], fetch_limit: int) -> list[dict[str, Any]]:
    """
    Fetch jobs from a single Selenium site (for parallel processing).
    
    Args:
        site: Site configuration dictionary
        fetch_limit: Maximum number of jobs to fetch
    
    Returns:
        List of job dictionaries
    """
    if not SELENIUM_AVAILABLE:
        return []
    
    driver = create_headless_driver()
    if driver is None:
        return []
    
    results: list[dict[str, Any]] = []
    
    try:
        # Use the existing fetch_selenium_sites logic for a single site
        temp_results = fetch_selenium_sites([site], fetch_limit)
        results.extend(temp_results)
    except Exception as e:
        print(f"[selenium-parallel] Error fetching {site.get('company', 'unknown')}: {str(e)[:100]}")
    finally:
        try:
            driver.quit()
        except Exception:
            pass
    
    return results


def fetch_selenium_sites_parallel(sites: list[Any], fetch_limit: int, max_workers: int = 3) -> list[dict[str, Any]]:
    """
    Fetch jobs from multiple Selenium sites in parallel.
    
    Args:
        sites: List of site configurations
        fetch_limit: Maximum number of jobs to fetch per site
        max_workers: Number of parallel Selenium drivers (default: 3, don't use too many)
    
    Returns:
        Combined list of job dictionaries from all sites
    """
    if not SELENIUM_AVAILABLE:
        return []
    
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    print(f"\n[selenium-parallel] Fetching from {len(sites)} sites with {max_workers} parallel workers...")
    
    results: list[dict[str, Any]] = []
    per_site_limit = max(1, fetch_limit // max(1, len(sites)))
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all sites for parallel fetching
        future_to_site = {
            executor.submit(fetch_selenium_site_parallel, site, per_site_limit): site 
            for site in sites
        }
        
        # Collect results as they complete
        for idx, future in enumerate(as_completed(future_to_site), 1):
            site = future_to_site[future]
            company = site.get('company', 'unknown')
            
            try:
                site_jobs = future.result()
                results.extend(site_jobs)
                print(f"  [selenium-parallel] {idx}/{len(sites)} - {company}: ✅ {len(site_jobs)} jobs")
            except Exception as e:
                print(f"  [selenium-parallel] {idx}/{len(sites)} - {company}: ❌ {str(e)[:50]}")
    
    print(f"[selenium-parallel] Completed: {len(results)} total jobs from {len(sites)} sites\n")
    
    return results

