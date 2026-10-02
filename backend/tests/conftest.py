import base64
import os

# Ensure valid test environment before any application module is imported
TEST_MASTER_KEY = base64.b64encode(b"0123456789abcdef0123456789abcdef").decode()
os.environ.setdefault("GATEWAY_MASTER_KEY", TEST_MASTER_KEY)
os.environ.setdefault("ENV", "test")
os.environ.setdefault("PUBLIC_URL", "http://localhost:3000")
