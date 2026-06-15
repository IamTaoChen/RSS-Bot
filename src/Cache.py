from __future__ import annotations
from dataclasses import dataclass, field
import json
from .Utils import Msg, to_list


@dataclass
class SendCache:
    """
    Cache for messages that failed to send. It will retry to send these messages in the next run.
    """
    caches: dict[str, set[Msg]] = field(default_factory=dict)
    file_path: str = "send_cache.json"

    def __post_init__(self):
        if self.caches is None:
            self.caches = {}
        self.load_from_file()

    @property
    def empty(self) -> bool:
        return self.total == 0

    @property
    def stats(self) -> dict[str, int]:
        return {notify: len(msgs) for notify, msgs in self.caches.items()}

    @property
    def total(self) -> int:
        return sum(i for i in self.stats.values())

    def pure(self) -> None:
        for notify in self.caches:
            if len(self.caches[notify]) == 0:
                del self.caches[notify]

    def add_msg(self, notify: str, msg: Msg) -> None:
        if notify not in self.caches:
            self.caches[notify] = set()
        self.caches[notify].add(msg)

    def append_msgs(self, notifies: str | list[str], msgs: Msg | list[Msg]) -> None:
        msgs = to_list(msgs)
        notifies = to_list(notifies)
        for notify in notifies:
            if notify not in self.caches:
                self.caches[notify] = set()
            self.caches[notify].update(msgs)

    def save_to_file(self, file_path: str = None) -> None:
        file_path = self._filename(file_path)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump({notify: [msg.dump() for msg in msgs] for notify, msgs in self.caches.items()}, f, ensure_ascii=False, indent=4)

    def load_from_file(self, file_path: str = None) -> None:
        file_path = self._filename(file_path)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.caches = {notify: set(Msg.new(**msg) for msg in msgs) for notify, msgs in data.items()}
        except FileNotFoundError:
            self.caches = {}

    def clear(self, notify: str | list[str] = None, save: bool = False) -> None:
        if notify:
            notifies = to_list(notify)
            for n in notifies:
                if n in self.caches:
                    del self.caches[n]
        else:
            self.caches = {}
        if save:
            self.save_to_file()

    def replace_msgs(self, notify: str, msgs: Msg | list[Msg], save: bool = False) -> None:
        msgs = to_list(msgs)
        self.caches[notify] = set(msgs)
        if save:
            self.save_to_file()

    def _filename(self, file_path: str) -> str:
        return file_path if file_path else self.file_path
