#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
from dataclasses import dataclass, field
import feedparser
from .Ai import AiAgent
from .Utils import _Config, Msg
from datetime import datetime, timezone
import calendar


class RssFetchErr(Exception):
    def __init__(self, url: str, original_exception: Exception = None):
        self.url = url
        self.original_exception = original_exception
        message = f"Failed to fetch RSS feed from {url}"
        if original_exception:
            message += f" | Reason: {repr(original_exception)}"
        super().__init__(message)


@dataclass
class RssItem:
    title: str
    link: str = ""
    description: str = ""
    id: str = None
    published: str = None
    pub_date: datetime = None
    content: str = None
    authors: list[str] = field(default_factory=list)

    def __repr__(self):
        _dict = self.__dict__
        _str = ""
        for key, value in _dict.items():
            if value is None:
                continue
            _str_temp = f"{key}: {value}\n"
            _str += _str_temp
        return _str


@dataclass
class RssConfig(_Config):
    name: str
    url: str
    description: str = None

    def __post_init__(self):
        if not self.name:
            raise ValueError("Name cannot be empty")
        if not self.url:
            raise ValueError("URL cannot be empty")
        if not self.url.startswith("http"):
            self.url = "https://" + self.url


class Rss():

    def __init__(self, config: RssConfig, ai_agent: AiAgent, translate_to: str = "Chinese"):
        self.config = config
        self._rss_items: list[RssItem] = []
        self._ai_agent: AiAgent = ai_agent
        self.translate_to: str = translate_to
        self._post_init_()

    def _post_init_(self) -> None:
        self._ai_agent.init()
        try:
            self.fetch()
        except:
            pass

    @property
    def items(self) -> list[RssItem]:
        return self._rss_items.copy()

    def get_items_since(self, since: datetime) -> list[RssItem]:
        """
        Return all RssItems published after the given datetime.

        Handles both timezone-aware and naive datetimes by converting naive `since` to UTC.
        Ignores items without a valid pub_date.
        """
        # Ensure `since` is timezone-aware (assume UTC if not)
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)

        # Filter items with pub_date > since
        return [item for item in self.items if item.pub_date and item.pub_date > since]

    def fetch(self) -> list[RssItem]:
        """
        Fetches the RSS feed from the URL and returns a list of RssItem objects.
        """

        feed = feedparser.parse(self.config.url)
        if feed.bozo:
            raise RssFetchErr(self.config.url, feed.bozo_exception)

        self._rss_items = []

        for entry in feed.entries:
            # 1. title 清洗（去换行、压缩空格、限制长度）
            raw_title = entry.get('title', '')
            title = ' '.join(raw_title.split())[:500]

            # 2. content fallback
            content = None
            if isinstance(entry.get('content'), list) and entry['content']:
                content = entry['content'][0].get('value')
            elif 'summary' in entry:
                content = entry['summary']

            # 3. description 清洗 + 提取图片
            raw_description = entry.get('description') or entry.get('summary', '')
            # description_text, image_links = clean_html(raw_description)

            # 4. 时间字段处理
            pub_struct = entry.get('published_parsed')
            pub_date = datetime.fromtimestamp(calendar.timegm(pub_struct), tz=timezone.utc) if pub_struct else None

            # 5. authors 处理
            authors = [a.get('name', '') for a in entry.get('authors', [])] if 'authors' in entry else []

            # 6. 构建对象
            item = RssItem(
                title=title,
                link=entry.get('link', ''),
                description=raw_description,
                published=entry.get('published'),
                pub_date=pub_date,
                id=entry.get('id'),
                authors=authors,
                content=content
            )
            self._rss_items.append(item)
        return self._rss_items

    def prompt(self, item: RssItem, translate_to: str = 'Chinese') -> str:
        """

        """
        content = item.content or item.description
        translate_to = translate_to.strip().lower()

        prompt = (
            "You will be given a social media or news post.\n"
            "Determine if it is an original post(who), a retweet(who), or a quoted tweet(who).\n"
            "If it's a quote/retweet, summarize both the original and the comment separately.\n"
            "Also, please research the background of this post\n"
            "Extract the most relevant information.\n"
        )

        if translate_to != "original":
            prompt += f"Then translate the summary into {translate_to.capitalize()}.\n"

        prompt += (
            "\n---\n"
            f"Title: {item.title}\n"
            f"Content: {content}\n"
            f"Link: {item.link}\n"
            "---"
        )
        return prompt

    def format_output(self, contents: str) -> str:
        """

        """
        return contents

    def summarize(self, items: list[RssItem] = None) -> list[Msg]:
        """

        """
        if items is None:
            items = self.items[-10:]
        if isinstance(items, RssItem):
            items = [items]
        msgs: list[Msg] = []
        for item in items:
            prompt_str = self.prompt(item=item, translate_to=self.translate_to)
            reply = self._ai_agent.act(prompt=prompt_str)
            format_reply = self.format_output(reply)
            msg = Msg(title=item.title,
                      authors=item.authors,
                      pub_date=item.pub_date,
                      description=item.description,
                      contents=format_reply,
                      link=item.link,
                      )
            msgs.append(msg)

        return msgs


def get_newest_time(items: RssItem | list[RssItem]) -> datetime:
    """
    Return the newest (latest) pub_date from a list of RssItem objects.
    If no valid datetime is found, return current time.
    """
    if isinstance(items, RssItem):
        items = [items]
    valid_dates = [item.pub_date for item in items if isinstance(item.pub_date, datetime)]

    if valid_dates:
        return max(valid_dates)
    else:
        return datetime.now()
