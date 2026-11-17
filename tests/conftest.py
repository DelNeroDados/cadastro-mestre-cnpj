import sys
from pathlib import Path

# O Python portátil não põe a raiz do projeto no sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
