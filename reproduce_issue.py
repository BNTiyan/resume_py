
import sys
import requests
import traceback
from selenium_scraper import fetch_selenium_sites

print(f"Python executable: {sys.executable}")

# Minimal config for Google and Uber from user's request
sites = [
    {
        "company": "google",
        "url": "https://www.google.com/about/careers/applications/jobs/results/",
        "list_selector": "li[class*='lLd3Je'], div[class*='job-card'], div[class*='job-listing'], li[class*='job'], article[class*='job'], a[href*='/job/'], a[href*='/jobs/']",
        "title_selector": "h2, h3, a[href*='/jobs/results/']",
        "location_selector": "span[class*='r0wTof'], span[class*='location'], div[class*='location']",
        "link_selector": "a[href*='/jobs/results/'], a[href*='/job/'], a[href*='/jobs/'], a[href*='careers']",
        "source": "selenium:google",
        "careers_url": "https://www.google.com/about/careers/",
        "domain_filter": "google.com",
        "absolute_base": "https://www.google.com",
        "sleep_seconds": 3,
        "wait_selector": "li[class*='lLd3Je'], div[class*='job-card']",
        "fetch_description_from_link": True,
        "detail_description_selector": "div[class*='KwJkGe'], div[class*='job-description'], article, main"
    },
    {
        "company": "uber",
        "url": "https://www.uber.com/us/en/careers/list/?department=Engineering",
        "list_selector": "a[href*='/careers/list/']",
        "title_selector": "a[href*='/careers/list/'], h3, h4",
        "location_selector": "span[class*='location'], div[class*='location']",
        "link_selector": "a[href*='/careers/list/']",
        "source": "selenium:uber",
        "careers_url": "https://www.uber.com/us/en/careers/",
        "domain_filter": "uber.com",
        "absolute_base": "https://www.uber.com",
        "sleep_seconds": 3,
        "wait_selector": "a[href*='/careers/list/']"
    }
]

print("Starting reproduction...")
try:
    results = fetch_selenium_sites(sites, fetch_limit=1)
    print(f"Results: {len(results)}")
except Exception:
    traceback.print_exc()
