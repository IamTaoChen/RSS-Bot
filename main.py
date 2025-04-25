from src.Config import Config
from src.Rss import Rss, RssFetchErr, get_newest_time
from src.Ai import AiAgent
from src.Notify import NotifyConfig, Msg
from src import create_rss
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from time import sleep
import argparse


@dataclass
class RssMain:
    rss: Rss = None
    enable: bool = True
    last: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    notifies: list[NotifyConfig] = field(default_factory=list)
    error_count: int = 0
    msgs_buffer: list[Msg] = field(default_factory=list)


class App:
    color_map = {
        'INFO': '\033[34m',     # Blue
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'DEBUG': '\033[90m',    # Gray
        'SUCCESS': '\033[32m'   # Green
    }
    color_reset = '\033[0m'

    def __init__(self, cfg_file: str):
        self.verbose = True
        self.log(f"App parsing config file: {cfg_file}")
        self._cfg_file = cfg_file
        self._config: Config = Config.load_from_yaml(cfg_file=cfg_file)
        self.rss: dict[str, RssMain] = {}
        self._init_rss_()

    @property
    def cfg_file(self) -> str:
        return self._cfg_file

    def log(self, msg: str, level: str = 'INFO'):
        if not self.verbose:
            return
        tz = timezone.utc
        try:
            if self._config.timezone:
                tz = self._config.timezone
        except:
            pass
        now = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S %Z")
        color = self.color_map.get(level.upper(), '')
        print(f"{color}[{now}] [{level.upper()}] {msg}{self.color_reset}")

    def print_split(self, order: int = 0):
        symbol = "="
        size = 50
        if order == 1:
            symbol = "-"
        elif order == 2:
            symbol = "+"
        elif order == 3:
            symbol = "~"
        elif order == 4:
            symbol = 'x'
        print(symbol * size)

    def _init_rss_(self) -> None:
        self.log(f"Initializing RSS...")
        self.log(f"Loading AI agent...")
        ai_agent = AiAgent(ai_config=self._config.ai)
        new_rss_dict: dict[str, Rss] = {}
        for rss_name, rss_config in self._config.rss.items():
            self.print_split(order=3)
            self.log(f"Initializing RSS feed: {rss_name} with the type {rss_config.type}")
            new_rss = create_rss(rss_config=rss_config, ai_agent=ai_agent, translate_to="Chinese")
            rss_main = self.rss.get(rss_name, None)
            if not rss_main:
                # if the rss is not initialized, create a new one
                last = datetime.now(timezone.utc)
                rss_main = RssMain(rss=new_rss, last=last)
            else:
                self.log(f"RSS feed {rss_name} already initialized, keeping the last state. But reloading the config.")
                rss_main.rss = new_rss

            # refill the notify
            notifies = self._config.get_notfies_by_names(self._config.rss_notify[rss_name])
            rss_main.notifies = notifies
            # refill the enable
            enable = self._config.rss_enable[rss_name]
            rss_main.enable = enable

            new_rss_dict[rss_name] = rss_main
            self.log(f"Initialized RSS feed: {rss_name}", level="SUCCESS")
        self.rss = new_rss_dict
        self.print_split(order=3)
        self.log(f"All RSS feeds initialized successfully.", level="SUCCESS")

    def make_error_msg(self, rss_name: str, url: str, error: Exception) -> Msg:
        return Msg(
            title=f"❗ Error: {rss_name}",
            description=f"Something went wrong while processing the RSS feed.\n\nURL: {url}",
            link=url,
            pub_date=datetime.now(timezone.utc),
            msg_type='error',
            contents={
                "Exception": str(error),
                "RSS Name": rss_name
            }
        )

    def run(self, interval: int = 60):
        self.print_split(order=0)
        try:
            while True:
                self.print_split(order=1)
                for rss_name, rss_combine in self.rss.items():
                    self.print_split(order=2)

                    if not getattr(rss_combine, "enable", True):
                        self.log(f"❌ {rss_name} is disabled, skipping...")
                        self.print_split(order=2)
                        continue
                    date_str = NotifyConfig.format_dt(dt=rss_combine.last, tz=self._config.timezone)
                    self.log(f"📡 Start handling RSS - {rss_name} (since {date_str})")

                    try:
                        all_items = rss_combine.rss.fetch()
                        new_rss_items = rss_combine.rss.get_items_since(rss_combine.last)
                        self.log(f"📎 Found {len(new_rss_items)} new item(s)")
                        if new_rss_items:
                            self.log("🧠 Summarizing with AI agent...")
                            self.rss[rss_name].last = get_newest_time(new_rss_items)
                            msgs = rss_combine.rss.summarize(items=new_rss_items, verbose=True)
                            rss_combine.msgs_buffer.extend(msgs)

                        if rss_combine.error_count > 0:
                            self.log(f"✅ {rss_name} is back online after {rss_combine.error_count} failed attempts.")
                            rss_combine.error_count = 0
                            rss_combine.msgs_buffer = [msg for msg in rss_combine.msgs_buffer if msg.msg_type != 'error']

                    except RssFetchErr as e:
                        rss_combine.error_count += 1
                        self.log(f"❗ Error while handling {rss_name} (fail count: {rss_combine.error_count}): {e}", level="ERROR")
                        if rss_combine.error_count == 3:
                            self.log("📬 Notify user about fetch failure...")
                            msg = self.make_error_msg(rss_name, rss_combine.rss.config.url, e)
                            rss_combine.msgs_buffer.append(msg)

                    except Exception as e:
                        self.log(f"❗ Unknown error while handling {rss_name}: {e}", level="ERROR")
                    self.send()
                    self.print_split(order=2)
                    self.print_split(order=1)
                    next_check = datetime.now(timezone.utc) + timedelta(seconds=interval)
                    date_str = NotifyConfig.format_dt(dt=next_check, tz=self._config.timezone)
                    print(f"🕒 Sleep for {interval} seconds... Next check at {date_str}")
                    sleep(interval)
                    self.check_config_and_load()
        except KeyboardInterrupt:
            self.log("🛑 Exiting...")
        except Exception as e:
            self.log(f"❗ Unknown error: {e}", level="ERROR")

    def send(self) -> None:
        for rss_name, rss_combine in self.rss.items():
            if not rss_combine.msgs_buffer:
                continue

            self.log(f"📤 Sending {len(rss_combine.msgs_buffer)} message(s) for {rss_name}...")

            failed_ids = set()
            for notify in rss_combine.notifies:
                failed = notify.send(msgs=rss_combine.msgs_buffer, local_tz=self._config.timezone)
                failed_ids.update(id(msg) for msg in failed)

            rss_combine.msgs_buffer = [msg for msg in rss_combine.msgs_buffer if id(msg) in failed_ids]
            if rss_combine.msgs_buffer:
                self.log(f"⚠️ {rss_name}: {len(rss_combine.msgs_buffer)} message(s) failed to send and will be retried.", level="WARNING")

    def check_config_and_load(self) -> None:
        """
        check if the config is modified, if so, reload the config
        """
        tmp_config: Config = Config.load_from_yaml(cfg_file=self.cfg_file)
        if self._config != tmp_config:
            self.print_split(order=4)
            self.log("Config file changed, reloading...", level="WARNING")
            self._config = tmp_config
            self._init_rss_()
            self.log("Config file reloaded successfully.", level="SUCCESS")
            self.print_split(order=0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", required=False, help="Path to config YAML file", default='./config.yaml')
    parser.add_argument("-i", "--interval", type=int, required=False, help="Polling interval in seconds", default=60)
    args = parser.parse_args()
    app = App(cfg_file=args.config)
    app.run(interval=args.interval)
