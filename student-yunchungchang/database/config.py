import os

from dotenv import load_dotenv

load_dotenv()


def get_cfg(name, default):
    return os.getenv(name, default)


DATABASE_PORT = int(get_cfg("DATABASE_PORT", 5004))
