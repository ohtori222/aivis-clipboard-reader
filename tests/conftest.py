import os
import sys
from unittest.mock import MagicMock

# Add src directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

# Mock external dependencies that might not work in CI
sys.modules["sounddevice"] = MagicMock()
sys.modules["soundfile"] = MagicMock()
sys.modules["pyperclip"] = MagicMock()
sys.modules["keyboard"] = MagicMock()

# Mock ConfigManager if needed (can be imported after modules are mocked)
