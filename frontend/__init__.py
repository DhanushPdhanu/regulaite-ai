# frontend/__init__.py
# Anchors sys.path to the project root so all cross-layer imports resolve correctly.
import sys, os
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
