import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger("jobpilot.scheduler")

class JobPilotScheduler:
    """
    APScheduler background service managing recurring daily discovery runs
    with start, pause, stop, and kill switch controls.
    """
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.is_running = False
        self.is_paused = False
        self.kill_switch_active = False

    def start(self):
        if not self.scheduler.running:
            self.scheduler.start()
            self.is_running = True
            self.is_paused = False
            self.kill_switch_active = False
            logger.info("JobPilot APScheduler started.")

    def pause(self):
        if self.scheduler.running:
            self.scheduler.pause()
            self.is_paused = True
            logger.info("JobPilot APScheduler paused.")

    def resume(self):
        if self.scheduler.running:
            self.scheduler.resume()
            self.is_paused = False
            logger.info("JobPilot APScheduler resumed.")

    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            self.is_running = False
            logger.info("JobPilot APScheduler stopped.")

    def trigger_kill_switch(self):
        self.kill_switch_active = True
        if self.scheduler.running:
            self.scheduler.pause()
        logger.warning("KILL SWITCH ACTIVATED: All active and scheduled jobs halted.")

    def reset_kill_switch(self):
        self.kill_switch_active = False
        logger.info("Kill switch reset.")

jobpilot_scheduler = JobPilotScheduler()
