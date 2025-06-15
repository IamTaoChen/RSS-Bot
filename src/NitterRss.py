#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
from dataclasses import dataclass
from .Utils import LogLevel
from .Rss import Rss, RssItem, RssConfig
from .Ai import AiAgent
import re
import requests
from bs4 import BeautifulSoup


def extract_html_p(html: str) -> str:
    """
    Extracts the content of the first <p> tag from the given HTML string.
    :param html: HTML string
    :return: Content of the first <p> tag or the original HTML if no <p> tag is found
    """
    match = re.search(r"<p>(.*?)</p>", html, re.DOTALL)
    return match.group(1) if match else html


def extract_nitter_post(url: str) -> str | None:
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # 主推文内容在 `.main-tweet .tweet-content` 中
        tweet_div = soup.select_one(".main-tweet .tweet-content")
        if tweet_div:
            content = tweet_div.get_text(strip=True)
            return content
        else:
            return None

    except Exception as e:
        return None


@dataclass
class Retweet:
    title: str
    id: str = ""
    author: str = None
    description: str = ""

    @classmethod
    def is_retweet(cls, item: RssItem, nitter_public_url: str = "https://x.com", nitter_url: str = None) -> tuple[bool, "Retweet"]:
        """
        Extract tweet info from RSS item.
        :param item: RSS feed item
        :param nitter_public_url: Base Twitter/Nitter URL (e.g., https://x.com or https://nitter.net)
        :param nitter_url: Nitter RSS URL, if it's None, it will use the nitter_public_url
        :return: Tuple of (is_retweet, Retweet object or None)
        """
        if nitter_url is None:
            nitter_url = nitter_public_url
        pattern = re.compile(r"<p>(.*?)</p>", re.DOTALL)
        matches = pattern.findall(item.description)
        if not matches:
            return False, None

        description_parts = []
        author = None
        tweet_link = None

        # Escape the base URL for safe regex usage
        safe_url_pattern = re.escape(nitter_public_url.rstrip("/"))

        for match in matches:
            href_match = re.search(rf'href="({safe_url_pattern}/([^/]+)/status/(\d+)[^"]*)"', match)
            if href_match:
                tweet_link = href_match.group(1)
                author = href_match.group(2)
            else:
                clean_text = re.sub(r"<.*?>", "", match).strip()
                if clean_text:
                    description_parts.append(clean_text)
        retweet = cls(title=item.title.strip(), id=tweet_link or item.link, author=author, description=description_parts)
        try:
            url = retweet.id.replace(nitter_public_url, nitter_url)
            contents = extract_nitter_post(url)
            if contents:
                retweet.description = contents
                return True, retweet
            return False, None
        except:
            return False, None


class RssNitter(Rss):
    """
    This class Inherits from the Rss class.
    """

    def __init__(self, config: RssConfig, ai_agent: AiAgent, translate_to: str = "Chinese", timeout: int = 60):
        self.url = config.url
        self.__url = self.url
        self.author = config.others.get("author", None)
        self.public_url = config.others.get("public_url", "https://x.com")
        self.__public_url = self.public_url
        super().__init__(config=config, ai_agent=ai_agent, translate_to=translate_to, timeout=timeout)

    @property
    def rss_url(self) -> str:
        """
        Get the RSS URL.
        :return: The RSS URL.
        """
        return f"{self.url}/{self.author}/rss"

    # def fetch(self) -> list[RssItem]:
    #     items = super().fetch()
    #     for item in items[:2]:
    #         print("--" * 20)
    #         is_retweet, retweet = Retweet.is_retweet(item=item, nitter_public_url=self.public_url, nitter_url=self.url)
    #         if is_retweet:
    #             print(f"Retweet found: {retweet}")
    #     return items

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
                f"You will be given a twitter from {item.authors}\n"
                "Determine if it is an original post(who), a retweet(who), or a quoted tweet(who).\n"
                "If it's a quote/retweet, summarize both the original and the comment separately.\n"
                "Also, please research the background of this post\n"
                "Extract the most relevant information.\n"
            )

        if translate_to != "original":
            prompt += f"Then translate the summary into {translate_to.capitalize()}.\n"

        prompt += self.item_flatten(item=item)
        return prompt

    def item_flatten(self, item: RssItem) -> str:
        """
        Flatten the RssItem object into a string.
        :param item: RssItem object
        :return: flattened string
        """
        is_retweet, retweet = Retweet.is_retweet(item=item, nitter_public_url=self.__public_url, nitter_url=self.__url)
        _str = self.rss_item_flatten(item=item)
        if is_retweet:
            # print(f"Retweet found: {retweet}")
            _str += f"\n---\nRetweet from: \nTitle: {retweet.title}\ndescription: {retweet.description}\nLink: {retweet.id}\n---"
        # else:
        #     print("No retweet found")
        return _str

    def fetch(self) -> list[RssItem]:
        candilates = {"self": self.rss_url, "nitter": "https://nitter.net"}
        err: Exception = None
        success: bool = False
        for key, url in candilates.items():
            try:
                if key == "self":
                    self.__public_url = self.public_url
                    self.__url = self.url
                else:
                    print(LogLevel.WARNING.warp(f"Try to fetch RSS from {url}", now=None))
                    self.__public_url = url
                    self.__url = url
                rss_url = f"{self.__url}/{self.author}/rss"
                items = self.fetch_from_url(rss_url=rss_url, timeout_seconds=self.timeout)
                self._rss_items = items
                success = True
                return items
            except Exception as e:
                print(LogLevel.ERROR.warp(f"Fetch RSS for {url} failed", now=None))
                if key == "self":
                    err = e

        if not success:
            raise err
