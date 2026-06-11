"""Import the metclouds component modules without Home Assistant installed.

Registers ``custom_components/metclouds`` as a package *without* executing
its ``__init__.py`` (which imports Home Assistant), so the pure modules
(``model``, ``api``, ``const``) can be used standalone.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "metclouds"

if "metclouds" not in sys.modules:
    pkg = types.ModuleType("metclouds")
    pkg.__path__ = [str(PKG_DIR)]
    sys.modules["metclouds"] = pkg
