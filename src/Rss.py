#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
from dataclasses import dataclass, field
import requests
import feedparser
from .Ai import AiAgent
from .Utils import _Config, Msg, LogLevel
from datetime import datetime, timezone
import calendar
import re


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
    type: str = "rss"
    others: dict = field(default_factory=dict)
    prompts: str = None
    filter_regex: str = None

    def __post_init__(self):
        if not self.name:
            raise ValueError("Name cannot be empty")
        if not self.url:
            raise ValueError("URL cannot be empty")
        if not self.url.startswith("http"):
            self.url = "https://" + self.url


class Rss:
    def __init__(self, config: RssConfig, ai_agent: AiAgent, translate_to: str = "Chinese", timeout: int = 60, run_init: bool = True):
        self.config = config
        self._rss_items: list[RssItem] = []
        self._ai_agent: AiAgent = ai_agent
        self.translate_to: str = translate_to
        self.timeout: int = timeout
        self._post_init_(run_init=run_init)

    def _post_init_(self, run_init: bool = True) -> None:
        self._ai_agent.init()
        if not run_init:
            return
        try:
            self.fetch()
        except:
            pass

    @property
    def rss_url(self) -> str:
        return self.config.url

    @property
    def items(self) -> list[RssItem]:
        return self._rss_items.copy()

    def get_items_since(self, since: datetime, fetch: bool = False, newest_at_first: bool = True) -> list[RssItem]:
        """
        Return all RssItems published after the given datetime.
        Handles both timezone-aware and naive datetimes by converting naive `since` to UTC.
        Ignores items without a valid pub_date.

        :param since: datetime object to filter items published after this time.
        :param fetch: if True, fetch the RSS feed before filtering.
        :param newest_at_first: if True, return items in descending order of pub_date.

        :return: list of RssItem objects published after the given datetime.
        """
        # Ensure `since` is timezone-aware (assume UTC if not)
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
        # If fetch is True, fetch the the rss feed
        if fetch:
            self.fetch()
        # Filter items with pub_date > since
        data = [item for item in self.items if item.pub_date and item.pub_date > since]
        # sort by pub_date in descending order
        data.sort(key=lambda x: x.pub_date, reverse=newest_at_first)
        return data

    @classmethod
    def fetch_from_url(cls, rss_url: str, timeout_seconds: int = 60) -> list[RssItem]:
        """
        Fetches the RSS feed from the URL and returns a list of RssItem objects.
        """
        try:
            response = requests.get(rss_url, timeout=timeout_seconds)
            response.raise_for_status()
            feed = feedparser.parse(response.content)
            if feed.bozo:
                raise RssFetchErr(rss_url, feed.bozo_exception)
        except Exception as e:
            raise e

        _rss_items = []

        for entry in feed.entries:
            # 1. title 清洗（去换行、压缩空格、限制长度）
            raw_title = entry.get("title", "")
            title = " ".join(raw_title.split())[:500]

            # 2. content fallback
            content = None
            if isinstance(entry.get("content"), list) and entry["content"]:
                content = entry["content"][0].get("value")
            elif "summary" in entry:
                content = entry["summary"]

            # 3. description 清洗 + 提取图片
            raw_description = entry.get("description") or entry.get("summary", "")
            # description_text, image_links = clean_html(raw_description)

            # 4. 时间字段处理
            pub_struct = entry.get("published_parsed")
            pub_date = datetime.fromtimestamp(calendar.timegm(pub_struct), tz=timezone.utc) if pub_struct else None

            # 5. authors 处理
            authors = [a.get("name", "") for a in entry.get("authors", [])] if "authors" in entry else []

            # 6. 构建对象
            item = RssItem(title=title, link=entry.get("link", ""), description=raw_description, published=entry.get("published"), pub_date=pub_date, id=entry.get("id"), authors=authors, content=content)
            _rss_items.append(item)
        return _rss_items

    def fetch(self) -> list[RssItem]:
        """
        Fetches the RSS feed from the URL and returns a list of RssItem objects.
        """
        items = self.fetch_from_url(self.rss_url, timeout_seconds=self.timeout)
        self._rss_items = items
        return items

    def prompt(self, item: RssItem, translate_to: str = "Chinese", custom_prompt: str = None) -> str:
        """
        build prompt for AI agent to summarize the rss item
        :param item: RssItem object
        :param translate_to: language to translate to
        :param custom_prompt: custom prompt for AI agent
        :return: prompt string
        """
        translate_to = translate_to.strip().lower()

        prompt = custom_prompt or ""
        if isinstance(prompt, list) and len(prompt) > 0 and isinstance(prompt[0], str):
            prompt = "\n".join(prompt)
        if not custom_prompt:
            prompt = (
                "You will be given a social media or news post.\n"
                "Determine if it is an original post(who), a retweet(who), or a quoted tweet(who).\n"
                "If it's a quote/retweet, summarize both the original and the comment separately.\n"
                "Also, please research the background of this post\n"
                "Extract the most relevant information.\n"
            )

        if translate_to != "original":
            prompt += f"Then translate the summary into {translate_to.capitalize()}.\n"

        prompt += self.rss_item_flatten(item=item)
        return prompt

    @classmethod
    def rss_item_flatten(cls, item: RssItem) -> str:
        """
        Flatten the RssItem object into a string.
        :param item: RssItem object
        :return: flattened string
        """
        content = item.content or item.description
        _str = f"\n---\nTitle: {item.title}\nContent: {content}\nLink: {item.link}\n---"
        return _str

    def format_output(self, contents: str) -> str:
        """
        Format the output from the AI agent.
        """
        return contents

    def summarize(self, items: list[RssItem] = None, verbose: bool = False) -> list[Msg]:
        """
        Summarize the RSS items using the AI agent.
        :param items: list of RssItem objects
        :return: list of Msg objects
        """
        if items is None:
            items = self.items[-10:]
        if isinstance(items, RssItem):
            items = [items]
        msgs: list[Msg] = []
        matched_items, unmatched_items = self.filter_items(items=items)
        if verbose:
            print(LogLevel.DEBUG.warp(message=f"Filter by {self.config.filter_regex}. Matched items: {len(matched_items)}, Unmatched items: {len(unmatched_items)}"))
        for item in unmatched_items:
            prompt_str = self.prompt(item=item, translate_to=self.translate_to, custom_prompt=self.config.prompts)
            if verbose:
                print(LogLevel.DEBUG.warp(message=f"Summarizing item: {item.title}"))
            reply = self._ai_agent.act(prompt=prompt_str)
            format_reply = self.format_output(reply)
            msg = Msg(
                title=item.title,
                authors=item.authors,
                pub_date=item.pub_date,
                description=item.description,
                contents=format_reply,
                link=item.link,
                _is_markdown=self._ai_agent._is_markdown
            )
            msgs.append(msg)
        contents = f"Item matches filter regex: {self.config.filter_regex}"
        for item in matched_items:
            msg = Msg(
                title=item.title,
                authors=item.authors,
                pub_date=item.pub_date,
                description=item.description,
                contents=contents,
                link=item.link,
            )
            msgs.append(msg)
        return msgs

    def filter_items(self, items: list[RssItem] | RssItem) -> tuple[list[RssItem], list[RssItem]]:
        """
        Filter items.
        Parameters:
            - items: A list of RssItem objects or a single RssItem object.

        Returns:
            - matched_items: List of items that match the filter regex.
            - unmatched_items: List of items that do not match the filter regex.
        """
        if isinstance(items, RssItem):
            items = [items]
        if self.config.filter_regex is None:
            return [], items
        pattern = re.compile(self.config.filter_regex, re.IGNORECASE)
        matched_items = []
        unmatched_items = []
        for item in items:
            if pattern.search(item.title) or pattern.search(item.description):
                matched_items.append(item)
            else:
                unmatched_items.append(item)
        return matched_items, unmatched_items


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
