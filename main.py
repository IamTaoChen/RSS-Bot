from src.Config import Config
from src.Rss import Rss, RssFetchErr, get_newest_time
from src.Ai import AiAgent
from src.Notify import NotifyConfig, Msg
from src import create_rss
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from time import sleep
import argparse
from pathlib import Path
from random import randint


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
        "INFO": "\033[34m",  # Blue
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "DEBUG": "\033[90m",  # Gray
        "SUCCESS": "\033[32m",  # Green
    }
    color_reset = "\033[0m"

    def __init__(self, cfg_file: str, cache_dir: str = "./cache"):
        self.verbose = True
        self.log(f"App parsing config file: {cfg_file}")
        self._cfg_file = Path(cfg_file)
        self._cfg_file_last_mtime = self._cfg_file.stat().st_mtime
        self._config: Config = Config.load_from_yaml(cfg_file=self.cfg_file)
        self.rss: dict[str, RssMain] = {}
        self.cache_dir: Path = Path(cache_dir)
        self.check_time_utc: datetime = datetime.now(timezone.utc)
        self.load_check_time()
        self._init_rss_()

    @property
    def cfg_file(self) -> str:
        return self._cfg_file

    def log(self, msg: str, level: str = "INFO"):
        if not self.verbose:
            return
        tz = timezone.utc
        try:
            if self._config.timezone:
                tz = self._config.timezone
        except:
            pass
        now = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S %Z")
        color = self.color_map.get(level.upper(), "")
        print(f"{color}[{now}] [{level.upper()}] {msg}{self.color_reset}")

    @property
    def check_time_file(self) -> Path:
        return self.cache_dir / "check_time.txt"

    def save_check_time(self) -> None:
        if not self.check_time_utc:
            self.check_time_utc = datetime.now(timezone.utc)
        with open(self.check_time_file.as_posix(), "w") as f:
            f.write(self.check_time_utc.isoformat())

    def load_check_time(self) -> None:
        try:
            with open(self.check_time_file.as_posix(), "r") as f:
                self.check_time_utc = datetime.fromisoformat(f.read().strip())
                self.log(f"Loaded last check time: {self.check_time_utc.isoformat()}", level="DEBUG")
        except FileNotFoundError:
            self.check_time_utc = datetime.now(timezone.utc)
        except Exception as e:
            self.log(f"Error loading check time: {e}", level="ERROR")
            self.check_time_utc = datetime.now(timezone.utc)

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
            symbol = "x"
        print(symbol * size)

    def _init_rss_(self) -> None:
        self.log(f"Initializing RSS...")
        self.log(f"Loading AI agent...")
        ai_agent = AiAgent(ai_config=self._config.ai)
        new_rss_dict: dict[str, Rss] = {}
        self.log(f"Check RSS feeds from {self.check_time_utc.isoformat()}")
        for rss_name, rss_config in self._config.rss.items():
            self.print_split(order=3)
            self.log(f"Initializing RSS feed: {rss_name} with the type {rss_config.type}")
            new_rss = create_rss(rss_config=rss_config, ai_agent=ai_agent, translate_to="Chinese", timeout=10)
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
            notifies_names = [notify.name for notify in notifies]
            if len(notifies) <= 0:
                self.log(f"❗ No notify found for {rss_name}, please check the config file.", level="Warning")
            else:
                self.log(f"Found {len(notifies)} notify(s) for {rss_name}: {', '.join(notifies_names)}")
            rss_main.notifies = notifies
            # refill the enable
            enable = self._config.rss_enable[rss_name]
            if not enable:
                self.log(f"❗ RSS feed {rss_name} is disabled, it will not be fetched.", level="WARNING")
            rss_main.enable = enable
            rss_main.last = self.check_time_utc
            new_rss_dict[rss_name] = rss_main
            self.log(f"Initialized RSS feed: {rss_name}", level="SUCCESS")
        self.rss = new_rss_dict
        self.print_split(order=3)
        enable_names = [rss_name for rss_name, rss in self.rss.items() if rss.enable]
        diable_names = [rss_name for rss_name, rss in self.rss.items() if not rss.enable]
        print("📰 RSS feeds will be fetched:")
        if len(enable_names) > 0:
            print(f"  - ✅ \033[32mEnabled\033[0m: {', '.join(enable_names)}")
        if len(diable_names) > 0:
            print(f"  - ❌ \033[31mDisabled\033[0m: {', '.join(diable_names)}")
        self.print_split(order=3)
        self.log(f"All RSS feeds initialized successfully.", level="SUCCESS")

    def make_error_msg(self, rss_name: str, url: str, error: Exception) -> Msg:
        return Msg(title=f"❗ Error: {rss_name}", description=f"Something went wrong while processing the RSS feed.\n\nURL: {url}", link=url, pub_date=datetime.now(timezone.utc), msg_type="error", contents={"Exception": str(error), "RSS Name": rss_name})

    def run(self, interval: int = 60):
        self.print_split(order=0)
        try:
            while True:
                fetch_success: list[bool]= []
                t0 = datetime.now(tz=timezone.utc)
                self.print_split(order=1)
                for rss_name, rss_combine in self.rss.items():
                    self.print_split(order=2)

                    if not getattr(rss_combine, "enable", True):
                        continue
                    date_str = NotifyConfig.format_dt(dt=rss_combine.last, tz=self._config.timezone)
                    self.log(f"📡 Start handling RSS - {rss_name} (since {date_str})")

                    try:
                        # all_items = rss_combine.rss.fetch()
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
                            rss_combine.msgs_buffer = [msg for msg in rss_combine.msgs_buffer if msg.msg_type != "error"]
                        fetch_success.append(True)
                    except RssFetchErr as e:
                        rss_combine.error_count += 1
                        self.log(f"❗ Error while handling {rss_name} (fail count: {rss_combine.error_count}): {e}", level="ERROR")
                        if rss_combine.error_count == 3:
                            self.log("📬 Notify user about fetch failure...")
                            msg = self.make_error_msg(rss_name, rss_combine.rss.config.url, e)
                            rss_combine.msgs_buffer.append(msg)
                        fetch_success.append(False)
                    except Exception as e:
                        self.log(f"❗ Unknown error while handling {rss_name}: {e}", level="ERROR")
                        fetch_success.append(False)
                    self.send()
                    self.print_split(order=2)
                self.print_split(order=1)
                # 计算已耗时和剩余等待时间
                elapsed = datetime.now(tz=timezone.utc) - t0
                remaining = max(timedelta(seconds=interval) - elapsed, timedelta(0))
                sleep_seconds = remaining.total_seconds() + randint(-5, 5)  # Add a random jitter of up to 5 seconds
                # 计算下次检查时间并格式化
                next_check_utc = datetime.now(timezone.utc) + remaining 
                next_check_str = NotifyConfig.format_dt(dt=next_check_utc, tz=self._config.timezone)
                # 打印信息并等待
                print(f"🕒 Waiting {sleep_seconds:.2f}s... Next check at {next_check_str}")
                # Save the check time to file
                if all(fetch_success):
                    self.check_time_utc = t0
                    self.save_check_time()
                # sleep
                sleep(sleep_seconds)
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
                self.log(f"🔔 Sending {len(rss_combine.msgs_buffer)} message(s) to {notify.name}...")
                failed = notify.send(msgs=rss_combine.msgs_buffer, local_tz=self._config.timezone)
                failed_ids.update(id(msg) for msg in failed)

            rss_combine.msgs_buffer = [msg for msg in rss_combine.msgs_buffer if id(msg) in failed_ids]
            if rss_combine.msgs_buffer:
                self.log(f"⚠️ {rss_name}: {len(rss_combine.msgs_buffer)} message(s) failed to send and will be retried.", level="WARNING")

    def check_config_and_load(self) -> None:
        """
        check if the config is modified, if so, reload the config
        """
        if not self.cfg_file.exists():
            return
        _cfg_file_last_mtime = self._cfg_file.stat().st_mtime
        if _cfg_file_last_mtime == self._cfg_file_last_mtime:
            return
        self._cfg_file_last_mtime = _cfg_file_last_mtime
        tmp_config: Config = Config.load_from_yaml(cfg_file=self.cfg_file)
        if self._config != tmp_config:
            self.print_split(order=4)
            self.log("Config file changed, reloading...", level="WARNING")
            self._config = tmp_config
            self._init_rss_()
            self.log("Config file reloaded successfully.", level="SUCCESS")
            self.print_split(order=0)


if __name__ == "__main__":
    import os
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", required=False, help="Path to config YAML file", default="./config.yaml")
    parser.add_argument("-d", "--cache-dir", required=False, help="Path to cache dir", default="/tmp/rss_cache")
    parser.add_argument("-i", "--interval", type=int, required=False, help="Polling interval in seconds", default=None)
    args = parser.parse_args()

    interval_env = os.getenv("RSS_INTERVAL")
    interval_sec = args.interval if args.interval is not None else int(interval_env) if interval_env else 60

    cache_dir_env = os.getenv("RSS_CACHE_DIR")
    cache_dir = args.cache_dir if args.cache_dir else cache_dir_env if cache_dir_env else "/tmp/rss_cache"
    if not Path(cache_dir).exists():
        Path(cache_dir).mkdir(parents=True, exist_ok=True)

    app = App(cfg_file=args.config, cache_dir=cache_dir)
    app.log(f"Fetch RSS evey {interval_sec} second")
    app.run(interval=interval_sec)
