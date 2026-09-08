# AI Crawler playbook

Roles: dispatcher (`enqueue`) → fetcher (`fetch`) → analyst (`extract`).

Hard rules:

- `allow_hosts` is required
- only `http` / `https`
- a URL whose host is not in the whitelist is rejected, never fetched

The dispatcher writes `.cowork/queue/<task>.json` and spawns fetch + extract.
The analyst writes `.cowork/results/<task>/structured.jsonl`.
