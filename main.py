from src.Config import Config
from src.Utils import LogLevel
from src.Rss import Rss, RssFetchErr, get_newest_time
from src.Ai import AiAgent
from src.Notify import NotifyConfig, Msg
from src import create_rss
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
import argparse
from pathlib import Path
from random import randint
import json
import signal
import threading


@dataclass
class RssMain:
    rss: Rss = None
    enable: bool = True
    last: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    notifies: list[NotifyConfig] = field(default_factory=list)
    error_count: int = 0
    msgs_buffer: list[Msg] = field(default_factory=list)
    last_error: datetime = None


class App:
    def __init__(self, cfg_file: str, cache_dir: str = "./cache", log_level: LogLevel = None):
        self._stop_event = threading.Event()
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        self._cfg_file = Path(cfg_file)
        self._cfg_file_last_mtime = self._cfg_file.stat().st_mtime
        self._config: Config = Config.load_from_yaml(cfg_file=self.cfg_file)
        if isinstance(log_level, LogLevel):
            self._config.log_cfg.level = log_level
        self.log(f"Log level: {self._config.log_cfg.level}", log_anyway=True)
        self.rss: dict[str, RssMain] = {}
        self.cache_dir: Path = Path(cache_dir)
        self.fetch_time_utc: dict[str, datetime] = {}
        self.load_fetch_time()
        self._init_rss_()

    @property
    def cfg_file(self) -> str:
        return self._cfg_file

    def log(self, msg: str | int, level: str | LogLevel = LogLevel.INFO, no_emoji: bool = False, is_spliter: bool = False, force_only_to_console: bool = False, log_anyway: bool = False) -> None:
        # Convert to LogLevel
        level = LogLevel.from_string(level)
        log_cfg = self._config.log_cfg
        current_level = log_cfg.level
        # Skip if below log threshold
        if level.value < current_level.value and not log_anyway:
            return
        if is_spliter:
            if log_cfg.to_console or log_anyway:
                self.print_split(order=msg if isinstance(msg, int) else 0)
            return
        # Format time
        tz = self._config.timezone or timezone.utc
        now = datetime.now(tz)
        formatted_msg = level.warp(message=msg, now=now, no_emoji=no_emoji)

        # Print to console
        if log_cfg.to_console or level in (LogLevel.ERROR, LogLevel.SUCCESS) or force_only_to_console or log_anyway:
            print(formatted_msg)

        # Check if we should log to file
        if log_cfg.file is None or force_only_to_console:
            return
        # Write to file
        filename = self.prepare_logfile(now=now)
        try:
            filename.parent.mkdir(parents=True, exist_ok=True)
            with open(filename, "a", encoding="utf-8") as f:
                f.write(formatted_msg + "\n")
        except Exception as e:
            self.log(f"Failed to write log to file {filename}: {e}", level=LogLevel.ERROR, force_only_to_console=True)

    def prepare_logfile(self, now: datetime | None = None) -> Path:
        log_file = self._config.log_cfg.file
        if not log_file:
            return None
        tz = self._config.timezone or timezone.utc
        filename = log_file
        if log_file.is_dir():
            filename = log_file / "rss.log"
            now = now or datetime.now(tz)
            if filename.exists():
                last_modified = datetime.fromtimestamp(filename.stat().st_mtime, tz)
                if last_modified.date() != now.date():
                    last_modified_str = last_modified.date().isoformat()
                    rotated_name = filename.parent / f"rss-{last_modified_str}.log"
                    if rotated_name.exists():
                        timestamp_ms = int(now.timestamp() * 1000)
                        rotated_name = filename.parent / f"rss-{last_modified_str}-{timestamp_ms}.log"
                    try:
                        filename.rename(rotated_name)
                    except Exception as e:
                        self.log(f"Failed to rotate log file {filename} to {rotated_name}: {e}", level=LogLevel.ERROR, force_only_to_console=True)
        return filename

    @property
    def fetch_time_file(self) -> Path:
        return self.cache_dir / "fetch_time.json"

    def signal_handler(self, signum, frame):
        self.log(f"Received signal {signum}, shutting down gracefully...", level=LogLevel.WARNING)
        self.save_fetch_time()
        self._stop_event.set()

    def save_fetch_time(self) -> None:
        data = {k: v.isoformat() for k, v in self.fetch_time_utc.items()}
        with open(self.fetch_time_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        self.log(f"Saved last check time to {self.fetch_time_file}", level="DEBUG")

    def load_fetch_time(self) -> None:
        if not self.fetch_time_file.exists():
            self.log(f"Fetch time file {self.fetch_time_file} does not exist, creating a new one.", level="DEBUG")
            self.fetch_time_file.touch()
            return

        with open(self.fetch_time_file, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                for rss_name, last_time_str in data.items():
                    self.fetch_time_utc[rss_name] = datetime.fromisoformat(last_time_str)
                self.log(f"Loaded last check time from {self.fetch_time_file}", level=LogLevel.DEBUG)
                self.log(f"Last fetch times: {self.fetch_time_utc}", level=LogLevel.DEBUG)
            except json.JSONDecodeError as e:
                self.log(f"Failed to load fetch time JSON: {e}", level=LogLevel.ERROR)
                self.log("Using current time for all RSS feeds.", level=LogLevel.WARNING)

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
        self.log("Initializing RSS...", log_anyway=True)
        self.log("Loading AI agent...", log_anyway=True)
        ai_agent = AiAgent(ai_config=self._config.ai)
        new_rss_dict: dict[str, Rss] = {}
        translate_to = self._config.translate_to
        for rss_name, rss_config in self._config.rss.items():
            self.log(msg=3, is_spliter=True)
            self.log(f"Initializing RSS feed: {rss_name} with the type {rss_config.type}")
            if rss_config.filter_regex:
                self.log(f"Filter regex for {rss_name}: {rss_config.filter_regex}")
            # refill the enable
            enable = self._config.rss_enable.get(rss_name, True)
            new_rss = create_rss(rss_config=rss_config, ai_agent=ai_agent, translate_to=translate_to, timeout=10, run_init=False)
            rss_main = self.rss.get(rss_name, None)
            if not rss_main:
                # if the rss is not initialized, create a new one
                last = datetime.now(timezone.utc)
                if self._config.rss_from_now.get(rss_name, True):
                    self.log(f"RSS feed {rss_name} will fetch from now.", level=LogLevel.INFO)
                else:
                    logged_last_time = self.fetch_time_utc.get(rss_name, None)
                    if logged_last_time is None:
                        self.log(f"RSS feed {rss_name} has no last fetch time logged, will fetch from now.", level=LogLevel.WARNING)
                        logged_last_time = last
                        if enable:
                            self.fetch_time_utc[rss_name] = last
                    else:
                        self.log(f"RSS feed {rss_name} will fetch from the last time which is logged at file, not from now.", level=LogLevel.INFO)
                    last = logged_last_time
                rss_main = RssMain(rss=new_rss, last=last)
            else:
                self.log(f"RSS feed {rss_name} already initialized, keeping the last state. But reloading the config.")
                rss_main.rss = new_rss

            # refill the notify
            notifies = self._config.get_notfies_by_names(self._config.rss_notify[rss_name])
            notifies_names = [notify.name for notify in notifies]
            if len(notifies) <= 0:
                self.log(f"No notify found for {rss_name}, please check the config file.", level=LogLevel.WARNING)
            else:
                self.log(f"Found {len(notifies)} notify(s) for {rss_name}: {', '.join(notifies_names)}")
            rss_main.notifies = notifies
            rss_main.enable = enable
            new_rss_dict[rss_name] = rss_main
            if not enable:
                self.log(f"RSS feed {rss_name} is disabled, it will not be fetched.", level=LogLevel.WARNING)
            else:
                msg = f"RSS feed {rss_name} initialized with {len(rss_main.notifies)} notify(s) and last fetch time {NotifyConfig.format_dt(dt=rss_main.last, tz=self._config.timezone)}"
                self.log(msg, level=LogLevel.SUCCESS)
        self.rss = new_rss_dict
        self.log(msg=3, is_spliter=True)
        enable_names = [rss_name for rss_name, rss in self.rss.items() if rss.enable]
        diable_names = [rss_name for rss_name, rss in self.rss.items() if not rss.enable]
        self.log("📰\tRSS feeds will be fetched:", no_emoji=True, log_anyway=True)
        if len(enable_names) > 0:
            self.log(f"\t  - ✅ \033[32mEnabled \033[0m: {', '.join(enable_names)}", no_emoji=True, log_anyway=True)
        if len(diable_names) > 0:
            self.log(f"\t  - ❌ \033[31mDisabled\033[0m: {', '.join(diable_names)}", no_emoji=True, log_anyway=True)
        self.log(msg=3, is_spliter=True)
        self.log("All RSS feeds initialized successfully.", level=LogLevel.SUCCESS)

    def make_error_msg(self, rss_name: str, url: str, error: Exception) -> Msg:
        return Msg(title=f"Error: {rss_name}", description=f"Something went wrong while processing the RSS feed.\n\nURL: {url}", link=url, pub_date=datetime.now(timezone.utc), msg_type="error", contents={"Exception": str(error), "RSS Name": rss_name})

    def run(self, interval: int = 60):
        self.log(msg=0, is_spliter=True, log_anyway=True)
        self.log(f"Starting RSS fetcher every {interval} seconds", log_anyway=True)
        try:
            while not self._stop_event.is_set():
                t0 = datetime.now(tz=timezone.utc)
                self.log(msg=1, is_spliter=True)
                for rss_name, rss_combine in self.rss.items():
                    self.log(msg=2, is_spliter=True)
                    if not self._config.rss_enable.get(rss_name, True):
                        self.log(f"RSS feed {rss_name} is disabled, skipping...")
                        continue
                    date_str = NotifyConfig.format_dt(dt=rss_combine.last, tz=self._config.timezone)
                    self.log(f"📡\tStart handling RSS - {rss_name} (since {date_str})", no_emoji=True)

                    try:
                        new_rss_items = rss_combine.rss.get_items_since(since=rss_combine.last, fetch=True, newest_at_first=False)
                        self.log(f"📎\tFound {len(new_rss_items)} new item(s) for {rss_name}", no_emoji=True)
                        if new_rss_items:
                            self.log("🧠 Summarizing with AI agent...", no_emoji=True)
                            self.rss[rss_name].last = get_newest_time(new_rss_items)
                            summarized_verbose = self._config.log_cfg.level == LogLevel.DEBUG
                            msgs = rss_combine.rss.summarize(items=new_rss_items, verbose=summarized_verbose)
                            rss_combine.msgs_buffer.extend(msgs)
                            if not summarized_verbose:
                                for item in msgs:
                                    pub_date_str = NotifyConfig.format_dt(dt=item.pub_date, tz=self._config.timezone)
                                    self.log(f"  - ({pub_date_str}) {item.title}", no_emoji=True)
                        if rss_combine.error_count > 0:
                            self.log(f"✅\t{rss_name} is back online after {rss_combine.error_count} failed attempts.", no_emoji=True)
                            rss_combine.error_count = 0
                            rss_combine.msgs_buffer = [msg for msg in rss_combine.msgs_buffer if msg.msg_type != "error"]
                    except RssFetchErr as e:
                        rss_combine.error_count += 1
                        self.log(f"Error while handling {rss_name} (fail count: {rss_combine.error_count}): {e}", level=LogLevel.ERROR)
                        if rss_combine.error_count == 3:
                            self.log("📬\tNotify user about fetch failure...", no_emoji=True)
                            msg = self.make_error_msg(rss_name, rss_combine.rss.config.url, e)
                            rss_combine.msgs_buffer.append(msg)
                    except Exception as e:
                        self.log(f"Unknown error while handling {rss_name}: {e}", level=LogLevel.ERROR)
                    self.send()
                    self.log(msg=2, is_spliter=True)
                self.log(msg=1, is_spliter=True)
                # Calculate elapsed time and remaining sleep time
                elapsed = datetime.now(tz=timezone.utc) - t0
                remaining = max(timedelta(seconds=interval) - elapsed, timedelta(0))
                sleep_seconds = remaining.total_seconds() + randint(-5, 5)  # Add a random jitter of up to 5 seconds
                # Calculate next check time and format it
                next_check_utc = datetime.now(timezone.utc) + remaining
                next_check_str = NotifyConfig.format_dt(dt=next_check_utc, tz=self._config.timezone)
                # Print the waiting message
                self.log(f"🕒\tWaiting {sleep_seconds:.2f}s... Next check at {next_check_str}", no_emoji=True)
                # Save the check time to file
                self.save_fetch_time()
                # sleep
                self._stop_event.wait(timeout=sleep_seconds)
                self.check_config_and_load()
        except KeyboardInterrupt:
            self.log("🛑\tExiting...", no_emoji=True)
        except Exception as e:
            self.log(f"Unknown error: {e}", level=LogLevel.ERROR)

    def send(self) -> None:
        for rss_name, rss_combine in self.rss.items():
            if not rss_combine.msgs_buffer:
                continue

            self.log(f"📤\tSending {len(rss_combine.msgs_buffer)} message(s) for {rss_name}...", no_emoji=True)

            failed_ids = set()
            for notify in rss_combine.notifies:
                self.log(f"🔔\tSending {len(rss_combine.msgs_buffer)} message(s) to {notify.name}...", no_emoji=True)
                failed = notify.send(msgs=rss_combine.msgs_buffer, local_tz=self._config.timezone)
                failed_ids.update(id(msg) for msg in failed)

            rss_combine.msgs_buffer = [msg for msg in rss_combine.msgs_buffer if id(msg) in failed_ids]
            if rss_combine.msgs_buffer:
                self.log(f"{rss_name}: {len(rss_combine.msgs_buffer)} message(s) failed to send and will be retried.", level=LogLevel.WARNING)
            else:
                self.fetch_time_utc[rss_name] = rss_combine.last

    def check_config_and_load(self) -> None:
        """
        check if the config is modified, if so, reload the config
        """
        if not self.cfg_file.exists():
            return
        _cfg_file_last_mtime = self._cfg_file.stat().st_mtime
        if _cfg_file_last_mtime == self._cfg_file_last_mtime:
            return
        self.log(msg=4, is_spliter=True)
        self.log(f"Config file {self.cfg_file} has been modified, Checking...")
        self._cfg_file_last_mtime = _cfg_file_last_mtime
        tmp_config: Config = Config.load_from_yaml(cfg_file=self.cfg_file)
        if self._config != tmp_config:
            self.log("Config is changed, reloading...", level=LogLevel.WARNING, log_anyway=True)
            self._config = tmp_config
            self._init_rss_()
            self.log("Config file reloaded successfully.", level=LogLevel.SUCCESS)
            self.log(msg=0, is_spliter=True, log_anyway=True)
        else:
            self.log("Config file is changed, but no significant changes detected.", level=LogLevel.INFO)
            self.log(msg=4, is_spliter=True)


if __name__ == "__main__":
    import os
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", required=False, help="Path to config YAML file", default="./config.yaml")
    parser.add_argument("-d", "--cache-dir", required=False, help="Path to cache dir", default="/tmp/rss_cache")
    parser.add_argument("-l", "--log-level", required=False, help="Log level", default=None)
    parser.add_argument("-i", "--interval", type=int, required=False, help="Polling interval in seconds", default=None)
    args = parser.parse_args()

    interval_env = os.getenv("RSS_INTERVAL")
    interval_sec = args.interval if args.interval is not None else int(interval_env) if interval_env else 60

    cache_dir_env = os.getenv("RSS_CACHE_DIR")
    cache_dir = args.cache_dir if args.cache_dir else cache_dir_env if cache_dir_env else "/tmp/rss_cache"
    if not Path(cache_dir).exists():
        Path(cache_dir).mkdir(parents=True, exist_ok=True)

    log_level_str = os.getenv("RSS_LOG_LEVEL") or args.log_level
    log_level = LogLevel.from_string(log_level_str) if log_level_str else None

    cfg_file = args.config
    print(f"{LogLevel.INFO.emoji}  Using config file: {cfg_file}")
    app = App(cfg_file=cfg_file, cache_dir=cache_dir, log_level=log_level)
    app.run(interval=interval_sec)
