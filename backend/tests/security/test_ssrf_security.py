import pytest

from app.core.ssrf import SSRFError, validate_url


def test_ssrf_blocks_loopback() -> None:
    """Security Test 6: Loopback IPv4 addresses must be blocked."""
    loopbacks = [
        "https://127.0.0.1/webhook",
        "https://127.0.0.2:8080/callback",
        "https://127.255.255.254/api",
        "https://localhost/api",
    ]
    for url in loopbacks:
        with pytest.raises(SSRFError, match="SSRF blocked"):
            validate_url(url, allow_private=False)


def test_ssrf_blocks_private_ranges() -> None:
    """Security Test 6: RFC 1918 private ranges must be blocked."""
    private_urls = [
        "https://10.0.0.1/admin",
        "https://10.255.255.255/hook",
        "https://172.16.0.1/hook",
        "https://172.31.255.255/hook",
        "https://192.168.1.1/hook",
        "https://192.168.100.50:9000/hook",
    ]
    for url in private_urls:
        with pytest.raises(SSRFError, match="SSRF blocked"):
            validate_url(url, allow_private=False)


def test_ssrf_blocks_metadata_address() -> None:
    """Security Test 6: Cloud metadata service IP (169.254.169.254) must be blocked."""
    metadata_urls = [
        "https://169.254.169.254/latest/meta-data/",
        "https://169.254.169.254/computeMetadata/v1/",
        "https://169.254.1.1/api",
    ]
    for url in metadata_urls:
        with pytest.raises(SSRFError, match="SSRF blocked"):
            validate_url(url, allow_private=False)


def test_ssrf_blocks_ipv6_variants() -> None:
    """Security Test 6: IPv6 loopback, ULA, and IPv4-mapped IPv6 must be blocked."""
    ipv6_blocked = [
        "https://[::1]/webhook",
        "https://[::]/webhook",
        "https://[fe80::1]/webhook",
        "https://[fc00::1]/webhook",
        "https://[fd00::1]/webhook",
        "https://[::ffff:127.0.0.1]/webhook",
        "https://[::ffff:169.254.169.254]/latest/meta-data/",
        "https://[::ffff:10.0.0.1]/webhook",
    ]
    for url in ipv6_blocked:
        with pytest.raises(SSRFError, match="SSRF blocked"):
            validate_url(url, allow_private=False)


def test_ssrf_blocks_decimal_and_hex_ips() -> None:
    """Security Test 6: Obfuscated decimal and hex IP representations must be blocked."""
    # 2130706433 is 127.0.0.1 in decimal integer
    # 0x7f000001 is 127.0.0.1 in hex
    # 2852039166 is 169.254.169.254 in decimal integer
    obfuscated_urls = [
        "https://2130706433/webhook",
        "https://0x7f000001/webhook",
        "https://2852039166/meta-data",
        "https://0xa9fea9fe/meta-data",
    ]
    for url in obfuscated_urls:
        with pytest.raises(SSRFError, match="SSRF blocked"):
            validate_url(url, allow_private=False)


def test_ssrf_blocks_non_https_unless_explicitly_allowed() -> None:
    """Security: Non-https schemes (http, ftp, gopher, file) must be blocked by default."""
    bad_schemes = [
        "http://api.openai.com/v1",
        "ftp://example.com/file",
        "file:///etc/passwd",
        "gopher://example.com",
    ]
    for url in bad_schemes:
        with pytest.raises(SSRFError):
            validate_url(url, allow_private=False)


def test_valid_public_https_url_passes() -> None:
    """Legitimate public HTTPS endpoint should pass validation."""
    valid_url = "https://api.openai.com/v1"
    assert validate_url(valid_url, allow_private=False) == valid_url
