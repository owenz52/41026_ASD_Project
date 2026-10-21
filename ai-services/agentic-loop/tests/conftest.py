import sys
from pathlib import Path

# The agentic loop runs as a script from its own directory, so its modules
# import each other as top-level modules.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
