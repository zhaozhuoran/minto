import os
import sys
import asyncio
import logging

# ASCII Art banner and information
BANNER = r"""
 ___  ___  _  _  _  _  ___
 |  \/  | | || \| ||_ _| ___
 | |\/| | | ||    | | | / _ \
 |_|  |_| |_||_|\_| |_| \___/

Welcome to Minto Proxy 1.0!
Minecraft Proxy & Hostname Rewrite Tool
"""

async def shutdown(logger_instance, proxy_instances):
    """Graceful shutdown of all services and timers."""
    logging.info("Initiating graceful shutdown...")
    for inst in proxy_instances:
        try:
            await asyncio.wait_for(inst.stop(), timeout=3.0)
        except asyncio.TimeoutError:
            logging.warning(f"Timeout stopping a proxy instance; proceeding.")
    try:
        await asyncio.wait_for(logger_instance.stop(), timeout=3.0)
    except asyncio.TimeoutError:
        logging.warning("Timeout stopping logger; proceeding.")
    logging.info("All services shutdown. Goodbye!")


def print_banner():
    # Multi-colored banner using ANSI escape sequence (light pink/purple/cyan palette)
    pink = "\x1b[38;5;218m"
    cyan = "\x1b[36;1m"
    reset = "\x1b[0m"
    print(pink + BANNER + reset)


async def main():
    print_banner()

    # Import inside main to make sure directory structures can be loaded cleanly
    from minto.config import ConfigManager

    # 1. Check and generate config file if needed
    config_manager = ConfigManager()
    if not config_manager.ensure_config_exists():
        # Prints message and exits as requested
        print("\x1b[33m[!] Config template generated at 'config/config.json'. Please review/modify it and restart Minto.\x1b[0m")
        sys.exit(0)

    # 2. Load configuration
    try:
        config_data = config_manager.load_config()
    except Exception as e:
        print(f"\x1b[31m[!] Failed to load configuration file: {e}\x1b[0m")
        sys.exit(1)

    # 3. Setup Logger
    from minto.logger import MintoLogger
    log_cfg = config_manager.log_config
    minto_logger = MintoLogger(
        level=log_cfg.get("Level", "INFO"),
        console_out=log_cfg.get("Console", True),
        file_out=log_cfg.get("File", True)
    )
    minto_logger.start_archiver()

    logger = minto_logger.get_logger("MintoMain")
    logger.info("Initializing Minto Proxy...")

    # 4. Instantiate and start Minecraft proxy services
    from minto.proxy import MinecraftProxyInstance
    proxy_instances = []

    for s_cfg in config_manager.services:
        inst = MinecraftProxyInstance(s_cfg)
        proxy_instances.append(inst)
        await inst.start()

    # 5. Keep running and listen for interruption/shutdown
    loop = asyncio.get_running_loop()

    # Handle OS signals on supported platforms (like Linux/MacOS)
    stop_event = asyncio.Event()

    if sys.platform != "win32":
        import signal
        def signal_handler():
            stop_event.set()

        loop.add_signal_handler(signal.SIGINT, signal_handler)
        loop.add_signal_handler(signal.SIGTERM, signal_handler)

    try:
        if sys.platform == "win32":
            # On Windows, signal handler is not supported in asyncio. Sleep in loop to catch KeyboardInterrupt.
            while not stop_event.is_set():
                await asyncio.sleep(1)
        else:
            await stop_event.wait()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Minto received termination signal.")
    finally:
        await shutdown(minto_logger, proxy_instances)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
