#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
from dataclasses import dataclass, field
from .Ai import AiConfig
from .Rss import RssConfig
from .Utils import _Config, LogLevel
from .Notify import NotifyConfig, MatrixConfig
from datetime import tzinfo
from zoneinfo import ZoneInfo
from pathlib import Path


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
    rss_enable: dict[str, bool] = field(default_factory=dict)
    rss_from_now: dict[str, bool] = field(default_factory=dict)
    notifies: dict[str, NotifyConfig] = field(default_factory=dict)
    timezone: tzinfo = field(default=None)
    other_tz: dict[str, tzinfo] = field(default_factory=dict)
    translate_to: str | None = None  # If not None, it will add prompts to translate the AI response to this language

    @classmethod
    def load_from_dict(cls, dict_data: dict) -> "Config":
        log_cfg: LogCfg = LogCfg.load_from_dict(dict_data.get("log", None))
        other_tz: dict[str, tzinfo] = cls.tz_dict(dict_data.get("other_tz", None))
        if "ai" in dict_data:
            ai_config = AiConfig.load_from_dict(dict_data["ai"])
        else:
            raise Exception("Cann't find AI config")
        rss_dict: dict = {}
        rss_notify: dict = {}
        rss_enable: dict = {}
        rss_from_now: dict = {}
        if "rss" in dict_data:
            for rss in dict_data["rss"]:
                notify = rss.pop("notify")
                notify = list(set(notify))
                try:
                    enable = rss.pop("enable")
                except Exception as e:
                    print(f"⚠️  RSS config missing 'enable' field, defaulting to True: {e}")
                    enable = True
                try:
                    from_now = rss.pop("from_now")
                except Exception as e:
                    print("⚠️  RSS config missing 'from_now' field, defaulting to True")
                    from_now = False
                rss_config: RssConfig = RssConfig.load_from_dict(rss)
                rss_dict[rss_config.name] = rss_config
                rss_notify[rss_config.name] = notify
                rss_enable[rss_config.name] = enable
                rss_from_now[rss_config.name] = from_now
        else:
            raise Exception("Cann't find RSS config")
        notify_dict: dict = {}
        if "notify" in dict_data:
            for notify in dict_data["notify"]:
                notify_type: str = notify.pop("type").lower()
                if notify_type == "matrix":
                    notify_ins: MatrixConfig = MatrixConfig.load_from_dict(notify)
                    notify_tz = cls.tz_dict(notify.get("tz", None))
                    notify_ins.tz = {**other_tz, **notify_tz}
                    notify_dict[notify["name"]] = notify_ins
        try:
            timezone = cls.format_tz(dict_data.get("timezone", None))
        except TypeError as e:
            print(f"⚠️ : {e}")
            timezone: tzinfo = None
        translate_to = dict_data.get("translate_to", None)
        return cls(log_cfg=log_cfg, ai=ai_config, rss=rss_dict, rss_notify=rss_notify, rss_enable=rss_enable, rss_from_now=rss_from_now, notifies=notify_dict, timezone=timezone, other_tz=other_tz, translate_to=translate_to)

    def get_notfies_by_names(self, names: list[str] | str) -> list[NotifyConfig]:
        """
        Get the notifies by their names (supports single string or list of strings).
        Filters out any names not found in self.notifies.
        """
        if isinstance(names, str):
            names = [names]
        return [self.notifies[name] for name in names if name in self.notifies]

    @classmethod
    def format_tz(cls, tz: tzinfo | str | None) -> tzinfo:
        """
        Format the timezone input to a tzinfo object.
        If the input is a string, it will be converted to ZoneInfo.
        If None, it will return None.
        """
        if isinstance(tz, str):
            try:
                return ZoneInfo(tz)
            except Exception as e:
                print(f"⚠️ Invalid timezone string '{tz}': {e}")
                return None
        elif isinstance(tz, ZoneInfo):
            return tz
        elif tz is None:
            return None
        else:
            raise TypeError("Timezone must be a str or ZoneInfo instance.")

    @classmethod
    def tz_dict(cls, tz: dict[str, str | tzinfo] | None) -> dict[str, tzinfo]:
        """
        Convert a dictionary of timezones to a dictionary of tzinfo objects.
        If the input is None, it will return an empty dictionary.
        """
        if not tz:
            return {}
        return {key: cls.format_tz(value) for key, value in tz.items() if value is not None}
