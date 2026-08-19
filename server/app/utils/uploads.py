"""
Shared helper for resolving upload directories.

`main.py` serves uploaded files via:
    uploads_dir = Path(__file__).parent.parent / "uploads"   # -> server/uploads
    app.mount("/uploads", StaticFiles(directory=str(uploads_dir)))

That mount always resolves to an absolute path anchored on this file's
location, regardless of the process's current working directory (CWD).

Route handlers that *save* uploaded files must use that same absolute
directory. Using a relative path instead (e.g. `"uploads/purchase_orders"`
or `os.makedirs("uploads/purchase_orders")`) resolves against whatever the
CWD happens to be when the app was launched — which usually matches
`server/` if started from a terminal with `cd server`, but does NOT match
if started from an IDE's run/debug button (which often defaults the CWD to
the workspace root, one level up). When that happens, the file still saves
successfully — just to the wrong directory — so the bug is invisible until
someone clicks the resulting URL and gets a 404 from `/uploads/...`.

Always use `get_upload_subdir(...)` below instead of a relative path when
writing an uploaded file, so saving and serving are guaranteed to agree no
matter how the app was started.
"""
from pathlib import Path

# server/ directory (this file lives at server/app/utils/uploads.py, so
# three parents up lands on server/), same anchor used by main.py's mount.
UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"


def get_upload_subdir(subfolder: str) -> Path:
    """Return an absolute path to server/uploads/<subfolder>, creating it
    (and any parent dirs) if it doesn't exist yet. Use this to build the
    filesystem path when writing an uploaded file; the corresponding public
    URL is simply f"/uploads/{subfolder}/{filename}".
    """
    d = UPLOADS_DIR / subfolder
    d.mkdir(parents=True, exist_ok=True)
    return d
