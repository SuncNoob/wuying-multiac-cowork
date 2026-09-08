# Cowork

无影 Computer Agent 的开源多智能体协作协议。多台隔离的 Ubuntu Agent 电脑不直连，只通过**一个 Git 仓库**交流、分活、交卷。

覆盖两个场景：

- **AI Coding**：Planner 拆任务 → Builder 实现 → Reviewer 验收
- **AI 爬虫**：Dispatcher 入队 → Fetcher 抓取 → Analyst 抽取（必须域名白名单）

## 客户五步开通

凭证全部留在客户侧，本项目不代持。密钥禁止进入 Git 仓库。

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 1. 自己认证 GitHub（需已 gh auth login）
cowork auth github

# 2. 自己认证无影 AC 的 SSH
export COWORK_SSH_PASSWORD='your-ssh-password'
cowork auth ssh \
  --host 8.139.215.238 \
  --agent ac1:56735:planner \
  --agent ac2:53326:builder \
  --agent ac3:53730:reviewer

# 3. 创建项目（all = 同时具备 coding + crawler 能力）
cowork project create --name demo --scenario all

# 4. 经 SSH 把 runtime 装到每台 AC 并拉起 coworkd
cowork bootstrap

# 5. 丢任务，三台机器只通过 Git 协作
cowork task add --scenario coding --type plan --title "hello" \
  --path workspace/hello.txt --content "hello cowork"
cowork task add --scenario crawler --type enqueue --title "example.com" \
  --url https://example.com --allow-host example.com
```

本地配置写在 `~/.config/cowork/config.json` 或仓库内 `cowork.local.json`（已 gitignore）。

## 协议

见 [PROTOCOL.md](PROTOCOL.md)。核心是原子认领：先 commit `claims/TASK-xxx.json` 再干活，push 冲突即没抢到。

## 开发

```bash
pytest -q
```

带三台真实 AC 的集成测试：

```bash
export COWORK_SSH_PASSWORD='...'
pytest -q -m integration
```
