
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import yaml
from datetime import datetime
import re
from html import unescape


def clean_html(html: str) -> tuple[str, list[str]]:
    """
    清洗 HTML 标签，返回纯文本和图片链接列表
    """
    img_links = re.findall(r'<img[^>]+src="([^">]+)"', html)
    text = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = unescape(text).strip()
    return text, img_links


@dataclass
class _Config:

    @classmethod
    def load_from_dict(cls, dict_data: dict) -> _Config:
        return cls(**dict_data)

    @classmethod
    def load_from_yaml(cls, cfg_file: str | Path) -> _Config:
        data = cls.load_yaml(cfg_file=cfg_file)
        return cls.load_from_dict(dict_data=data)

    @classmethod
    def load_yaml(cls, cfg_file: str | Path) -> dict:
        if isinstance(cfg_file, str):
            cfg_file = Path(cfg_file)
        elif not isinstance(cfg_file, Path):
            raise Exception("cfg_file should be a str or Path instanse")

        if not cfg_file.exists():
            raise Exception(f"The cfg_file({cfg_file}) does not exist)")
        with open(cfg_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        return data


@dataclass
class Msg:
    title: str
    description: str
    link: str = None
    pub_date: datetime = None
    images: list[str] = field(default_factory=list)
    authors: list[str] = field(default_factory=list)
    contents: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        des, img_links = clean_html(self.description)
        self.description = des
        self.images = img_links

    def __str__(self) -> str:
        _str = ""
        content_splitter = '\n' + '=' * 5 + ' CONTENTS ' + '=' * 5 + '\n'

        def fmt(k, v):
            return f"{k.ljust(10)}: {v}\n"

        for key, value in self.__dict__.items():
            if key == 'pub_date':
                if self.pub_date:
                    _str += fmt("PubDate", self.pub_date)
            elif key == 'contents':
                if isinstance(value, dict) and value:
                    _str += content_splitter
                    for key2, value2 in value.items():
                        _str += f"{key2}:\n  {value2.strip()}\n"
                elif isinstance(value, str) and value.strip():
                    _str += content_splitter
                    _str += f"{value.strip()}\n"
            else:
                if value:  # Skip empty fields
                    _str += fmt(key.capitalize(), value)

        return _str

    def __repr__(self) -> str:
        return str(self)

    def __init_post__(self):
        if self.datetime is None:
            self.datetime = datetime.now()

    def format(self) -> str:
        return str(self)
