# AI Crawler playbook

Roles: dispatcher (`enqueue`) → fetcher (`fetch`) → analyst (`extract`).

Hard rules:

- `allow_hosts` is required
- only `http` / `https`
- a URL whose host is not in the whitelist is rejected, never fetched

The dispatcher writes `.cowork/queue/<task>.json` and **fans out one fetch task per seed URL**, so multiple Agent Computers crawl in parallel. The analyst writes `.cowork/results/<task>/structured.jsonl` and `pics/CATALOG.md`.

## Browser fetch (`mode: browser`)

Each Agent Computer runs **`codex exec`** with that machine's Wuying gateway token (not a shared laptop token). The session must show up in the 无影 console.

Codex should:

- Use the **browser-use** MCP / real browser
- Open the official site, click into product detail pages (子页面)
- Save jewelry photos under `pics/<brand>/`
- Stay inside `allow_hosts`

Do not silently replace Codex with dump-dom or products.json for this mode.
