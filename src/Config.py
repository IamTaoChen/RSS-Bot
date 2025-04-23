#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
from dataclasses import dataclass, field
from .Ai import AiConfig
from .Rss import RssConfig
from .Utils import _Config
from .Notify import NotifyConfig, MatrixConfig


@dataclass
class Config(_Config):
    ai: AiConfig
    rss: dict[str, RssConfig] = field(default_factory=dict)
    rss_notify: dict[str, list[str]] = field(default_factory=dict)
    rss_enable: dict[str, list[bool]] = field(default_factory=dict)
    notify: dict[str, NotifyConfig] = field(default=dict)

    @classmethod
    def load_from_dict(cls, dict_data: dict) -> "Config":
        if 'ai' in dict_data:
            ai_config = AiConfig.load_from_dict(dict_data['ai'])
        else:
            raise Exception("")
        rss_dict: dict = {}
        rss_notify: dict = {}
        rss_enable: dict = {}
        if 'rss' in dict_data:
            for rss in dict_data['rss']:
                notify = rss.pop('notify')
                enable = rss.pop('enable')
                rss_config: RssConfig = RssConfig.load_from_dict(rss)
                rss_dict[rss_config.name] = rss_config
                rss_notify[rss_config.name] = notify
                rss_enable[rss_config.name] = enable
        else:
            raise Exception("")
        notify_dict: dict = {}
        if 'notify' in dict_data:
            for notify in dict_data['notify']:
                notify_type: str = notify.pop('type').lower()
                notify_name: str = notify.pop('name')
                if notify_type == 'matrix':
                    notify_dict[notify_name] = MatrixConfig.load_from_dict(notify)

        return cls(
            ai=ai_config,
            rss=rss_dict,
            rss_notify=rss_notify,
            rss_enable=rss_enable,
            notify=notify_dict
        )

    def get_notfies_by_names(self, names: list[str] | str) -> list[NotifyConfig]:
        """
        Get the notifies by their names
        """
        if isinstance(names, str):
            names = [names]
        return [self.notify[notify_name] for notify_name in self.notify.keys() if notify_name in names]
