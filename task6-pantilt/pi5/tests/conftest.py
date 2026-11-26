"""Makes the programs in pi5/ and the helpers in tests/ importable for pytest."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
