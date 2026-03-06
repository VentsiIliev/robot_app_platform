import logging


class _ColorFormatter(logging.Formatter):
    _RESET  = "\033[0m"
    _COLORS = {
        logging.DEBUG:    "\033[36m",   # cyan
        logging.INFO:     "\033[32m",   # green
        logging.WARNING:  "\033[33m",   # yellow
        logging.ERROR:    "\033[31m",   # red
        logging.CRITICAL: "\033[1;31m", # bold red
    }

    def format(self, record: logging.LogRecord) -> str:
        color = self._COLORS.get(record.levelno, self._RESET)
        return f"{color}{super().format(record)}{self._RESET}"


def setup_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(_ColorFormatter(
        fmt="%(asctime)s [%(levelname)-8s] %(name)s.%(funcName)s — %(message)s",
        datefmt="%H:%M:%S",
    ))
    logging.basicConfig(level=logging.DEBUG, handlers=[handler])

    # suppress noisy third-party loggers
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)