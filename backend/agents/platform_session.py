import os
import sys
import json
import shutil
import sqlite3
import logging
import subprocess
import datetime
from pathlib import Path
from typing import Dict, Any

from backend.config import settings

logger = logging.getLogger("jobpilot.platform_session")

STATUS_FILE = Path(settings.DATA_DIR) / "platform_status.json"

def get_cookie_file_path() -> Path:
    p1 = Path(settings.BROWSER_PROFILE_DIR) / "Default" / "Network" / "Cookies"
    if p1.exists():
        return p1
    p2 = Path(settings.BROWSER_PROFILE_DIR) / "Default" / "Cookies"
    return p2

def check_cookies_db(domain_substr: str, token_names: list) -> bool:
    """Safely checks SQLite cookie store for session tokens."""
    cookie_file = get_cookie_file_path()
    if not cookie_file.exists():
        return False

    temp_copy = Path(settings.DATA_DIR) / f"temp_check_{domain_substr}.db"
    try:
        shutil.copyfile(cookie_file, temp_copy)
        conn = sqlite3.connect(temp_copy)
        c = conn.cursor()
        query = f"SELECT name FROM cookies WHERE host_key LIKE ?"
        c.execute(query, (f"%{domain_substr}%",))
        rows = [r[0] for r in c.fetchall()]
        conn.close()
        return any(t in rows for t in token_names)
    except Exception as e:
        logger.debug(f"Cookie check error for {domain_substr}: {e}")
        return False
    finally:
        if temp_copy.exists():
            try:
                temp_copy.unlink()
            except Exception:
                pass

def get_platform_status(platform: str) -> Dict[str, Any]:
    """
    Returns login status for a platform by checking:
    1. Saved platform_status.json
    2. Persistent Chromium profile cookie store
    """
    platform = platform.lower()
    cached_status = False
    details = "Not logged in"
    updated_at = None

    if STATUS_FILE.exists():
        try:
            data = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
            if platform in data:
                cached_status = bool(data[platform].get("logged_in", False))
                details = data[platform].get("details", details)
                updated_at = data[platform].get("updated_at")
        except Exception:
            pass

    # If not confirmed via status file, verify directly via profile cookies
    if not cached_status:
        if platform == "internshala":
            is_logged_in = check_cookies_db("internshala", ["in_user_id", "user_id", "user_key", "in_session", "PHPSESSID"])
            if is_logged_in:
                cached_status = True
                details = "Session cookie detected in browser profile"
        elif platform == "naukri":
            is_logged_in = check_cookies_db("naukri", ["nauk_user", "nk_token", "USER", "logged_in", "user_id"])
            if is_logged_in:
                cached_status = True
                details = "Session cookie detected in browser profile"

    return {
        "platform": platform,
        "logged_in": cached_status,
        "details": details,
        "updated_at": updated_at or datetime.datetime.utcnow().isoformat()
    }

def get_all_platforms_status() -> Dict[str, Any]:
    internshala_st = get_platform_status("internshala")
    naukri_st = get_platform_status("naukri")
    return {
        "internshala": internshala_st,
        "naukri": naukri_st,
        "all_ready": internshala_st["logged_in"] # Primary platform is Internshala
    }

def launch_browser_login_subprocess(platform: str, url: str = None) -> Dict[str, Any]:
    """
    Spawns browser_launcher in a completely separate OS process.
    Never blocks or conflicts with uvicorn event loops or --reload watchers.
    """
    if platform not in ["internshala", "naukri"]:
        platform = "internshala"

    target_url = url
    if not target_url:
        if platform == "internshala":
            target_url = "https://internshala.com/login/user"
        else:
            target_url = "https://www.naukri.com/nlogin/login"

    cmd = [
        sys.executable,
        "-m",
        "backend.agents.browser_launcher",
        "--platform",
        platform,
        "--url",
        target_url
    ]

    try:
        # Launch detached subprocess so it runs independently of uvicorn
        creation_flags = 0
        if sys.platform == "win32":
            # CREATE_NEW_PROCESS_GROUP = 0x00000200, DETACHED_PROCESS = 0x00000008
            creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

        proc = subprocess.Popen(
            cmd,
            creationflags=creation_flags,
            close_fds=(sys.platform != "win32")
        )

        return {
            "status": "opened",
            "pid": proc.pid,
            "platform": platform,
            "url": target_url,
            "message": f"Persistent browser opened for {platform.capitalize()} login. Please complete login in the opened window."
        }
    except Exception as e:
        logger.error(f"Failed to launch browser subprocess: {e}", exc_info=True)
        return {
            "status": "error",
            "platform": platform,
            "error": str(e),
            "message": f"Failed to launch browser: {str(e)}"
        }

