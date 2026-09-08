"""Run Codex on the Agent Computer so Wuying gateway sessions are visible."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

CODEX_TIMEOUT_SECONDS = 1800
CODEX_LEASE_SECONDS = 2400
DEFAULT_MAX_IMAGES = 16
MIN_PDP_PAGES = 12


def jewelry_prompt(brand: str, url: str, allow_hosts: list[str], limit: int, pic_dir: str) -> str:
    hosts = ", ".join(allow_hosts)
    need = min(limit, MIN_PDP_PAGES)
    return f"""You are a 无影 Computer Agent. Use THIS machine's Codex tools and the browser-use MCP (real Chrome) so the session is visible in the Wuying console. Consume this Agent Computer's own Wuying gateway token. Do not ask for approval.

Brand: {brand}
Official listing URL (start here, this is NOT the image source): {url}
Image output directory (create if needed, overwrite old files): {pic_dir}
Save {limit} unique product photos from at least {need} distinct product detail pages.
Allowed hosts only: {hosts}

Hard rules — listing-page thumbnails are a FAIL:
1. Open the official listing in the browser. Do not use a search engine.
2. Click into individual product DETAIL pages (子页面). Required URL shapes:
   - Shopify: /products/<slug>
   - ARTIDA OUD: /item/detail/...
   - synchronicity / BASE: /items/<id>
   Do NOT download images while still on /collections/, category, or home.
3. On each detail page, save the MAIN product photo of the jewelry itself (hero / og:image / first gallery still). Prefer the largest file (width>=800 if possible). Use curl or the browser download.
4. One product page → one file. No duplicate SKUs, no two sizes of the same CDN asset.
5. Skip logos, favicons, banners, models-only lifestyle if no jewelry is visible, payment icons, about-us stones, campaign KV.
6. Filenames: 01.jpg … {limit:02d}.jpg (png/webp ok).
7. Write {pic_dir}/manifest.json as a JSON array:
   [{{"file":"01.jpg","source_page":"https://.../products/...","image_url":"https://cdn...","product":"name"}}]
   source_page MUST be the detail URL from step 2, never the listing URL.

When finished, print DONE, how many distinct detail pages you opened, and the file list.
If you cannot open detail pages, print FAIL and why. Saving {limit} images all from the listing page is FAIL.
"""


def codex_bin() -> str | None:
    return shutil.which("codex")


def run_codex(prompt: str, cwd: Path, timeout: int = CODEX_TIMEOUT_SECONDS) -> dict:
    binary = codex_bin()
    if not binary:
        return {"ok": False, "code": 127, "stdout": "", "stderr": "codex not found", "cmd": []}
    cwd = cwd.resolve()
    cmd = [
        binary,
        "exec",
        "--dangerously-bypass-approvals-and-sandbox",
        "-s",
        "danger-full-access",
        "-C",
        str(cwd),
        "-c",
        f'projects."{cwd}".trust_level="trusted"',
        prompt,
    ]
    env = os.environ.copy()
    env.setdefault("HOME", str(Path.home()))
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=env,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        stdout = proc.stdout.decode("utf-8", "replace")
        stderr = proc.stderr.decode("utf-8", "replace")
        return {
            "ok": proc.returncode == 0,
            "code": proc.returncode,
            "stdout": stdout[-8000:],
            "stderr": stderr[-4000:],
            "cmd": cmd[:8],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "code": 124,
            "stdout": (exc.stdout or b"").decode("utf-8", "replace")[-4000:],
            "stderr": "codex exec timed out",
            "cmd": cmd[:8],
        }
    except OSError as exc:
        return {"ok": False, "code": 1, "stdout": "", "stderr": str(exc), "cmd": cmd[:8]}
