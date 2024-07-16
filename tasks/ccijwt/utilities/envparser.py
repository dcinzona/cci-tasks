import os
import re

TOKEN_PATTERN = r"^\{([a-zA-Z0-9_]+)\}$"


def get_value_from_option(optval):
    isToken = re.match(TOKEN_PATTERN, optval)
    keyval = isToken.group(1) if isToken else optval
    return os.getenv(keyval) if keyval in os.environ else optval


def load_env_vars(path=".env"):
    """Loads env vars from a .env file into os.environ"""
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ[k] = v


def getCert(cert_path, trim=True):
    with open(cert_path, "r", encoding="utf-8") as f:
        cert = ""
        for line in f.readlines():
            if trim:
                cert += line.strip() if line.find("-----") == -1 else ""
            else:
                cert += line
        return cert


def getKey(trim=True):
    return getCert(os.getenv("_KEYPATH"), trim)
