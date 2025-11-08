from __future__ import annotations

import contextlib
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from selenium.common.exceptions import WebDriverException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


@dataclass
class CandidateProfile:
    first_name: str
    last_name: str
    email: str
    phone: str = ""


def is_greenhouse_url(url: str | None) -> bool:
    if not url:
        return False
    u = url.lower()
    return "greenhouse.io" in u or "boards.greenhouse.io" in u


def is_lever_url(url: str | None) -> bool:
    if not url:
        return False
    u = url.lower()
    return "jobs.lever.co" in u or "lever.co" in u


class _BaseSimpleAutofill:
    def __init__(self, driver_factory: Callable[[], WebDriver | None], profile: CandidateProfile, wait_seconds: int = 20, verbose: bool = True) -> None:
        self._driver_factory = driver_factory
        self.profile = profile
        self.wait_seconds = wait_seconds
        self.verbose = verbose
        self._driver: WebDriver | None = None

    def __enter__(self) -> "_BaseSimpleAutofill":
        self._ensure_driver()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _ensure_driver(self) -> WebDriver | None:
        if self._driver is None:
            self._driver = self._driver_factory()
        return self._driver

    @property
    def driver(self) -> WebDriver:
        drv = self._ensure_driver()
        if drv is None:
            raise RuntimeError("Selenium driver could not be created")
        return drv

    def close(self) -> None:
        if self._driver:
            with contextlib.suppress(WebDriverException):
                self._driver.quit()
        self._driver = None

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(f"[autofill.portal] {msg}")

    def _click_first(self, driver: WebDriver, selectors: Iterable[tuple[str, str]]) -> bool:
        for by, sel in selectors:
            for el in driver.find_elements(by, sel):
                with contextlib.suppress(WebDriverException):
                    el.click()
                    time.sleep(0.8)
                    return True
        return False

    def _set_value(self, driver: WebDriver, selectors: Iterable[tuple[str, str]], value: str) -> bool:
        if not value:
            return False
        for by, sel in selectors:
            try:
                el = WebDriverWait(driver, 2).until(EC.presence_of_element_located((by, sel)))
            except TimeoutException:
                continue
            try:
                el.clear()
            except WebDriverException:
                pass
            with contextlib.suppress(WebDriverException):
                el.send_keys(value)
                return True
        return False

    def _upload_file(self, driver: WebDriver, selectors: Iterable[tuple[str, str]], path: Path) -> bool:
        for by, sel in selectors:
            for el in driver.find_elements(by, sel):
                with contextlib.suppress(WebDriverException):
                    el.send_keys(str(path))
                    time.sleep(1.2)
                    return True
        return False


class SimpleGreenhouseAutofill(_BaseSimpleAutofill):
    APPLY_SELECTORS: tuple[tuple[str, str], ...] = (
        (By.XPATH, "//a[contains(translate(., 'APPLY', 'apply'),'apply')]"),
        (By.XPATH, "//button[contains(translate(., 'APPLY', 'apply'),'apply')]"),
    )
    RESUME_INPUTS: tuple[tuple[str, str], ...] = (
        (By.CSS_SELECTOR, "input[type='file'][id*='resume'], input[type='file'][name*='resume']"),
        (By.CSS_SELECTOR, "input[type='file'][id*='resume_cv'], input[type='file'][name*='resume_cv']"),
    )
    COVER_INPUTS: tuple[tuple[str, str], ...] = (
        (By.CSS_SELECTOR, "input[type='file'][id*='cover'], input[type='file'][name*='cover']"),
    )
    FIRST_NAME: tuple[tuple[str, str], ...] = (
        (By.CSS_SELECTOR, "input#first_name, input[name='first_name']"),
    )
    LAST_NAME: tuple[tuple[str, str], ...] = (
        (By.CSS_SELECTOR, "input#last_name, input[name='last_name']"),
    )
    EMAIL: tuple[tuple[str, str], ...] = (
        (By.CSS_SELECTOR, "input#email, input[name='email']"),
    )
    PHONE: tuple[tuple[str, str], ...] = (
        (By.CSS_SELECTOR, "input#phone, input[name='phone']"),
    )

    def fill_application(self, job_url: str, resume_path: str | None = None, cover_letter_path: str | None = None) -> bool:
        d = self.driver
        d.get(job_url)
        time.sleep(1.5)
        self._click_first(d, self.APPLY_SELECTORS)
        time.sleep(1.0)
        self._set_value(d, self.FIRST_NAME, self.profile.first_name)
        self._set_value(d, self.LAST_NAME, self.profile.last_name)
        self._set_value(d, self.EMAIL, self.profile.email)
        self._set_value(d, self.PHONE, self.profile.phone)
        if resume_path:
            p = Path(resume_path).expanduser()
            if p.exists():
                self._upload_file(d, self.RESUME_INPUTS, p)
        if cover_letter_path:
            p = Path(cover_letter_path).expanduser()
            if p.exists():
                self._upload_file(d, self.COVER_INPUTS, p)
        self._log("Finished Greenhouse autofill.")
        return True


class SimpleLeverAutofill(_BaseSimpleAutofill):
    APPLY_SELECTORS: tuple[tuple[str, str], ...] = (
        (By.XPATH, "//a[contains(translate(., 'APPLY', 'apply'),'apply')]"),
        (By.XPATH, "//button[contains(translate(., 'APPLY', 'apply'),'apply')]"),
    )
    RESUME_INPUTS: tuple[tuple[str, str], ...] = (
        (By.CSS_SELECTOR, "input[type='file'][name*='resume']"),
        (By.CSS_SELECTOR, "input[type='file'][data-qa*='resume']"),
    )
    COVER_INPUTS: tuple[tuple[str, str], ...] = (
        (By.CSS_SELECTOR, "input[type='file'][name*='cover']"),
    )
    NAME: tuple[tuple[str, str], ...] = (
        (By.CSS_SELECTOR, "input[name='name'], input#name"),
    )
    EMAIL: tuple[tuple[str, str], ...] = (
        (By.CSS_SELECTOR, "input[name='email'], input#email"),
    )
    PHONE: tuple[tuple[str, str], ...] = (
        (By.CSS_SELECTOR, "input[name='phone'], input#phone"),
    )

    def fill_application(self, job_url: str, resume_path: str | None = None, cover_letter_path: str | None = None) -> bool:
        d = self.driver
        d.get(job_url)
        time.sleep(1.5)
        self._click_first(d, self.APPLY_SELECTORS)
        time.sleep(1.0)
        # Lever commonly has a single name field
        full_name = f"{self.profile.first_name} {self.profile.last_name}".strip()
        self._set_value(d, self.NAME, full_name)
        self._set_value(d, self.EMAIL, self.profile.email)
        self._set_value(d, self.PHONE, self.profile.phone)
        if resume_path:
            p = Path(resume_path).expanduser()
            if p.exists():
                self._upload_file(d, self.RESUME_INPUTS, p)
        if cover_letter_path:
            p = Path(cover_letter_path).expanduser()
            if p.exists():
                self._upload_file(d, self.COVER_INPUTS, p)
        self._log("Finished Lever autofill.")
        return True


