from __future__ import annotations

import re

import help_workspace
import resource_ui_workspace
import viewshed_core
from viewshed_core import resource_path


VERSION = resource_path("VERSION").read_text(encoding="utf-8").strip()
if not re.fullmatch(r"\d+\.\d+\.\d+", VERSION):
    raise RuntimeError(f"Invalid Signal Peak release version: {VERSION!r}")


def _set_current_release_docs() -> None:
    workspace = getattr(help_workspace, "ViewshedWorkspace", None)
    docs = getattr(workspace, "DOCS", None)
    if not isinstance(docs, list):
        return
    current = ("2.2.1 Release Notes", "docs/RELEASE_NOTES_2.2.1.md")
    historical_paths = {
        "docs/RELEASE_NOTES_2.0.0.md",
        "docs/RELEASE_NOTES_2.0.1.md",
        "docs/RELEASE_NOTES_2.1.0.md",
        "docs/RELEASE_NOTES_2.2.0.md",
        "docs/RELEASE_NOTES_2.2.1.md",
    }
    updated = [entry for entry in docs if entry[1] not in historical_paths]
    insert_at = next(
        (i for i, entry in enumerate(updated) if entry[1] == "docs/RELEASE_NOTES_1.2.0.md"),
        len(updated),
    )
    updated.insert(insert_at, current)
    workspace.DOCS = updated


# Apply the single packaged release version before viewshed_app imports its
# version symbols or constructs the Help/About and Resources workspaces.
viewshed_core.APP_VERSION = VERSION
help_workspace.PRODUCT_VERSION = VERSION
help_workspace.APP_VERSION = VERSION
resource_ui_workspace.PRODUCT_VERSION = VERSION
_set_current_release_docs()

_original_sync_release_identity = resource_ui_workspace._sync_release_identity


def _sync_release_identity_for_current_release() -> None:
    _original_sync_release_identity()
    _set_current_release_docs()


resource_ui_workspace._sync_release_identity = _sync_release_identity_for_current_release

from viewshed_app import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
