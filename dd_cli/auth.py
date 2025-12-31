"""Authentication handling for Datadog web session."""

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from datetime import datetime


@dataclass
class Auth:
    """Datadog web session authentication."""
    dogweb_cookie: str
    csrf_token: str
    base_url: str = "https://app.datadoghq.eu"
    created_at: Optional[datetime] = None


def get_auth_file_path() -> Path:
    """Get the path to the auth file."""
    return Path.home() / ".datadog-auth"


def load_auth() -> Optional[Auth]:
    """Load authentication from ~/.datadog-auth file."""
    auth_file = get_auth_file_path()
    
    if not auth_file.exists():
        return None
    
    dogweb_cookie = None
    csrf_token = None
    base_url = "https://app.datadoghq.eu"
    created_at = None
    
    with open(auth_file, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("#"):
                # Parse created timestamp from comment
                if "Created:" in line:
                    try:
                        date_str = line.split("Created:")[1].strip()
                        created_at = datetime.fromisoformat(date_str)
                    except (ValueError, IndexError):
                        pass
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                
                if key == "DOGWEB_COOKIE":
                    dogweb_cookie = value
                elif key == "CSRF_TOKEN":
                    csrf_token = value
                elif key == "DD_BASE_URL":
                    base_url = value
    
    if not dogweb_cookie or not csrf_token:
        return None
    
    return Auth(
        dogweb_cookie=dogweb_cookie,
        csrf_token=csrf_token,
        base_url=base_url,
        created_at=created_at,
    )


def save_auth(auth: Auth) -> None:
    """Save authentication to ~/.datadog-auth file."""
    auth_file = get_auth_file_path()
    
    with open(auth_file, "w") as f:
        f.write("# Datadog auth tokens - regenerate when expired\n")
        f.write(f'# Created: {datetime.now().isoformat()}\n')
        f.write(f'DOGWEB_COOKIE="{auth.dogweb_cookie}"\n')
        f.write(f'CSRF_TOKEN="{auth.csrf_token}"\n')
        if auth.base_url != "https://app.datadoghq.eu":
            f.write(f'DD_BASE_URL="{auth.base_url}"\n')
    
    # Secure the file
    os.chmod(auth_file, 0o600)


def interactive_auth_setup() -> Auth:
    """Interactive prompt to set up authentication."""
    print("Datadog Auth Setup", file=sys.stderr)
    print("=" * 40, file=sys.stderr)
    print("", file=sys.stderr)
    print("1. Open https://app.datadoghq.eu/logs in Chrome", file=sys.stderr)
    print("2. Open DevTools (F12) → Network tab", file=sys.stderr)
    print("3. Perform any search", file=sys.stderr)
    print("4. Find a request to 'logs-analytics'", file=sys.stderr)
    print("5. Right-click → Copy as cURL", file=sys.stderr)
    print("", file=sys.stderr)
    print("From that curl command, extract:", file=sys.stderr)
    print("", file=sys.stderr)
    
    dogweb = input("dogweb cookie value: ").strip()
    csrf = input("x-csrf-token header value: ").strip()
    
    auth = Auth(dogweb_cookie=dogweb, csrf_token=csrf)
    save_auth(auth)
    
    print(f"\n✓ Auth saved to {get_auth_file_path()}", file=sys.stderr)
    return auth
