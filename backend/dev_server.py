"""Start the local Django API with SQLite and the mock AI provider."""

import os
import sys

os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
os.environ["DJANGO_DEBUG"] = "true"
os.environ["USE_SQLITE"] = "true"
os.environ["AI_PROVIDER"] = "mock"

from django.core.management import execute_from_command_line


if __name__ == "__main__":
    arguments = sys.argv[1:] or ["runserver", "8000"]
    execute_from_command_line(["manage.py", *arguments])
