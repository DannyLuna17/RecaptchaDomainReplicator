from recaptcha_domain_replicator.browser_config import (
    build_host_resolver_rules,
    create_browser_options,
    mapped_hosts_for_domain,
)


def test_build_host_resolver_rules_adds_www_variant_for_normal_domains():
    rules = build_host_resolver_rules("example.com")
    assert "MAP example.com 127.0.0.1" in rules
    assert "MAP www.example.com 127.0.0.1" in rules


def test_build_host_resolver_rules_adds_base_variant_when_domain_has_www():
    rules = build_host_resolver_rules("www.example.com")
    assert "MAP www.example.com 127.0.0.1" in rules
    assert "MAP example.com 127.0.0.1" in rules


def test_build_host_resolver_rules_strips_port():
    rules = build_host_resolver_rules("example.com:8080")
    assert ":8080" not in rules
    assert "MAP example.com 127.0.0.1" in rules


def test_build_host_resolver_rules_does_not_auto_add_www_for_recaptcha_api_domains():
    rules = build_host_resolver_rules("google.com")
    assert "MAP google.com 127.0.0.1" in rules
    assert "www.google.com" not in rules


def test_mapped_hosts_for_domain_adds_www_variant_for_normal_domains():
    assert mapped_hosts_for_domain("example.com") == ["example.com", "www.example.com"]


def test_mapped_hosts_for_domain_adds_base_variant_when_domain_has_www():
    assert mapped_hosts_for_domain("www.example.com") == ["www.example.com", "example.com"]


def test_mapped_hosts_for_domain_strips_port():
    assert mapped_hosts_for_domain("example.com:8080") == ["example.com", "www.example.com"]


def test_mapped_hosts_for_domain_does_not_auto_add_www_for_recaptcha_api_domains():
    assert mapped_hosts_for_domain("google.com") == ["google.com"]
    assert mapped_hosts_for_domain("www.google.com") == ["www.google.com"]


def test_create_browser_options_sets_browser_path():
    fake_path = r"C:\path\to\chrome.exe"
    opts = create_browser_options(browser_path=fake_path)
    assert getattr(opts, "browser_path", None) == fake_path
