import os
import json
import logging
from typing import Any, Dict, List

DEFAULT_CONFIG = {
    "Log": {
        "Level": "INFO",
        "Console": True,
        "File": True
    },
    "Services": [
        {
            "Name": "Hypixel-in",
            "Listen": 25565,
            "TargetAddress": "mc.hypixel.net",
            "TargetPort": 25565,
            "IPAccess": {
                "Mode": "", # "accept" / "deny" / "" (disabled)
                "List": [] # list of IP strings
            },
            "Minecraft": {
                "EnableHostnameRewrite": True,
                "RewrittenHostname": "mc.hypixel.net",
                "OnlineCount": {
                    "Max": 2026,
                    "Online": -1, # -1 means proxy/actual current online count
                    "EnableMaxLimit": False
                },
                "NameAccess": {
                    "Mode": "", # "accept" / "deny" / "" (disabled)
                    "List": [] # list of player names
                },
                "PingMode": "disconnect", # "disconnect" / "0ms" / "normal"
                "MotdFavicon": "{DEFAULT_MOTD}",
                "MotdDescription": "§d{NAME}§e, provided by Minto §a§o\n§c§lProxy for §6§n{HOST}:{PORT}§r"
            }
        }
    ]
}


class ConfigManager:
    def __init__(self, config_dir: str = "config", config_file: str = "config.json"):
        self.config_dir = config_dir
        self.config_filepath = os.path.join(config_dir, config_file)
        self.config_data: Dict[str, Any] = {}

    def ensure_config_exists(self) -> bool:
        """
        Ensures that the config directory and config file exist.
        If not, creates them with default templates and returns False (indicating user should modify it).
        Otherwise returns True.
        """
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)

        if not os.path.exists(self.config_filepath):
            with open(self.config_filepath, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_CONFIG, f, indent=4, ensure_ascii=False)
            return False
        return True

    def load_config(self) -> Dict[str, Any]:
        """Loads and parses the config file."""
        if not os.path.exists(self.config_filepath):
            raise FileNotFoundError(f"Config file not found at {self.config_filepath}")

        with open(self.config_filepath, "r", encoding="utf-8") as f:
            self.config_data = json.load(f)
        return self.config_data

    @property
    def log_config(self) -> Dict[str, Any]:
        return self.config_data.get("Log", {"Level": "INFO", "Console": True, "File": True})

    @property
    def services(self) -> List[Dict[str, Any]]:
        return self.config_data.get("Services", [])
