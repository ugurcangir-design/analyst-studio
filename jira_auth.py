"""
Jira OAuth 2.0 (3-legged) yetkilendirme yardımcıları.
Web app callback: http://localhost:5003/api/jira/callback
"""

import os
import requests
from pathlib import Path
from urllib.parse import urlencode
from dotenv import load_dotenv

ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# Callback URL — Atlassian developer console'da KAYITLI olan ile birebir
# eşleşmelidir. Port veya host farklıysa .env'den override edilebilir:
#   JIRA_REDIRECT_URI=http://localhost:5003/api/jira/callback
# Aksi halde PORT env'inden türetilir (varsayılan localhost:5003).
def _redirect_uri_belirle() -> str:
    acik = os.getenv("JIRA_REDIRECT_URI", "").strip()
    if acik:
        return acik
    port = os.getenv("PORT", "5003")
    host = os.getenv("JIRA_CALLBACK_HOST", "localhost")
    return f"http://{host}:{port}/api/jira/callback"


REDIRECT_URI = _redirect_uri_belirle()
OAUTH_SCOPE  = (
    "read:jira-work write:jira-work read:jira-user offline_access "
    # Confluence classic scopes (v1 API destekliyorsa)
    "read:confluence-space.summary read:confluence-content.all "
    "read:confluence-content.summary write:confluence-content "
    # Confluence granular scopes (Modern Mode / v2 API için zorunlu)
    "read:space:confluence read:page:confluence write:page:confluence"
)


def env_al(key: str) -> str:
    return os.getenv(key, "")


def env_guncelle(key: str, value: str) -> None:
    from dotenv import set_key
    set_key(str(ENV_PATH), key, value)
    os.environ[key] = value


ESKI_STATE = "brd_analyst_auth"   # sabit state (geri uyum — app.py rastgele state'e geçene kadar)


def yeni_state() -> str:
    """OAuth CSRF koruması için her yetkilendirme başlangıcında RASTGELE `state` üretir
    (`secrets.token_urlsafe(24)`). Çağıran (app.py `/api/jira/auth-url`) bu değeri Flask
    `session`'a yazar ve `auth_url_olustur(state=...)`'a geçer; `/api/jira/callback`
    `request.args["state"]`'i session'daki değerle `secrets.compare_digest` ile kıyaslar,
    uyuşmazsa code değişimini REDDEDER ve session'daki state'i tek-kullanımlık olarak siler."""
    import secrets
    return secrets.token_urlsafe(24)


def state_dogrula(beklenen: str | None, gelen: str | None) -> bool:
    """Callback'teki `state`'i sabit-zamanlı kıyaslar (boş/None → False)."""
    import secrets
    if not beklenen or not gelen:
        return False
    return secrets.compare_digest(str(beklenen), str(gelen))


def auth_url_olustur(state: str | None = None) -> str:
    """Atlassian OAuth URL'ini döndür.

    `state`: `yeni_state()` ile üretilen rastgele değer (önerilen; app.py session'da saklayıp
    callback'te doğrular). None verilirse ESKİ sabit `brd_analyst_auth` kullanılır — mevcut app.py
    davranışı aynen korunur; orchestrator app.py'yi güncelleyince rastgele state devreye girer."""
    cid = env_al("JIRA_CLIENT_ID")
    if not cid:
        raise ValueError("JIRA_CLIENT_ID .env dosyasında tanımlı değil.")
    params = {
        "audience": "api.atlassian.com",
        "client_id": cid,
        "scope": OAUTH_SCOPE,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "prompt": "consent",
        "state": state or ESKI_STATE,
    }
    return "https://auth.atlassian.com/authorize?" + urlencode(params)


def token_al(auth_code: str) -> dict:
    """Authorization code ile access/refresh token al."""
    cid  = env_al("JIRA_CLIENT_ID")
    csec = env_al("JIRA_CLIENT_SECRET")
    r = requests.post(
        "https://auth.atlassian.com/oauth/token",
        json={
            "grant_type": "authorization_code",
            "client_id": cid,
            "client_secret": csec,
            "code": auth_code,
            "redirect_uri": REDIRECT_URI,
        },
        timeout=30,
    )
    return r.json()


def cloud_id_al(access_token: str) -> list[dict]:
    """Erişilebilir Jira instance'larını döndür."""
    r = requests.get(
        "https://api.atlassian.com/oauth/token/accessible-resources",
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        timeout=30,
    )
    return r.json() if r.status_code == 200 else []


def auth_tamamla(auth_code: str, cloud_index: int = 0) -> dict:
    """
    OAuth callback'ten sonra çağrılır.
    Returns: {task_key: str, cloud_id: str, cloud_name: str}
    """
    tokens = token_al(auth_code)
    if "access_token" not in tokens:
        raise RuntimeError(f"Token alınamadı: {tokens}")

    access_token  = tokens["access_token"]
    refresh_token = tokens.get("refresh_token", "")

    instances = cloud_id_al(access_token)
    if not instances:
        raise RuntimeError("Erişilebilir Jira instance bulunamadı.")

    if cloud_index >= len(instances):
        cloud_index = 0
    inst = instances[cloud_index]

    env_guncelle("JIRA_ACCESS_TOKEN", access_token)
    env_guncelle("JIRA_REFRESH_TOKEN", refresh_token)
    env_guncelle("JIRA_CLOUD_ID", inst["id"])

    return {
        "cloud_id": inst["id"],
        "cloud_name": inst.get("name", ""),
        "instances": instances,
    }
