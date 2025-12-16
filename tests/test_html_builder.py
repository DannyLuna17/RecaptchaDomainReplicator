from pathlib import Path

from recaptcha_domain_replicator.html_builder import create_captcha_html


def test_create_captcha_html_does_not_write_file_by_default(tmp_path: Path):
    page = create_captcha_html(
        download_dir=str(tmp_path),
        website_key="TEST_SITE_KEY",
        website_url="https://example.com/path",
        is_invisible=False,
        is_enterprise=False,
    )

    assert page.path is None
    assert "TEST_SITE_KEY" in page.content
    assert "[No token yet]" in page.content
    assert list(tmp_path.glob("*.html")) == []


def test_create_captcha_html_writes_file_when_persist_enabled(tmp_path: Path):
    page = create_captcha_html(
        download_dir=str(tmp_path),
        website_key="TEST_SITE_KEY",
        website_url="https://example.com/path",
        is_invisible=False,
        is_enterprise=False,
        persist_html=True,
    )

    assert page.path is not None
    p = Path(page.path)
    assert p.exists()
    content = p.read_text(encoding="utf-8")
    assert "TEST_SITE_KEY" in content
    assert "[No token yet]" in content


def test_create_captcha_html_generates_unique_filenames(tmp_path: Path):
    a = create_captcha_html(
        download_dir=str(tmp_path),
        website_key="A",
        website_url="https://example.com/path",
    )
    b = create_captcha_html(
        download_dir=str(tmp_path),
        website_key="B",
        website_url="https://example.com/path",
    )
    assert a.filename != b.filename
