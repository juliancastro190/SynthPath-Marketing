import os

from dotenv import load_dotenv

load_dotenv()

ASSISTANT_NAME = os.environ.get("GRIFFIN_NAME", "Griffin")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
MODEL_NAME = os.environ.get("GRIFFIN_MODEL", "claude-sonnet-5")
