"""Diagnostic script to test configured Gemini API keys directly."""

import sys
from pathlib import Path
import httpx

backend_dir = Path(__file__).resolve().parent.parent
env_path = backend_dir / ".env"

env_vars = {}
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            env_vars[k.strip()] = v.strip()

key_names = [
    "GEMINI_API_KEY",
    "GEMINI_API_A_KEY",
    "GEMINI_API_B_KEY",
    "GEMINI_API_C_KEY",
    "GOOGLE_API_D_KEY",
    "GOOGLE_API_KEY",
]

payload = {
    "contents": [{"parts": [{"text": "Say hello"}]}]
}

# Test modern and supported model names
test_models = ["gemini-2.5-flash", "gemini-3.8-flash"]

print(f"Reading keys from: {env_path}\n", flush=True)

for name in key_names:
    val = env_vars.get(name)
    if not val:
        print(f"[{name}]: NOT CONFIGURED IN .env", flush=True)
        continue

    masked = f"{val[:4]}...{val[-4:]}" if len(val) > 8 else "***"

    if val.lower() in ("your_key_here", "placeholder", "none", "") or val.lower().startswith("your_"):
        print(f"[{name}] ({masked}): SKIPPED (Placeholder value)", flush=True)
        continue

    print(f"[{name}] ({masked}):", flush=True)
    success = False
    for mod in test_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={val}"
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(url, json=payload)
                print(f"  Model '{mod}': HTTP {resp.status_code}", flush=True)
                if resp.status_code == 200:
                    data = resp.json()
                    text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    print(f"    -> SUCCESS: {text[:60].strip()}...", flush=True)
                    success = True
                    break
                else:
                    detail = resp.text[:140].replace("\n", " ").strip()
                    print(f"    -> ERROR DETAIL: {detail}", flush=True)
        except httpx.TimeoutException as te:
            print(f"  Model '{mod}': TIMEOUT ({type(te).__name__}: {str(te)})", flush=True)
        except httpx.RequestError as re_err:
            print(f"  Model '{mod}': REQUEST ERROR ({type(re_err).__name__}: {str(re_err)})", flush=True)
        except Exception as exc:
            print(f"  Model '{mod}': EXCEPTION ({type(exc).__name__}: {str(exc)})", flush=True)

    print("-" * 50, flush=True)

