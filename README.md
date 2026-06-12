# E2B Code Runner - AstrBot 插件 ☁️

一款基于 [E2B](https://e2b.dev/) 云端沙箱的代码运行插件。在聊天中通过 `/e2b run` 指令即可执行 Python、JavaScript、TypeScript、R、Java、Bash 等多语言代码，自动捕获输出结果和绘图图片。

100% 隔离的云端沙箱，绝不影响宿主机安全。

---

## ✨ 特性

- 🔒 **安全隔离** — 代码在 E2B 云端沙箱中运行，与宿主机完全隔离
- 📊 **图表自动提取** — Matplotlib 等绘图代码自动生成图片发回聊天
- 💾 **会话持久化** — 同一会话内变量和导入的模块自动保留
- 🖨️ **多维输出** — 标准输出、错误栈、返回结果格式化输出
- 🧩 **指令组设计** — 统一 `/e2b` 前缀，不与其他插件冲突
- ⚙️ **WebUI 配置** — 在 AstrBot 管理后台直接配置所有参数

---

## 🚀 指令

| 指令 | 说明 |
|------|------|
| `/e2b run <代码>` | 执行代码（支持单行和多行） |
| `/e2b reset` | 重置沙箱，清除所有变量和状态 |
| `/e2b plan` | 查看当前计划类型和限制 |
| `/e2b help` | 显示帮助信息 |

### 示例

```
/e2b run print("Hello!")

/e2b run
import matplotlib.pyplot as plt
plt.plot([1, 2, 3])
plt.show()
```

---

## 🛠️ 配置项

在 AstrBot WebUI → 插件设置 中配置：

| 配置键 | 说明 | 默认值 |
|--------|------|--------|
| `e2b_api_key` | E2B API Key（从 [e2b.dev](https://e2b.dev/) 获取） | - |
| `plan_type` | 账户计划类型：`hobby`（免费）或 `pro`（付费） | `hobby` |
| `timeout_seconds` | 代码执行超时时间（秒） | `30` |
| `session_keepalive` | 闲置会话自动销毁时间（秒） | `300` |
| `max_sessions` | 最大并发沙箱数 | `20` |
| `max_code_length` | 单次代码最大字符数 | `10000` |
| `admin_only` | 仅管理员可用 | `false` |
| `default_template` | E2B 沙箱模板 ID（留空用默认） | `""` |

### 计划类型说明

| 计划 | 并发沙箱 | 会话时长 | 磁盘 |
|------|----------|----------|------|
| Hobby（免费） | 20 | 1 小时 | 10 GB |
| Pro（付费） | 100 | 24 小时 | 20 GB |

---

## 📦 安装

### 方式一：AstrBot WebUI 插件市场（推荐）

搜索 `astrbot_plugin_e2b_code` 一键安装。

### 方式二：手动安装

```bash
cd data/plugins/
git clone https://github.com/Rat0323/astrbot_plugin_e2b_code.git
```

重启 AstrBot 即可。

### 依赖

插件依赖 `e2b-code-interpreter`，AstrBot 会自动安装。若手动安装失败：

```bash
pip install e2b-code-interpreter>=2.2.2,<3.0.0
```

---

## 📄 更新日志

<details>
<summary>v1.0.1</summary>

- 新增 `/e2b plan` 指令，查看计划类型和资源限制
- 新增 `plan_type` 配置，选择免费/付费计划
- 新增 `max_code_length` 和 `max_sessions` 配置项
- 指令升级为 `/e2b` 指令组（`/e2b run`, `/e2b reset`, `/e2b help`, `/e2b plan`）
- 修复长时间运行后的内存泄漏
- 移除 `httpx` 依赖，插件更轻量

</details>

<details>
<summary>v1.0.0</summary>

- 首次发布
- 支持 E2B 云端沙箱代码执行
- 自动捕获输出结果和绘图图片
- 会话持久化（变量和模块自动保留）

</details>

---

## 📄 许可证

[MIT](LICENSE)
