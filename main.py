from src.Config import Config
from src.Rss import Rss, get_newest_time
from src.Ai import AiAgent
from src.Notify import NotifyConfig
from datetime import datetime, timezone
from dataclasses import dataclass, field
from time import sleep
import argparse


@dataclass
class RssMain:
    rss: Rss
    enable: bool = True
    last: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    notifies: list[NotifyConfig] = field(default_factory=list)


class App:
    def __init__(self, cfg_file: str):
        self.verbose = True
        self.log(f"App parsing config file: {cfg_file}")
        self._config: Config = Config.load_from_yaml(cfg_file=cfg_file)
        self.rss: dict[str, RssMain] = {}
        self._init_rss()

    def log(self, msg: str, level: str = 'INFO'):
        if self.verbose:
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")
            print(f"[{now}] [{level}] {msg}")

    def print_split(self, order: int = 0):
        symbol = "="
        size = 50
        if order == 1:
            symbol = "-"
        elif order == 2:
            symbol = "+"
        elif order == 3:
            symbol = "~"
        print(symbol * size)

    def _init_rss(self) -> None:
        ai_agent = AiAgent(ai_config=self._config.ai)
        for rss_name, rss_config in self._config.rss.items():
            rss = Rss(config=rss_config, ai_agent=ai_agent)
            now = datetime.now(timezone.utc)
            notifies = self._config.get_notfies_by_names(self._config.rss_notify[rss_name])
            enable = self._config.rss_enable[rss_name]
            rss_main = RssMain(rss=rss, last=now, notifies=notifies, enable=enable)
            self.rss[rss_name] = rss_main
            self.log(f"Initialized RSS feed: {rss_name}")

    def run(self, interval: int = 60):
        self.print_split(order=0)
        while True:
            self.print_split(order=1)
            for rss_name, rss_combine in self.rss.items():
                self.print_split(order=2)

                if not getattr(rss_combine, "enable", True):
                    self.log(f"❌ {rss_name} is disabled, skipping...")
                    self.print_split(order=2)
                    continue

                self.log(f"📡 Start handling RSS - {rss_name} (since {rss_combine.last})")

                try:
                    all_items = rss_combine.rss.fetch()
                    new_rss_items = rss_combine.rss.get_items_since(rss_combine.last)
                    self.log(f"📎 Found {len(new_rss_items)} new item(s)")
                    self.print_split(order=2)

                    if new_rss_items:
                        self.print_split(order=3)
                        self.log("📤 Start to send messages...")
                        self.rss[rss_name].last = get_newest_time(new_rss_items)
                        msgs = rss_combine.rss.summarize(new_rss_items)
                        for notify in rss_combine.notifies:
                            notify.send(msgs=msgs)
                        self.print_split(order=3)

                except Exception as e:
                    self.log(f"❗ Error while handling {rss_name}: {e}", level="ERROR")

            self.print_split(order=1)
            sleep(interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", required=False, help="Path to config YAML file", default='./config.yaml')
    parser.add_argument("-i", "--interval", type=int, required=False, help="Polling interval in seconds", default=60)
    args = parser.parse_args()
    app = App(cfg_file=args.config)
    app.run(interval=args.interval)
