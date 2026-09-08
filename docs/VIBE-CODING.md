# 客户 Vibe Coding 示例

把下面整段话贴进 **Cursor Agent**（工作区选本仓库）。不要改结构；只需换成你的主机、端口和仓库名。

密码只放环境变量或本机 `cowork.local.json`，不要写进对话里的 Git 提交。

---

## 复制即用的提示词

```text
我是无影 Computer Agent 的客户。这台笔记本已经能 SSH 上三台 Ubuntu Agent 电脑（互不相通，只能通过一个 GitHub 仓库协作）。

请按本仓库的 Cowork 协议帮我 vibe coding 跑通一条双场景流水线，我只负责看结果：

1. 用 cowork auth / project create / bootstrap 把 runtime 装到 ac1、ac2、ac3（角色 planner / builder / reviewer，并打开 crawler 能力）。
2. 丢两条任务就停手，不要替 Agent Computer 写业务代码：
   - coding：plan 一份 hello，最终文件 workspace/hello.txt，内容 hello cowork
   - crawler：enqueue https://example.com ，allow_hosts 只有 example.com
3. 在笔记本启动本地监控：cowork monitor --open
4. 我要在 http://127.0.0.1:8765/ 看到三台机各自在跑什么；任务描述要用自然语言，不要只显示品牌字段。
5. 如果有任务卡住，从监控页点「下发」或「下发全部未完成」，不要让我 SSH 进机器手改。

约束：密钥不要进 Git；browser 模式必须走那台 AC 自己的 Codex / 无影网关，这样我才能在无影控制台看到 AI 会话。
```

---

## 跑完你应该看到什么

| 位置 | 信号 |
|---|---|
| 无影控制台 | 对应 AC 出现 Codex / 浏览器会话（若任务是 browser 抓取） |
| GitHub 仓库 `.cowork/tasks/` | `plan` → `implement` → `review`，以及 `enqueue` → `fetch` → `extract` |
| `workspace/hello.txt` | `hello cowork` |
| 监控页三张卡片 | 空闲 / 已领任务 / Codex 运行中 |
| 监控页任务表 | 「任务描述」列能读懂在干什么 |

## 常见下一句（继续 vibe）

任务跑通之后，可以再贴：

```text
监控里 fetch 已完成。请再 enqueue 五个日本独立首饰官网，mode=browser，每家从商品详情子页抓 16 张产品主图，写入 pics/<brand>/，域名必须白名单。我只在监控里下发和看进度。
```

官网列表与白名单以你的业务为准；协议仓库里的演示抓取见独立仓库 [japan-jewelry-pics](https://github.com/SuncNoob/japan-jewelry-pics)。
