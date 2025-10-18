#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, unique
import openai
from .Utils import _Config


@unique
class AiType(Enum):
    """
    Enum for AI types.
    """
    OPENAI = "openai"
    XAI = "xai"
    CUSTOM = "custom"


@dataclass
class AiConfig(_Config):
    ai_type: AiType = AiType.OPENAI
    api_url: str = None
    api_key: str = None
    name: str = None
    description: str = None
    model: str = "gpt-3.5-turbo"
    temperature: float = 0.7
    max_tokens: int = 1000
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0

    def __post_init__(self):
        if isinstance(self.ai_type, str):
            self.ai_type = AiType[self.ai_type.upper()]
        if not self.name:
            self.name = self.ai_type.name
        if self.ai_type == AiType.OPENAI:
            if not self.api_key:
                raise ValueError("API key cannot be empty")
            if not self.api_url:
                self.api_url = "https://api.openai.com/v1/chat/completions"
        elif self.ai_type == AiType.XAI:
            if not self.api_key:
                raise ValueError("API key cannot be empty")
            if not self.api_url:
                self.api_url = "https://api.x.ai/v1"

    @classmethod
    def load_from_dict(cls, dict_data: dict) -> AiConfig:
        return cls(**dict_data)


class AiAgent():
    def __init__(self, ai_config: AiConfig):
        self._config = ai_config
        self.__client: openai.OpenAI = None
        self.__init: bool = False
        self.init()

    def __eq__(self, other: AiAgent) -> bool:
        if not isinstance(other, AiAgent):
            return False
        return self._config == other._config

    @property
    def client(self) -> openai.OpenAI:
        return self.__client

    def init(self) -> None:
        if self.__init:
            return
        try:
            if self._config.ai_type == AiType.OPENAI:
                self.__client = openai.OpenAI(api_key=self._config.api_key)
            elif self._config.ai_type == AiType.XAI:
                self.__client = openai.OpenAI(api_key=self._config.api_key, base_url=self._config.api_url)
            self.__init = True
        except:
            raise Exception("init ai agent failed")

    def assert_init(self) -> None:
        if not self.__init:
            raise Exception("Agent didn't initlize")

    def act(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self._config.model,
            messages=[
                {"role": "system", "content": "You are an assistant summarizing social media posts."},
                {"role": "user", "content": prompt}
            ],
            temperature=self._config.temperature
        )
        return response.choices[0].message.content.strip()
