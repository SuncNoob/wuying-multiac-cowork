---
name: wuying-cowork
description: >-
  Writes and maintains 无影 Computer Agent Cowork customer docs (README, vibe-coding
  prompts, playbooks) using Diataxis plus Anthropic doc-coauthoring reader tests.
  Use when editing README.md, docs/, customer onboarding, 开通, vibe coding examples,
  or explaining the Git bus / monitor / three Agent Computers.
---

# 无影 Cowork 客户文档

Audience is a **customer who vibe-codes in Cursor**, not a protocol implementer.

Professional basis:

- [Diataxis](https://diataxis.fr/) — tutorials vs how-to vs reference vs explanation
- [Anthropic doc-coauthoring](https://github.com/anthropics/skills/tree/main/skills/doc-coauthoring) — name the reader, gather context, reader-test the page

## Reader

Someone who already has (or will have) three 无影 Ubuntu Agent Computers, GitHub, and Cursor. They should finish the page knowing: **open a monitor, paste one sentence, watch three ACs split work through Git**.

## Diataxis map

| Kind | Lives in | Must answer |
|---|---|---|
| Tutorial | `docs/VIBE-CODING.md` | One copy-paste prompt that actually runs |
| How-to | README 「开通」「监控」 | Exact commands, no theory |
| Reference | PROTOCOL.md, `cowork --help` | States, files, CLI |
| Explanation | README opening + PROTOCOL.md | Why Git, never P2P |

Do not mix a 40-line protocol dump into the first screen of README.

## Hard rules

- Secrets stay in `cowork.local.json` / `COWORK_SSH_PASSWORD` / AC env. Never show a real password in docs.
- Laptop **monitor** (`cowork monitor`) is the customer’s control plane; ACs only talk via Git.
- `mode: browser` fetch must go through **that AC’s Codex** (无影 gateway token), not silent curl/dump-dom.
- Prefer 中文 for customer pages unless the user asked for English.

## Vibe-coding example

When the customer asks 「怎么用」「举个例子」, point them to `docs/VIBE-CODING.md` and tell them to paste the prompt into a **new Cursor Agent chat** opened on this repo.

## Reader test (before you ship a doc change)

A fresh agent with only the markdown should answer:

1. Where do SSH passwords live?
2. How do I see what ac2 is running right now?
3. What sentence do I paste to start coding + crawl together?
4. Why don’t the three ACs SSH to each other?

If it cannot, the page is not ready.
