#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
from dataclasses import dataclass, field
from .Ai import AiConfig
from .Rss import RssConfig
from .Utils import _Config
from .Notify import NotifyConfig, MatrixConfig
from datetime import tzinfo
from zoneinfo import ZoneInfo
from enum import Enum
from pathlib import Path


class LogLevel(Enum):
    SUCCESS = 5
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40

    def __str__(self):
        return self.name


@dataclass
class LogCfg:
    level: LogLevel = LogLevel.INFO
    file: Path = None
    to_console: bool = True


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
        if "log" in dict_data:
            log_cfg = LogCfg(**dict_data["log"])
            if isinstance(log_cfg.level, str):
                log_cfg.level = LogLevel[log_cfg.level]
            log_cfg.file = Path(log_cfg.file) if log_cfg.file else None
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
                except:
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
        except:
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
