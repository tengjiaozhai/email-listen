import sys
from pathlib import Path

# Add scripts/ to Python path so tests can import slider_solver directly
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
