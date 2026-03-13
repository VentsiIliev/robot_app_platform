class CancellationToken:
    def __init__(self) -> None:
        self._cancelled = False
        self._reason    = ""

    def cancel(self, reason: str = "") -> None:
        self._cancelled = True
        self._reason    = reason

    def is_cancelled(self) -> bool:
        return self._cancelled

    def get_cancellation_reason(self) -> str:
        return self._reason

