from __future__ import annotations

import re

import help_workspace
import resource_ui_workspace
import viewshed_core
from viewshed_core import resource_path


VERSION = resource_path("VERSION").read_text(encoding="utf-8").strip()
if not re.fullmatch(r"\d+\.\d+\.\d+", VERSION):
    raise RuntimeError(f"Invalid Signal Peak release version: {VERSION!r}")

# Apply the single packaged release version before viewshed_app imports its
# version symbols or constructs the Help/About and Resources workspaces.
viewshed_core.APP_VERSION = VERSION
help_workspace.PRODUCT_VERSION = VERSION
help_workspace.APP_VERSION = VERSION
resource_ui_workspace.PRODUCT_VERSION = VERSION

from viewshed_app import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
