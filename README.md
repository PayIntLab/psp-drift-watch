# PSP Drift Watch（支付平台变更漂移监测）

把「PSP Change Drift Watch」从手动内容升级成可运行的监测工具：定时抓取
Stripe / PayPal / Adyen 的 changelog、迁移指南、SDK 发布说明，对比上一次快照，
有变化就生成一份漂移报告，并可选触发支付 QA 回归测试。

## 为什么做这个

6 类支付集成真痛点的共同根源是「平台在变，你的系统没跟上」：

- 平台单方面改字段格式/长度 → 老代码解析失败或静默丢单
- 字段默认值变化 → 不报错，只是突然没值
- SDK 大版本 + pinned API version → 升级动作本身掩盖风险
- EOL / 迁移 → 迁移窗口里「返回 200 但业务没触发」的静默失败

本工具把「盯这些源」自动化：先盯住变化，再按三条信号判断要不要动手。

## 目录结构

```
psp-drift-watch/
├── sources.json           # 监测源清单（平台 / 类型 / URL / 信号）
├── fetch.py               # 抓取所有源 → snapshot.json
├── diff.py                # 对比 baseline.json vs snapshot.json → drift-report.md
├── baseline.json          # 上次快照（首次运行后由 snapshot.json 复制而来）
├── drift.sh               # 一键：fetch → diff →（可选）回归
└── hooks/trigger_regression.sh   # 回归触发（指向 payment-qa-framework）
```

## 用法

```bash
# 第一次：建立基线
python3 fetch.py          # 生成 snapshot.json
cp snapshot.json baseline.json   # 固化当前状态为基线

# 之后每次监测
./drift.sh                 # 抓取 + 对比 + 出报告
./drift.sh --regress       # 额外触发 payment-qa-framework 回归
```

报告输出到 `drift-report.md`，列出：新增/变化/失败/未变化的源，以及升级前回归清单。

## 三条判断信号

| 信号 | 含义 | 例子 |
|---|---|---|
| `eol` | EOL / 迁移 | PayPal IPN → Webhooks |
| `field_default` | 字段默认值变化 | Stripe `billed_until` 不再默认返回 |
| `sdk_version` | SDK 大版本 / pinned API | stripe-node 21 webhook 解析方法抛错 |
| `api_version` | API 版本变更 | Adyen Checkout v72 校验变严 |

## 回归触发

`hooks/trigger_regression.sh` 读环境变量 `FRAMEWORK_DIR`（指向
`payment-qa-framework` 仓库），存在 `pom.xml` 时执行 `mvn -B test`；未配置则打印
回归清单提醒。

## 扩展监测源

在 `sources.json` 里加一条即可。`kind` 决定怎么抓稳定信号：

- `github_commits`：看某个 GitHub 仓库最新 commit（`repo`），适合 OpenAPI spec 仓库。
- `github_releases`：看某个仓库最新 release 的 tag（`repo`），适合 SDK 版本。
- `devto_api`：看某篇 dev.to 文章的编辑时间（`username` + `slug`）。
- `http`：普通 HTTP（`url`），优先用 ETag，退化为内容哈希（只适合静态页/原始 .md）。

每条都要 `id`、`platform`、`name`、`kind`、`signal`。用稳定信号做指纹，
任何真实变化（新 commit / 新 release / 编辑）都会在下次 diff 里被标记出来。
