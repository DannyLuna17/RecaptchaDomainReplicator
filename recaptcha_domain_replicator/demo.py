from .captcha_replicator import RecaptchaDomainReplicator


def run_demo():
    """Run a simple demo using the Google test sitekey."""

    replicator = RecaptchaDomainReplicator(
        proxy=None,
        browser_path=None,  # Prefer to use Edge and Chrome for Testing
    )

    print("\n=== Testing RecaptchaDomainReplicator ===")
    print("Browser will stay open until the captcha is solved.")

    browser, token_handle = replicator.replicate_captcha(
        is_invisible=False,
        is_enterprise=False,
        website_key="6Le-wvkSAAAAAPBMRTvw0Q4Muexq9bi0DJwx_mJ-",
        website_url="https://www.google.com/recaptcha/api2/demo",
        observation_time=0,  # 0 means run until solved/closed
        bypass_domain_check=True,
        use_ssl=True,
        action=None,
        api_domain="google.com",
        browser=None,
        cookies=None,
        user_agent=None,
        tab=None,
    )

    if not browser:
        print("Failed to start reCAPTCHA session. See error messages above.")
        replicator.stop_http_server()
        return

    # Wait until the token is captured
    token_handle.wait(timeout=0) if token_handle else None
    token = token_handle.get()

    if token:
        print("\n=== CAPTCHA TOKEN OBTAINED ===")
        print(f"Token (first 120 chars): {token[:120]}...")
        print(f"Token length: {len(token)}")
    else:
        print("\n=== NO TOKEN OBTAINED ===")
        print("The CAPTCHA was not solved or token was not captured.")

    print("\n=== Completed replicated CAPTCHA session ===")


if __name__ == "__main__":
    run_demo()
