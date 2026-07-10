import os
import sys
import logging
import zipfile
import asyncio
from datetime import datetime


class ColoredFormatter(logging.Formatter):
    """Custom formatter to print colourful messages in console."""
    GREY = "\x1b[38;20m"
    YELLOW = "\x1b[33;20m"
    RED = "\x1b[31;20m"
    BOLD_RED = "\x1b[31;1m"
    RESET = "\x1b[0m"
    GREEN = "\x1b[32m"
    BLUE = "\x1b[34m"

    FORMAT = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"

    FORMATS = {
        logging.DEBUG: GREY + FORMAT + RESET,
        logging.INFO: GREEN + FORMAT + RESET,
        logging.WARNING: YELLOW + FORMAT + RESET,
        logging.ERROR: RED + FORMAT + RESET,
        logging.CRITICAL: BOLD_RED + FORMAT + RESET
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno, self.GREY + self.FORMAT + self.RESET)
        formatter = logging.Formatter(log_fmt, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)


class MintoLogger:
    def __init__(self, log_dir: str = "logs", level: str = "INFO", console_out: bool = True, file_out: bool = True):
        self.log_dir = log_dir
        self.level = getattr(logging, level.upper(), logging.INFO)
        self.console_out = console_out
        self.file_out = file_out
        self.latest_filepath = os.path.join(log_dir, "latest.log")
        self._current_date = datetime.now().date()
        self._archive_task = None
        self._shutdown_event = asyncio.Event()

        # Ensure logs dir exists
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

        # Setup python root logger
        self.root_logger = logging.getLogger()
        self.root_logger.setLevel(self.level)

        # Clear existing handlers
        self.root_logger.handlers = []

        # Console handler
        if self.console_out:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(ColoredFormatter())
            self.root_logger.addHandler(console_handler)

        # File handler
        self.file_handler = None
        if self.file_out:
            self.file_handler = logging.FileHandler(self.latest_filepath, encoding="utf-8")
            file_formatter = logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
            self.file_handler.setFormatter(file_formatter)
            self.root_logger.addHandler(self.file_handler)

    def get_logger(self, name: str) -> logging.Logger:
        return logging.getLogger(name)

    def _do_blocking_archive(self, zip_filepath: str, date_str: str):
        """The blocking zip and file truncate logic, safe to run in an executor thread."""
        try:
            # Create a zip archive
            with zipfile.ZipFile(zip_filepath, "w", zipfile.ZIP_DEFLATED) as zipf:
                # Add latest.log as date_str.log inside the zip file
                zipf.write(self.latest_filepath, arcname=f"{date_str}.log")

            # Truncate latest.log
            with open(self.latest_filepath, "w", encoding="utf-8") as f:
                f.write("")
        except Exception as e:
            sys.stderr.write(f"Failed to archive latest.log to {zip_filepath}: {e}\n")

    def archive_current_log(self, date_str: str):
        """Archives the current latest.log to date_str.zip and truncates latest.log (blocking/synchronous version)."""
        if not os.path.exists(self.latest_filepath) or os.path.getsize(self.latest_filepath) == 0:
            return

        zip_filepath = os.path.join(self.log_dir, f"{date_str}.zip")

        # Close file handler temporarily to release file lock on Windows/Linux
        if self.file_handler:
            self.root_logger.removeHandler(self.file_handler)
            self.file_handler.close()

        try:
            self._do_blocking_archive(zip_filepath, date_str)
            logging.info(f"Successfully archived log to {zip_filepath}")
        finally:
            # Recreate & attach file handler
            if self.file_out:
                self.file_handler = logging.FileHandler(self.latest_filepath, encoding="utf-8")
                file_formatter = logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
                self.file_handler.setFormatter(file_formatter)
                self.root_logger.addHandler(self.file_handler)

    async def async_archive_current_log(self, date_str: str):
        """Asynchronously archives current log by offloading heavy I/O to executor."""
        if not os.path.exists(self.latest_filepath) or os.path.getsize(self.latest_filepath) == 0:
            return

        zip_filepath = os.path.join(self.log_dir, f"{date_str}.zip")

        # Close file handler on main event loop thread
        if self.file_handler:
            self.root_logger.removeHandler(self.file_handler)
            self.file_handler.close()

        try:
            # Offload heavy zip compression and disk write I/O to executor
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._do_blocking_archive, zip_filepath, date_str)
            logging.info(f"Successfully archived log asynchronously to {zip_filepath}")
        except Exception as e:
            sys.stderr.write(f"Failed asynchronous archive: {e}\n")
        finally:
            # Recreate & attach file handler on main event loop thread
            if self.file_out:
                self.file_handler = logging.FileHandler(self.latest_filepath, encoding="utf-8")
                file_formatter = logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
                self.file_handler.setFormatter(file_formatter)
                self.root_logger.addHandler(self.file_handler)

    async def _archive_loop(self):
        """Asynchronous background loop to check for day transition and auto-archive."""
        while not self._shutdown_event.is_set():
            try:
                # Sleep and check every 10 seconds (highly responsive & clean)
                await asyncio.sleep(10)
                now_date = datetime.now().date()
                if now_date > self._current_date:
                    # Date transitioned! Archive previous date
                    prev_date_str = self._current_date.strftime("%Y-%m-%d")
                    await self.async_archive_current_log(prev_date_str)
                    self._current_date = now_date
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Error in MintoLogger archive loop: {e}")

    def start_archiver(self):
        """Starts the background log archiver task."""
        # Archive any leftover/unfinished log from a previous day first
        # We can compare the last modified date of latest.log with today
        if os.path.exists(self.latest_filepath) and os.path.getsize(self.latest_filepath) > 0:
            mtime = os.path.getmtime(self.latest_filepath)
            last_date = datetime.fromtimestamp(mtime).date()
            if last_date < datetime.now().date():
                last_date_str = last_date.strftime("%Y-%m-%d")
                self.archive_current_log(last_date_str)

        self._archive_task = asyncio.create_task(self._archive_loop())

    async def stop(self):
        """Stops the log archiver loop and cleans up."""
        self._shutdown_event.set()
        if self._archive_task:
            self._archive_task.cancel()
            try:
                await self._archive_task
            except asyncio.CancelledError:
                pass

        # Finally, flush and close the file handler
        if self.file_handler:
            self.root_logger.removeHandler(self.file_handler)
            self.file_handler.close()
