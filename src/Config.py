#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
from dataclasses import dataclass, field
from .Ai import AiConfig
from .Rss import RssConfig
from .Utils import _Config
from .Notify import NotifyConfig, MatrixConfig
from datetime import tzinfo, datetime
from zoneinfo import ZoneInfo
from enum import Enum
from pathlib import Path


class LogLevel(Enum):
    SUCCESS = (5, "✅", "\033[32m")
    DEBUG = (10, "🐛", "\033[90m")
    INFO = (20, "ℹ️", "\033[34m")
    WARNING = (30, "⚠️", "\033[33m")
    ERROR = (40, "❌", "\033[31m")

    def __init__(self, level: int, emoji: str, color: str):
        self._value_ = level
        self._emoji = emoji
        self._color = color

    def __str__(self) -> str:
        return self.name

    @property
    def emoji(self) -> str:
        return self._emoji

    @property
    def color(self) -> str:
        return self._color

    @property
    def color_reset(self) -> str:
        return "\033[0m"

    @classmethod
    def from_string(cls, level_str: str | LogLevel) -> LogLevel:
        if isinstance(level_str, LogLevel):
            return level_str
        try:
            return cls[level_str.upper()]
        except (AttributeError, KeyError):
            print(f"⚠️ Unknown log level '{level_str}', fallback to INFO")
            return cls.INFO

    def to_emoji(self) -> str:
        return self.emoji

    def to_color(self) -> str:
        return self.color

    def warp(self, message: str, now: datetime = None, no_emoji: bool = False) -> str:
        """
        Wraps the message with the log level's color and emoji.
        """
        message = f"{self.emoji} {message}" if not no_emoji else message
        now = now or datetime.now()
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S %Z")
        return f"{self.color}[{timestamp}] [{self.name:<7}] {message}{self.color_reset}".strip()


@dataclass
class LogCfg:
    level: LogLevel = LogLevel.INFO
    file: Path = None
    to_console: bool = True

    @classmethod
    def load_from_dict(cls, dict_data: dict) -> "LogCfg":
        if not dict_data:
            return cls()
        level = LogLevel.from_string(dict_data.get("level", "INFO"))
        file = Path(dict_data.get("file", "")) if dict_data.get("file") else None
        to_console = dict_data.get("to_console", True)
        return cls(level=level, file=file, to_console=to_console)


@dataclass
class Config(_Config):
    ai: AiConfig
    log_cfg: LogCfg = field(default_factory=LogCfg)
    rss: dict[str, RssConfig] = field(default_factory=dict)
    rss_notify: dict[str, list[str]] = field(default_factory=dict)
    rss_enable: dict[str, list[bool]] = field(default_factory=dict)
    notifies: dict[str, NotifyConfig] = field(default_factory=dict)
    timezone: tzinfo = field(default=None)

    @classmethod
    def load_from_dict(cls, dict_data: dict) -> "Config":
        log_cfg: LogCfg = LogCfg.load_from_dict(dict_data.get("log", None))
        if "ai" in dict_data:
            ai_config = AiConfig.load_from_dict(dict_data["ai"])
        else:
            raise Exception("Cann't find AI config")
        rss_dict: dict = {}
        rss_notify: dict = {}
        rss_enable: dict = {}
        if "rss" in dict_data:
            for rss in dict_data["rss"]:
                notify = rss.pop("notify")
                notify = list(set(notify))
                try:
                    enable = rss.pop("enable")
                except Exception as e:
                    print(f"⚠️ RSS config missing 'enable' field, defaulting to True: {e}")
                    enable = True
                rss_config: RssConfig = RssConfig.load_from_dict(rss)
                rss_dict[rss_config.name] = rss_config
                rss_notify[rss_config.name] = notify
                rss_enable[rss_config.name] = enable
        else:
            raise Exception("Cann't find RSS config")
        notify_dict: dict = {}
        if "notify" in dict_data:
            for notify in dict_data["notify"]:
                notify_type: str = notify.pop("type").lower()
                if notify_type == "matrix":
                    notify_dict[notify["name"]] = MatrixConfig.load_from_dict(notify)
        try:
            timezone = ZoneInfo(dict_data.get("timezone", None))
        except Exception as e:
            print(f"⚠️ Invalid timezone in config, defaulting to None: {e}")
            timezone: tzinfo = None
        return cls(log_cfg=log_cfg, ai=ai_config, rss=rss_dict, rss_notify=rss_notify, rss_enable=rss_enable, notifies=notify_dict, timezone=timezone)

    def get_notfies_by_names(self, names: list[str] | str) -> list[NotifyConfig]:
        """
        Get the notifies by their names (supports single string or list of strings).
        Filters out any names not found in self.notifies.
        """
        if isinstance(names, str):
            names = [names]
        return [self.notifies[name] for name in names if name in self.notifies]
