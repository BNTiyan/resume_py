    def _perform_login(self, driver: WebDriver) -> bool:
        passwords = [self._login_password]
        # Add secondary password if available
        import os
        secondary = os.getenv("WORKDAY_PASSWORD_SECONDARY")
        if secondary:
            passwords.append(secondary.strip())
            
        for pwd in passwords:
            if not pwd:
                continue
                
            # Fill username
            user_set = False
            for by, selector in self.LOGIN_USERNAME_SELECTORS:
                try:
                    el = WebDriverWait(driver, 5).until(EC.presence_of_element_located((by, selector)))
                    with contextlib.suppress(WebDriverException):
                        el.clear()
                    el.send_keys(self._login_username)
                    user_set = True
                    break
                except TimeoutException:
                    continue
                except WebDriverException:
                    continue
                    
            # Fill password
            pass_set = False
            for by, selector in self.LOGIN_PASSWORD_SELECTORS:
                try:
                    el = WebDriverWait(driver, 5).until(EC.presence_of_element_located((by, selector)))
                    with contextlib.suppress(WebDriverException):
                        el.clear()
                    el.send_keys(pwd)
                    pass_set = True
                    break
                except TimeoutException:
                    continue
                except WebDriverException:
                    continue
            
            # Submit
            submitted = False
            if user_set and pass_set:
                for by, selector in self.LOGIN_SUBMIT_SELECTORS:
                    btns = driver.find_elements(by, selector)
                    for b in btns:
                        with contextlib.suppress(WebDriverException):
                            b.click()
                            submitted = True
                            break
                    if submitted:
                        break
            
            if not submitted:
                continue
                
            time.sleep(2.5)
            # Success condition: apply button or application iframe appears
            if self._wait_for_any(driver, self.APPLY_BUTTON_SELECTORS + self.APPLICATION_IFRAME_SELECTORS, self.wait_seconds):
                self._log("Login successful.")
                return True
            
            self._log("Login attempt failed (or not detected), trying next password if available...")
            
        self._log("All login attempts failed.")
        return False
