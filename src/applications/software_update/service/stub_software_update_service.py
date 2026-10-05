from .i_software_update_service import ISoftwareUpdateService


class StubSoftwareUpdateService(ISoftwareUpdateService):
    def __init__(self):
        self.staged = ""
        self.scheduled = False

    def get_status(self):
        return {"installed": "1.0.0", "staged": self.staged,
                "configuration": "updates.json", "enabled": True}

    def check(self):
        return {"version": "1.1.0", "available": True}

    def download(self):
        self.staged = "1.1.0"
        return {"version": self.staged}

    def schedule_installation(self):
        if not self.staged:
            raise RuntimeError("Download a release first")
        self.scheduled = True
