import asyncio
import random
import os
import datetime
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from playwright.async_api import async_playwright, BrowserContext, Page
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.config import settings
from backend.vault.models import JobApplication, JobPreference, Resume, DocumentVault, ActivityLog, SavedQuestionAnswer
from backend.agents.field_resolver import FieldResolver

logger = logging.getLogger("jobpilot.form_filler")

class PlaywrightFormFiller:
    """
    Playwright browser engine with persistent profile context, human-like delays,
    multi-page navigation, resume selection, cover letter generation, assignment questions,
    and responsive Blocker / 'Needs You' alert management with configurable timeout.
    """

    def __init__(self, headless: bool = False):
        self.headless = headless
        self.playwright = None
        self.context: Optional[BrowserContext] = None
        self.profile_dir = Path(settings.BROWSER_PROFILE_DIR).resolve()
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        # In-memory dictionary for blocker answers signaled by the dashboard in real-time
        # {application_id: asyncio.Event} and {application_id: answer_data}
        self.pending_blockers: Dict[int, asyncio.Event] = {}
        self.provided_answers: Dict[int, str] = {}

    async def initialize_browser(self):
        if not self.playwright:
            self.playwright = await async_playwright().start()
        if not self.context:
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.profile_dir),
                headless=self.headless,
                viewport={"width": 1280, "height": 800},
                args=["--disable-blink-features=AutomationControlled"]
            )

    async def is_logged_in_to_internshala(self) -> bool:
        """Checks if active persistent browser context has saved Internshala session cookies."""
        try:
            await self.initialize_browser()
            cookies = await self.context.cookies(["https://internshala.com"])
            # Internshala session cookies include user login tokens (e.g. PHPSESSID, in_user_id, etc.)
            user_session_tokens = [c for c in cookies if c.get("name") in ["in_user_id", "user_id", "user_key", "in_session"]]
            if user_session_tokens:
                return True
            # Secondary check: inspect any cookies on internshala domain
            return any(c.get("name") in ["in_user_id", "user_id", "in_session"] for c in cookies)
        except Exception as e:
            logger.warning(f"Error checking Internshala login: {e}")
            return False

    async def open_manual_login_session(self, url: str = "https://internshala.com/login/user") -> Dict[str, Any]:
        """
        Opens persistent browser session for the user to log in manually once.
        JobPilot NEVER asks for or stores passwords.
        """
        await self.initialize_browser()
        page = await self.context.new_page()
        await page.goto(url, timeout=45000)
        return {
            "status": "opened",
            "message": "Persistent browser opened. Please log in manually. Your session cookies will be saved in your local browser profile."
        }

    async def close(self):
        if self.context:
            await self.context.close()
            self.context = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None

    async def human_delay(self, min_ms: int = 500, max_ms: int = 1500):
        ms = random.randint(min_ms, max_ms)
        await asyncio.sleep(ms / 1000.0)

    async def log_activity(self, message: str, session: AsyncSession):
        logger.info(message)
        log = ActivityLog(message=message)
        session.add(log)
        await session.commit()

    def signal_blocker_resolved(self, application_id: int, answer: str):
        """Called when user submits an answer via dashboard while job is waiting."""
        self.provided_answers[application_id] = answer
        event = self.pending_blockers.get(application_id)
        if event:
            event.set()

    async def fill_application(
        self,
        application_id: int,
        session: AsyncSession,
        override_resume_path: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        mode_override: Optional[str] = None,
        progress_callback: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Executes application filling.
        Supports DRY_RUN, REVIEW, and AUTO modes.
        Enforces DRY_RUN or REVIEW on first run unless explicitly set to AUTO.
        """
        stmt = select(JobApplication).where(JobApplication.id == application_id)
        res = await session.execute(stmt)
        app_record = res.scalars().first()
        if not app_record:
            return {"status": "error", "message": "Application record not found"}

        stmt_prefs = select(JobPreference).limit(1)
        prefs_res = await session.execute(stmt_prefs)
        prefs = prefs_res.scalars().first()

        # Enforce safe mode (Never auto-submit in first run unless explicitly configured)
        configured_mode = mode_override or (prefs.mode if prefs and prefs.mode else settings.APPLICATION_MODE).upper()
        if configured_mode not in ["DRY_RUN", "REVIEW", "AUTO"]:
            configured_mode = "DRY_RUN"
        mode = configured_mode

        wait_timeout = timeout_seconds or settings.HUMAN_ALERT_TIMEOUT_SECONDS

        await self.initialize_browser()
        page: Page = await self.context.new_page()

        submitted_answers = dict(app_record.answers_submitted or {})
        resume_path = override_resume_path

        # Resolve resume
        if not resume_path and app_record.resume_id:
            stmt_r = select(Resume).where(Resume.id == app_record.resume_id)
            r_res = await session.execute(stmt_r)
            r_entry = r_res.scalars().first()
            if r_entry:
                resume_path = r_entry.file_path
                app_record.resume_version_used = f"{r_entry.role_tag} v{r_entry.version}"

        try:
            await self.log_activity(f"Navigating to {app_record.apply_url} for {app_record.company}", session)

            if "127.0.0.1:8000/mock" in app_record.apply_url or "localhost:8000/mock" in app_record.apply_url:
                from backend.mock_form_server import HTML_PAGE_1
                mock_file = settings.data_path / "mock_page_1.html"
                mock_file.write_text(HTML_PAGE_1, encoding="utf-8")
                await page.goto(f"file:///{mock_file.resolve().as_posix()}", wait_until="load")
            else:
                try:
                    await page.goto(app_record.apply_url, timeout=30000)
                except Exception as net_err:
                    screenshot_path = str(settings.data_path / f"error_nav_{app_record.id}.png")
                    try:
                        await page.screenshot(path=screenshot_path)
                    except Exception:
                        pass
                    app_record.status = "failed"
                    app_record.skip_reason = f"Navigation error: {str(net_err)}"
                    await session.commit()
                    return {"status": "error", "message": f"Navigation failed: {net_err}"}

            if progress_callback:
                await progress_callback(f"Opening listing: {app_record.company} - {app_record.title}")

            # Check if login is required
            content = await page.content()
            if "log in" in content.lower() and "sign up" in content.lower() and ("password" in content.lower() or "login/user" in page.url):
                return await self._handle_blocker_flow(
                    page=page,
                    app_record=app_record,
                    reason="Login Required on Platform",
                    question_text="Please log into your Internshala account in Settings > Platforms first.",
                    session=session,
                    wait_timeout=wait_timeout
                )

            # If Internshala detail page, click 'Apply now' button with fallbacks
            if "internshala.com" in page.url and ("/job/detail/" in page.url or "/internship/detail/" in page.url):
                apply_button_selector = (
                    "button#apply_now_button, "
                    "a#apply_now_button, "
                    "button.apply_now_btn, "
                    "a.apply_now_button, "
                    "button:has-text('Apply now'), "
                    "a:has-text('Apply now')"
                )
                try:
                    btn = page.locator(apply_button_selector).first
                    if await btn.is_visible():
                        await self.log_activity("Clicking 'Apply now' on Internshala listing", session)
                        if progress_callback:
                            await progress_callback(f"Clicking Apply now for {app_record.company}")
                        await btn.click()
                        await self.human_delay(1500, 2500)
                except Exception as e:
                    logger.warning(f"Could not click initial apply button on Internshala: {e}")

            page_number = 1
            max_pages = 10

            while page_number <= max_pages:
                progress_msg = f"Filling page {page_number} for {app_record.company}"
                await self.log_activity(progress_msg, session)
                if progress_callback:
                    await progress_callback(progress_msg)
                await self.human_delay(600, 1200)

                # Check for OTP or Captcha blocker
                content = await page.content()
                if any(x in content.lower() for x in ["enter otp", "verification code", "captcha", "are you human"]):
                    return await self._handle_blocker_flow(
                        page=page,
                        app_record=app_record,
                        reason="OTP / CAPTCHA Verification Required",
                        question_text="Please solve the OTP / CAPTCHA in the browser.",
                        session=session,
                        wait_timeout=wait_timeout,
                        page_num=page_number,
                        filled_so_far=submitted_answers
                    )

                # 1. Fill inputs, textareas, selects
                input_locators = await page.locator("input, textarea, select").all()

                for locator in input_locators:
                    try:
                        if not await locator.is_visible():
                            continue

                        tag_name = await locator.evaluate("el => el.tagName.toLowerCase()")
                        input_type = await locator.get_attribute("type") or "text"
                        name_attr = await locator.get_attribute("name") or ""
                        id_attr = await locator.get_attribute("id") or ""
                        placeholder = await locator.get_attribute("placeholder") or ""

                        # Label extraction with fallbacks
                        label_text = await locator.evaluate("""el => {
                            let l = document.querySelector(`label[for="${el.id}"]`);
                            if (l) return l.innerText;
                            let parent = el.closest('label');
                            if (parent) return parent.innerText;
                            let prev = el.previousElementSibling;
                            if (prev && (prev.tagName === 'LABEL' || prev.tagName === 'SPAN' || prev.tagName === 'DIV')) return prev.innerText;
                            let header = el.closest('.form-group, .question_container, .assessment_question')?.querySelector('label, .heading, h4, h5');
                            if (header) return header.innerText;
                            return el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.name || '';
                        }""")

                        field_label = (label_text or placeholder or name_attr or id_attr).strip()
                        if not field_label:
                            continue

                        classified_type = FieldResolver.classify_field(field_label, input_type, tag_name)

                        # Handle File / Resume Upload or Selection
                        if classified_type == "file":
                            if "resume" in field_label.lower() or "cv" in field_label.lower():
                                if resume_path and os.path.exists(resume_path):
                                    await locator.set_input_files(resume_path)
                                    submitted_answers[field_label] = {"answer": Path(resume_path).name, "source": "resume_library"}
                                    await self.human_delay(400, 800)
                            continue

                        # Check if already filled
                        current_val = await locator.input_value() if tag_name != "select" else ""
                        if current_val:
                            continue

                        # Resolve field value through Vault, Grounded Engine, or Saved QA
                        resolved_val, source_tag = await FieldResolver.resolve_field_value(
                            field_label=field_label,
                            field_type=classified_type,
                            job_description=app_record.job_description or "",
                            session=session
                        )

                        if resolved_val is None:
                            # BLOCKER FLOW: Unknown field
                            blocker_res = await self._handle_blocker_flow(
                                page=page,
                                app_record=app_record,
                                reason=f"Unknown form field: {field_label}",
                                question_text=field_label,
                                session=session,
                                wait_timeout=wait_timeout,
                                page_num=page_number,
                                filled_so_far=submitted_answers
                            )

                            if blocker_res.get("status") == "answered_in_time":
                                resolved_val = blocker_res.get("answer")
                                source_tag = "user_interactive_answer"
                            else:
                                # Timeout expired -> Parked as 'Needs You' and returned so scheduler/filler moves to next job
                                return blocker_res

                        # Fill input element
                        if classified_type == "dropdown":
                            try:
                                await locator.select_option(label=resolved_val)
                            except Exception:
                                try:
                                    await locator.select_option(value=resolved_val)
                                except Exception:
                                    pass
                        elif classified_type in ["checkbox", "radio"]:
                            if str(resolved_val).lower() in ["true", "yes", "1"]:
                                await locator.check()
                        else:
                            await locator.click()
                            await self.human_delay(100, 250)
                            await locator.fill(str(resolved_val))
                            await self.human_delay(200, 500)

                        submitted_answers[field_label] = {"answer": resolved_val, "source": source_tag}

                    except Exception as field_err:
                        logger.debug(f"Input fill skipped: {field_err}")

                # Check for Next / Continue / Submit button with fallbacks
                next_btn = page.locator("button:has-text('Next'), input[value='Next'], button:has-text('Continue'), input[value='Continue']").first
                submit_btn = page.locator(
                    "button:has-text('Submit'), "
                    "input[type='submit'], "
                    "button:has-text('Apply Now'), "
                    "button:has-text('Submit application'), "
                    "button#submit, "
                    "button.submit_btn, "
                    "button:has-text('Complete')"
                ).first

                has_next = await next_btn.is_visible() if await next_btn.count() > 0 else False
                has_submit = await submit_btn.is_visible() if await submit_btn.count() > 0 else False

                if has_next:
                    await self.log_activity(f"Navigating to Next Page ({page_number + 1})", session)
                    if "127.0.0.1:8000/mock" in app_record.apply_url or "localhost:8000/mock" in app_record.apply_url:
                        from backend.mock_form_server import HTML_PAGE_2
                        mock_file_2 = settings.data_path / "mock_page_2.html"
                        mock_file_2.write_text(HTML_PAGE_2, encoding="utf-8")
                        await page.goto(f"file:///{mock_file_2.resolve().as_posix()}", wait_until="load")
                    else:
                        await next_btn.click()
                    await self.human_delay(600, 1200)
                    page_number += 1
                    continue
                elif has_submit:
                    # Final page reached
                    app_record.answers_submitted = submitted_answers

                    if mode == "DRY_RUN":
                        screenshot_path = str(settings.data_path / f"dry_run_{app_record.id}.png")
                        await page.screenshot(path=screenshot_path)
                        app_record.status = "matched"
                        msg = f"DRY RUN completed for {app_record.company}. Screenshot saved (stopped before submit)."
                        await self.log_activity(msg, session)
                        if progress_callback:
                            await progress_callback(msg)
                        await session.commit()
                        return {"status": "dry_run_complete", "screenshot": screenshot_path}

                    elif mode == "REVIEW":
                        screenshot_path = str(settings.data_path / f"review_{app_record.id}.png")
                        await page.screenshot(path=screenshot_path)
                        app_record.status = "needs_you"
                        app_record.needs_you_reason = "Review Mode: Awaiting one-click human approval before submit"
                        app_record.needs_you_question = "Approve final submission?"
                        app_record.needs_you_screenshot = screenshot_path
                        app_record.needs_you_timestamp = datetime.datetime.utcnow()
                        msg = f"Waiting for your approval for {app_record.company}"
                        await self.log_activity(msg, session)
                        if progress_callback:
                            await progress_callback(msg)
                        await session.commit()
                        return {"status": "review_pending", "message": "Paused for one-click approval"}

                    elif mode == "AUTO":
                        await submit_btn.click()
                        await self.human_delay(2000, 3000)
                        app_record.status = "applied"
                        app_record.applied_at = datetime.datetime.utcnow()
                        await self.log_activity(f"AUTO SUBMITTED application for {app_record.company}", session)
                        await session.commit()
                        return {"status": "applied", "message": "Successfully applied"}

                break # No further navigation buttons detected

            return {"status": "completed_pages", "answers": submitted_answers}

        except Exception as e:
            logger.error(f"Form filler error on {app_record.company}: {e}", exc_info=True)
            screenshot_path = str(settings.data_path / f"error_page_{app_record.id}.png")
            try:
                await page.screenshot(path=screenshot_path)
            except Exception:
                screenshot_path = None
            app_record.status = "failed"
            app_record.skip_reason = f"Automation error: {str(e)}"
            await session.commit()
            return {"status": "error", "message": str(e), "screenshot": screenshot_path}
        finally:
            await page.close()

    async def _handle_blocker_flow(
        self,
        page: Page,
        app_record: JobApplication,
        reason: str,
        question_text: str,
        session: AsyncSession,
        wait_timeout: int,
        page_num: int = 1,
        filled_so_far: Optional[dict] = None
    ) -> Dict[str, Any]:
        """
        BLOCKER FLOW:
        1. Capture screenshot and set job state with needs_you alert.
        2. Keep job paused for configurable wait (default 5 min or custom e.g. 10 sec).
        3. If answered in time via dashboard, save answer to vault & continue immediately.
        4. If timeout expires, park job as 'Needs You' with saved state and move to next job.
        """
        screenshot_path = str(settings.data_path / f"needs_you_{app_record.id}.png")
        try:
            await page.screenshot(path=screenshot_path)
        except Exception:
            screenshot_path = None

        app_record.status = "needs_you"
        app_record.needs_you_reason = reason
        app_record.needs_you_question = question_text
        app_record.needs_you_screenshot = screenshot_path
        app_record.needs_you_timestamp = datetime.datetime.utcnow()
        app_record.needs_you_state = {
            "page_num": page_num,
            "filled_fields": filled_so_far or {},
            "url": page.url
        }
        await self.log_activity(f"[NEEDS YOU ALERT] {reason} for {app_record.company}. Paused for {wait_timeout}s.", session)
        await session.commit()

        # Set up real-time event
        event = asyncio.Event()
        self.pending_blockers[app_record.id] = event

        try:
            # Wait for user answer or timeout
            await asyncio.wait_for(event.wait(), timeout=float(wait_timeout))
            user_answer = self.provided_answers.get(app_record.id, "")
            await self.log_activity(f"[ANSWER RECEIVED IN TIME] Continuing application {app_record.id} immediately.", session)
            return {
                "status": "answered_in_time",
                "answer": user_answer,
                "screenshot": screenshot_path
            }
        except asyncio.TimeoutError:
            # Timeout expired -> Job remains parked as 'Needs You' with saved state
            await self.log_activity(f"[TIMEOUT EXPIRED {wait_timeout}s] Parked {app_record.company} as 'Needs You' with saved state. Moving to next job.", session)
            return {
                "status": "needs_you",
                "reason": reason,
                "question": question_text,
                "screenshot": screenshot_path,
                "parked": True,
                "timed_out": True
            }
        finally:
            self.pending_blockers.pop(app_record.id, None)
            self.provided_answers.pop(app_record.id, None)

playwright_form_filler = PlaywrightFormFiller(headless=False)
