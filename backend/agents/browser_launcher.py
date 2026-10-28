import os
import sys
import json
import asyncio
import argparse
import datetime
from pathlib import Path

# On Windows, ensure ProactorEventLoop is used so Playwright driver can spawn subprocesses
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from backend.config import settings

STATUS_FILE = Path(settings.DATA_DIR) / "platform_status.json"

def update_platform_status(platform: str, logged_in: bool, details: str = ""):
    status_data = {}
    if STATUS_FILE.exists():
        try:
            status_data = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        except Exception:
            status_data = {}
    status_data[platform] = {
        "logged_in": logged_in,
        "details": details,
        "updated_at": datetime.datetime.utcnow().isoformat()
    }
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(json.dumps(status_data, indent=2), encoding="utf-8")

async def check_page_logged_in(page, context, platform: str) -> bool:
    try:
        url = page.url.lower()
        cookies = await context.cookies()
        if platform == "internshala":
            # URL check: redirected away from login/registration to dashboard/jobs/student
            url_logged_in = ("internshala.com" in url and 
                             "login" not in url and 
                             "registration" not in url and 
                             ("student" in url or "dashboard" in url or "user" in url or "profile" in url or url.rstrip("/").endswith("internshala.com")))
            
            # Cookie check
            cookie_names = [c.get("name") for c in cookies if "internshala" in c.get("domain", "")]
            has_user_cookie = any(name in ["in_user_id", "user_id", "user_key", "in_session", "PHPSESSID"] for name in cookie_names)
            return url_logged_in or has_user_cookie
            
        elif platform == "naukri":
            url_logged_in = ("naukri.com" in url and 
                             "login" not in url and 
                             ("homepage" in url or "mnjuser" in url or "mynaukri" in url or "profile" in url))
            cookie_names = [c.get("name") for c in cookies if "naukri" in c.get("domain", "")]
            has_user_cookie = any(name in ["nauk_user", "nk_token", "USER", "logged_in", "user_id"] for name in cookie_names)
            return url_logged_in or has_user_cookie
    except Exception:
        pass
    return False

async def launch_and_monitor(platform: str, target_url: str):
    from playwright.async_api import async_playwright

    profile_dir = Path(settings.BROWSER_PROFILE_DIR).resolve()
    profile_dir.mkdir(parents=True, exist_ok=True)

    print(f"Launching persistent browser context in {profile_dir} for {platform}...")
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            viewport={"width": 1280, "height": 800},
            args=["--disable-blink-features=AutomationControlled"]
        )

        page = await context.new_page()
        try:
            await page.goto(target_url, timeout=45000)
        except Exception as e:
            print(f"Navigation warning: {e}")

        # Check initial status
        logged_in = await check_page_logged_in(page, context, platform)
        update_platform_status(platform, logged_in, "Initial check upon opening")

        # Monitor loop while browser remains open
        # Checks every 2 seconds for login
        try:
            for _ in range(300): # Monitor up to 10 minutes
                if context.pages:
                    active_page = context.pages[-1]
                    logged_in = await check_page_logged_in(active_page, context, platform)
                    if logged_in:
                        update_platform_status(platform, True, f"Logged in detected at {active_page.url}")
                        print(f"[SUCCESS] Logged in to {platform} successfully detected!")
                else:
                    break
                await asyncio.sleep(2)
        except Exception as e:
            print(f"Monitoring loop ended: {e}")
        finally:
            try:
                await context.close()
            except Exception:
                pass

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", default="internshala", choices=["internshala", "naukri"])
    parser.add_argument("--url", default=None)
    args = parser.parse_args()

    url = args.url
    if not url:
        if args.platform == "internshala":
            url = "https://internshala.com/login/user"
        else:
            url = "https://www.naukri.com/nlogin/login"

    asyncio.run(launch_and_monitor(args.platform, url))

if __name__ == "__main__":
    main()

