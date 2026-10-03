# Security Policy

The security of LLM Gateway and the protection of provider credentials, user data, and system integrity is our highest priority.

---

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1.0 | :x:                |

---

## Reporting a Vulnerability

If you discover a security vulnerability within LLM Gateway, please **do NOT report it publicly** on GitHub Issues or discussions.

Instead, please send a detailed disclosure email to:
**security@llmgateway.example.com** (or through GitHub Private Vulnerability Reporting).

Please include:
- A description of the vulnerability and its potential impact.
- Clear reproduction steps or proof-of-concept (PoC).
- Any recommended remediation steps.

We will acknowledge receipt within 48 hours and work with you to coordinate a disclosure timeline and security release.

---

## Core Security Commitments

1. **Zero Secret Leakage**:
   - Provider API keys and gateway keys are never stored in plaintext or logged.
   - Credentials at rest are protected using AES-256-GCM authenticated encryption.
   - Secret redaction filters strip API keys, bearer tokens, and credentials from all logs and error streams.
2. **SSRF Hardening**:
   - Outbound requests (such as webhook notifications) strictly reject private IP ranges (RFC 1918), link-local addresses, loopback addresses, and cloud provider metadata IPs (e.g. 169.254.169.254).
3. **Session & Auth Protection**:
   - Passwords hashed using Argon2id with high memory and iteration parameters.
   - HttpOnly, SameSite, Secure cookies with cryptographic CSRF token validation.
   - Gateway keys verified via constant-time SHA-256 hash comparison.
