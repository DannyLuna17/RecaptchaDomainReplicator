from __future__ import annotations

import recaptcha_domain_replicator.captcha_replicator as cr
from recaptcha_domain_replicator.captcha_replicator import RecaptchaDomainReplicator
from recaptcha_domain_replicator.html_builder import CaptchaHtml


class _FakeTab:
    def __init__(self) -> None:
        self.got: list[str] = []

    def get(self, url: str) -> None:
        self.got.append(url)

    @property
    def url(self) -> str:
        return self.got[-1] if self.got else "about:blank"


class _FakeBrowser:
    def __init__(self, tab: _FakeTab) -> None:
        self.latest_tab = tab
        self.quit_calls = 0

    def quit(self) -> None:
        self.quit_calls += 1


class _DummyThread:
    def join(self, timeout: float | None = None) -> None:
        return


def test_close_browser_does_not_quit_caller_provided_browser() -> None:
    tab = _FakeTab()
    browser = _FakeBrowser(tab)
    rep = RecaptchaDomainReplicator()
    try:
        rep._get_or_create_browser(browser=browser, use_ssl=False)
        rep.close_browser()
        assert browser.quit_calls == 0
    finally:
        rep.close()


def test_close_browser_quits_owned_browser() -> None:
    tab = _FakeTab()
    browser = _FakeBrowser(tab)
    rep = RecaptchaDomainReplicator()
    try:
        rep.browser = browser
        rep.tab = tab
        rep._owns_browser = True
        rep.close_browser()
        assert browser.quit_calls == 1
    finally:
        rep.close()


def test_replicate_captcha_observation_time_controls_token_monitor(monkeypatch) -> None:
    rep = RecaptchaDomainReplicator()
    tab = _FakeTab()

    captured: dict[str, object] = {}

    def fake_start_http_server(domain: str | None = None, use_ssl: bool = True) -> int:  # noqa: ARG001
        rep.server_port = 12345
        rep.server.use_ssl = False
        rep.server.port_forwarding_enabled = False
        return 12345

    def fake_create_captcha_html(**kwargs) -> CaptchaHtml:  # noqa: ARG001
        return CaptchaHtml(filename="page.html", content="<html></html>", path=None)

    def fake_handle(*, tab, local_file_url: str, user_agent=None, cookies=None) -> bool:  # noqa: ARG001
        captured["local_file_url"] = local_file_url
        return True

    def fake_start_token_monitor(
        tab,
        on_token,
        max_checks=600,
        stop_event=None,
        on_stop=None,
        poll_interval: float = 1.0,
    ):
        captured["max_checks"] = max_checks
        captured["poll_interval"] = poll_interval
        return _DummyThread()

    monkeypatch.setattr(rep, "start_http_server", fake_start_http_server)
    monkeypatch.setattr(rep, "create_captcha_html", fake_create_captcha_html)
    monkeypatch.setattr(rep, "_handle_captcha_interaction", fake_handle)
    monkeypatch.setattr(cr, "start_token_monitor", fake_start_token_monitor)

    try:
        _, token_handle = rep.replicate_captcha(
            website_key="TEST_SITE_KEY",
            website_url="https://example.com/path",
            tab=tab,
            observation_time=10,
            bypass_domain_check=False,
            use_ssl=False,
        )
        assert token_handle is not None
        assert captured["max_checks"] == 11
        assert captured["local_file_url"] == "http://localhost:12345/page.html"
    finally:
        rep.close()


def test_replicate_captcha_observation_time_zero_runs_indefinitely(monkeypatch) -> None:
    rep = RecaptchaDomainReplicator()
    tab = _FakeTab()

    captured: dict[str, object] = {}

    def fake_start_http_server(domain: str | None = None, use_ssl: bool = True) -> int:  # noqa: ARG001
        rep.server_port = 12345
        rep.server.use_ssl = False
        rep.server.port_forwarding_enabled = False
        return 12345

    def fake_create_captcha_html(**kwargs) -> CaptchaHtml:  # noqa: ARG001
        return CaptchaHtml(filename="page.html", content="<html></html>", path=None)

    def fake_handle(*, tab, local_file_url: str, user_agent=None, cookies=None) -> bool:  # noqa: ARG001
        captured["local_file_url"] = local_file_url
        return True

    def fake_start_token_monitor(
        tab,
        on_token,
        max_checks=600,
        stop_event=None,
        on_stop=None,
        poll_interval: float = 1.0,
    ):
        captured["max_checks"] = max_checks
        captured["poll_interval"] = poll_interval
        return _DummyThread()

    monkeypatch.setattr(rep, "start_http_server", fake_start_http_server)
    monkeypatch.setattr(rep, "create_captcha_html", fake_create_captcha_html)
    monkeypatch.setattr(rep, "_handle_captcha_interaction", fake_handle)
    monkeypatch.setattr(cr, "start_token_monitor", fake_start_token_monitor)

    try:
        _, token_handle = rep.replicate_captcha(
            website_key="TEST_SITE_KEY",
            website_url="https://example.com/path",
            tab=tab,
            observation_time=0,
            bypass_domain_check=False,
            use_ssl=False,
        )
        assert token_handle is not None
        assert captured["max_checks"] == 0
        assert captured["local_file_url"] == "http://localhost:12345/page.html"
    finally:
        rep.close()
