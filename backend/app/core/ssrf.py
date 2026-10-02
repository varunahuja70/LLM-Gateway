import ipaddress
import socket
from urllib.parse import urlparse

from app.config import get_settings


class SSRFError(ValueError):
    """Raised when a URL violates SSRF safety rules."""


# Blocked IPv4 networks
BLOCKED_IPV4_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),  # Current network
    ipaddress.ip_network("10.0.0.0/8"),  # Private RFC 1918
    ipaddress.ip_network("100.64.0.0/10"),  # Shared address space / CGNAT
    ipaddress.ip_network("127.0.0.0/8"),  # Loopback
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local / Cloud metadata (169.254.169.254)
    ipaddress.ip_network("172.16.0.0/12"),  # Private RFC 1918
    ipaddress.ip_network("192.0.0.0/24"),  # IETF protocol assignments
    ipaddress.ip_network("192.0.2.0/24"),  # Documentation (TEST-NET-1)
    ipaddress.ip_network("192.88.99.0/24"),  # 6to4 relay anycast
    ipaddress.ip_network("192.168.0.0/16"),  # Private RFC 1918
    ipaddress.ip_network("198.18.0.0/15"),  # Benchmarking
    ipaddress.ip_network("198.51.100.0/24"),  # Documentation (TEST-NET-2)
    ipaddress.ip_network("203.0.113.0/24"),  # Documentation (TEST-NET-3)
    ipaddress.ip_network("224.0.0.0/4"),  # Multicast
    ipaddress.ip_network("240.0.0.0/4"),  # Reserved for future use
    ipaddress.ip_network("255.255.255.255/32"),  # Broadcast
]

# Blocked IPv6 networks
BLOCKED_IPV6_NETWORKS = [
    ipaddress.ip_network("::/128"),  # Unspecified
    ipaddress.ip_network("::1/128"),  # Loopback
    ipaddress.ip_network("::ffff:0:0/96"),  # IPv4-mapped (handled specifically as well)
    ipaddress.ip_network("100::/64"),  # Discard-only prefix
    ipaddress.ip_network("2001:db8::/32"),  # Documentation
    ipaddress.ip_network("fc00::/7"),  # Unique local (ULA)
    ipaddress.ip_network("fe80::/10"),  # Link-local unicast
    ipaddress.ip_network("ff00::/8"),  # Multicast
]


def is_ip_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check if an IP address belongs to any blocked private/internal ranges."""
    # Check if IPv4-mapped IPv6 address (e.g. ::ffff:127.0.0.1 or ::ffff:169.254.169.254)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        return is_ip_blocked(ip.ipv4_mapped)

    # General standard checks
    if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_multicast or ip.is_reserved:
        return True

    if isinstance(ip, ipaddress.IPv4Address):
        for net in BLOCKED_IPV4_NETWORKS:
            if ip in net:
                return True
    elif isinstance(ip, ipaddress.IPv6Address):
        for net in BLOCKED_IPV6_NETWORKS:
            if ip in net:
                return True

    return False


def _parse_as_ip_literal(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """Attempt to parse host as direct IPv4 or IPv6 address, including decimal/hex forms."""
    # Strip brackets for IPv6 literals (e.g. [::1])
    clean_host = host.strip("[]")

    # Try standard IPv4 or IPv6 parse
    try:
        return ipaddress.ip_address(clean_host)
    except ValueError:
        pass

    # Try integer/decimal/hex/octal forms (e.g., 2130706433 or 0x7f000001)
    try:
        int_val = int(clean_host, 0)
        if 0 <= int_val <= 0xFFFFFFFF:
            return ipaddress.IPv4Address(int_val)
    except (ValueError, TypeError):
        pass

    return None


def validate_url(url: str, allow_private: bool | None = None) -> str:
    """Validate a user-supplied URL against SSRF rules.

    Raises SSRFError if the URL is invalid or targets internal/private/loopback resources.
    Returns cleaned URL string if valid.
    """
    if not url or not url.strip():
        raise SSRFError("URL cannot be empty.")

    url = url.strip()
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise SSRFError(f"Malformed URL: {e}") from e

    scheme = parsed.scheme.lower()
    if not scheme:
        raise SSRFError("URL must include an explicit scheme (e.g. https://).")

    if allow_private is None:
        settings = get_settings()
        allow_private = settings.ALLOW_PRIVATE_PROVIDER_URLS

    # Scheme restrictions
    if allow_private:
        if scheme not in ("https", "http"):
            raise SSRFError("Scheme must be https or http.")
    else:
        if scheme != "https":
            raise SSRFError("Only https scheme is permitted.")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFError("URL must contain a valid hostname.")

    hostname = hostname.lower()

    # Check for direct IP literal in hostname
    literal_ip = _parse_as_ip_literal(hostname)
    if literal_ip is not None:
        if allow_private and (literal_ip.is_loopback or str(literal_ip) == "127.0.0.1"):
            return url
        if is_ip_blocked(literal_ip):
            raise SSRFError(
                f"SSRF blocked: IP address '{literal_ip}' is in a reserved/private/loopback range."
            )
        return url

    # Localhost string check
    if hostname in ("localhost", "localhost.localdomain"):
        if allow_private:
            return url
        raise SSRFError("SSRF blocked: localhost is not permitted.")

    # Resolve domain to IP addresses via DNS
    try:
        addr_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror as e:
        raise SSRFError(f"DNS resolution failed for hostname '{hostname}': {e}") from e

    resolved_ips: set[str] = set()
    for item in addr_info:
        ip_str = str(item[4][0])
        resolved_ips.add(ip_str)

    if not resolved_ips:
        raise SSRFError(f"No IP addresses resolved for hostname '{hostname}'.")

    for ip_str in resolved_ips:
        resolved_ip = ipaddress.ip_address(ip_str)
        if allow_private and resolved_ip.is_loopback:
            continue
        if is_ip_blocked(resolved_ip):
            raise SSRFError(
                f"SSRF blocked: hostname '{hostname}' resolves to blocked IP '{resolved_ip}'."
            )

    return url
