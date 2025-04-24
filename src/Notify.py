#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
from dataclasses import dataclass
from datetime import tzinfo, datetime
from .Utils import _Config, Msg
from abc import ABC, abstractmethod
import requests
import time

SESSION = requests.Session()


@dataclass
class NotifyConfig(_Config, ABC):
    username: str
    token: str

    def send(self, msgs: Msg | list[Msg], use_html: bool = True, local_tz: tzinfo = None) -> list[Msg]:
        """
        Send messages. Return the list of messages that failed to send.
        """
        if isinstance(msgs, Msg):
            msgs = [msgs]
        elif not isinstance(msgs, list):
            raise TypeError("The msgs should be Msg or list[Msg]")

        failed_msgs = []
        for msg in msgs:
            try:
                if not self.send_core(msg=msg, use_html=use_html, local_tz=local_tz):
                    failed_msgs.append(msg)
            except Exception as e:
                print(f"❌ Exception while sending message '{msg.title}': {e}")
                failed_msgs.append(msg)

        return failed_msgs

    @abstractmethod
    def send_core(self, msg: Msg, use_html: bool = True, local_tz: tzinfo = None) -> bool:
        pass

    def msg2str(self, msg: Msg, html: bool = False, local_tz: tzinfo = None) -> str:
        return str(msg)

    @classmethod
    def format_dt(cls, dt: datetime, tz: tzinfo = None) -> str:
        dt = dt.astimezone(tz) if tz else dt
        return dt.strftime('%Y-%m-%d %H:%M:%S %Z')


@dataclass
class MatrixConfig(NotifyConfig):
    homeserver: str
    room_id: str

    def send_core(self, msg: Msg, use_html: bool = True, local_tz: tzinfo = None) -> bool:
        if use_html is None:
            use_html = True
        body = self.msg2str(msg, html=use_html, local_tz=local_tz)
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
        res = SESSION.put(url, headers=headers, json=payload)

        return res.status_code == 200

    def msg2str(self, msg: Msg, html: bool = False, local_tz: tzinfo = None) -> str:
        lines = []

        def fmt(k: str, v: str) -> str:
            return f"<b>{k}:</b> {v}<br><br>" if html else f"{k}: {v}\n"

        # Title
        title = ' '.join(msg.title.strip().split())
        if html:
            lines.append(f"<h1 style='text-align:center;'>{title}</h1><br><br>")
        else:
            lines.append(f"Title: {title}\n")

        # Description
        if msg.description:
            lines.append(fmt("Description", msg.description.strip()))

        # Link
        if msg.link:
            link = f'<a href="{msg.link}">{msg.link}</a>' if html else msg.link
            lines.append(fmt("Link", link))

        # PubDate
        if msg.pub_date:
            lines.append(fmt("PubDate", self.format_dt(msg.pub_date)))
            if local_tz:
                lines.append(fmt("LocalTime", self.format_dt(msg.pub_date, local_tz)))

        # Authors
        if msg.authors:
            lines.append(fmt("Authors", ', '.join(msg.authors)))

        # Images
        if msg.images:
            if html:
                for img in msg.images:
                    lines.append(f'<img src="{img}" style="max-width:100%; margin-top:8px;"><br>')
            else:
                lines.append(fmt("Images", ', '.join(msg.images)))

        # Contents
        if msg.contents:
            lines.append("<h3>📦 Contents</h3><br>" if html else "===== CONTENTS =====\n")
            if isinstance(msg.contents, dict):
                for k, v in msg.contents.items():
                    if html:
                        lines.append(f"<b>{k}</b><br><pre>{v.strip()}</pre><br><br>")
                    else:
                        lines.append(f"{k}:\n{v.strip()}\n\n")
            elif isinstance(msg.contents, str):
                content_text = msg.contents.strip()
                if html:
                    for line in content_text.splitlines():
                        lines.append(line.strip() + "<br>")
                    lines.append("<br>")
                else:
                    lines.append(content_text + "\n")

        lines.append(
            "<div style='color:#888; font-size:small;'>— End —</div><br><br>"
            if html else "=" * 40 + "\n"
        )

        return ''.join(lines) if html else '\n'.join(lines)
