from recaptcha_domain_replicator import hosts_manager


def test_domain_variants_normal_domain():
    assert hosts_manager._domain_variants("example.com") == ["example.com", "www.example.com"]


def test_domain_variants_www_domain():
    assert hosts_manager._domain_variants("www.example.com") == ["www.example.com", "example.com"]


def test_domain_variants_strips_port():
    assert hosts_manager._domain_variants("example.com:8080") == ["example.com", "www.example.com"]


def test_domain_variants_recaptcha_api_domain_does_not_add_www_variant():
    assert hosts_manager._domain_variants("google.com") == ["google.com"]
