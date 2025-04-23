#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
from dataclasses import dataclass, field
from .Utils import _Config, Msg
from abc import ABC, abstractmethod
import requests
import time


@dataclass
class NotifyConfig(_Config, ABC):
    username: str
    token: str

    @abstractmethod
    def send(self, msgs: Msg) -> bool:
        """
        Send msg
        """
        pass

    def msg2str(self, msg: Msg, html: bool = False) -> str:
        """
        Format
        """
        return str(msg)


@dataclass
class MatrixConfig(NotifyConfig):
    homeserver: str
    room_id: str

    def send(self, msgs: Msg | list[Msg], use_html: bool = True) -> bool:
        if isinstance(msgs, Msg):
            msgs = [msgs]
        elif not isinstance(msgs, list):
            raise Exception("The msgs should be Msg or list[Msg]")

        session = requests.Session()

        for msg in msgs:
            body = self.msg2str(msg, html=False)
            payload = {
                "msgtype": "m.text",
                "body": body
            }

            if use_html:
                payload["format"] = "org.matrix.custom.html"
                payload["formatted_body"] = self.msg2str(msg, html=True)

            txn_id = str(int(time.time() * 1000))
            url = f"{self.homeserver}/_matrix/client/r0/rooms/{self.room_id}/send/m.room.message/{txn_id}"
            headers = {"Authorization": f"Bearer {self.token}"}
            session.put(url, headers=headers, json=payload)

    def msg2str(self, msg: Msg, html: bool = False) -> str:
        lines = []

        def fmt(k: str, v: str) -> str:
            if html:
                return f"<b>{k}:</b> {v}<br>"
            return f"{k}: {v}"

        title = ' '.join(msg.title.strip().split())
        lines.append(f"<h4>{title}</h4>" if html else f"Title: {title}")

        if msg.description:
            lines.append(fmt("Description", msg.description.strip()))

        if msg.link:
            link = f'<a href="{msg.link}">{msg.link}</a>' if html else msg.link
            lines.append(fmt("Link", link))

        if msg.pub_date:
            date_str = msg.pub_date.strftime('%Y-%m-%d %H:%M:%S %Z')
            lines.append(fmt("PubDate", date_str))

        if msg.images:
            if html:
                for img in msg.images:
                    lines.append(f'<img src="{img}" style="max-width:100%;"><br>')
            else:
                lines.append(fmt("Images", ', '.join(msg.images)))

        if msg.authors:
            lines.append(fmt("Authors", ', '.join(msg.authors)))

        if msg.contents:
            lines.append("<hr><b>CONTENTS</b><br>" if html else "===== CONTENTS =====")

            if isinstance(msg.contents, dict):
                for k, v in msg.contents.items():
                    if html:
                        lines.append(f"<b>{k}</b><br><pre>{v.strip()}</pre><br>")
                    else:
                        lines.append(f"{k}:\n{v.strip()}\n")

            elif isinstance(msg.contents, str):
                content_text = msg.contents.strip()
                if html:
                    for line in content_text.splitlines():
                        lines.append(line.strip() + "<br>")
                else:
                    lines.append(content_text)

        return ''.join(lines) if html else '\n'.join(lines)
