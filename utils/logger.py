import sys
from datetime import datetime

class Logger:
    @staticmethod
    def log(message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}", file=sys.stderr)

    @staticmethod
    def info(message: str):
        Logger.log(message, "INFO")

    @staticmethod
    def error(message: str):
        Logger.log(message, "ERROR")

    @staticmethod
    def warning(message: str):
        Logger.log(message, "WARNING")
