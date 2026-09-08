# Cowork

无影 Computer Agent 的开源多智能体协作协议。

三台互相隔离的 Ubuntu Agent 电脑**不直连**。它们只通过 **一个 GitHub 仓库**认领任务、交卷、打心跳。笔记本上的本地网页是你的监控台。

| 你要做的事 | 走哪条路 |
|---|---|
| 让三台机一起写代码 | `coding`：plan → implement → review |
| 让三台机一起抓网页 | `crawler`：enqueue → fetch → extract（必须域名白名单） |
| 看谁在干活、卡住就改派 | 本机 `cowork monitor` → http://127.0.0.1:8765/ |

凭证全部留在你这边。本项目不代持密钥，也禁止把密码推进 Git。

## 开通（How-to）

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

cowork auth github

export COWORK_SSH_PASSWORD='你的SSH密码'
cowork auth ssh \
  --host 你的无影公网IP \
  --agent ac1:端口:planner \
  --agent ac2:端口:builder \
  --agent ac3:端口:reviewer

cowork project create --name demo --scenario all
cowork bootstrap
```

本地配置在 `~/.config/cowork/config.json` 或仓库内 `cowork.local.json`（已 gitignore）。

## Vibe coding（Tutorial）

不要先背协议。打开 Cursor，把 [docs/VIBE-CODING.md](docs/VIBE-CODING.md) 里的提示词整段贴进 Agent。

Agent 会替你：装 runtime、丢 coding + crawler 各一条任务、打开监控页。你只需要在浏览器里看三台 AC 的卡片和「任务描述」列。

## 监控（How-to）

```bash
cowork monitor --open
# 指定总线仓库时：
# COWORK_CONFIG=cowork.jewelry.json cowork monitor --root /path/to/bus --open
```

页面每 3 秒经 SSH 看各机 `coworkd` / `codex exec`。点「下发」会把未完成任务写成 `claimed` 并唤醒对应 AC（不必干等下一轮 poll）。

`mode: browser` 的抓取必须走**那台 Agent Computer 自己的 Codex**（无影网关 token），控制台里才能看到 AI 会话。

## 说明与参考

- 为什么用 Git、状态机、认领规则：[PROTOCOL.md](PROTOCOL.md)
- 爬虫白名单与 browser 抓取：[scenarios/crawler/PLAYBOOK.md](scenarios/crawler/PLAYBOOK.md)
- 编码流水线：[scenarios/coding/PLAYBOOK.md](scenarios/coding/PLAYBOOK.md)

```bash
pytest -q
```
