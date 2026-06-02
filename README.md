# E2B Code Runner - AstrBot 插件 ☁️

`astrbot_plugin_e2b_code` 是一款基于 [E2B](https://e2b.dev/) 安全云端沙箱的云端代码运行指令插件（默认运行 Python 代码）。该插件支持群聊或私聊中通过显式指令运行代码，自动捕获标准输出（Stdout）、标准错误（Stderr）、返回结果（Result），并且支持将绘图结果（如 Matplotlib 等）自动提取并发回聊天中。沙箱内置对 Python, JavaScript, TypeScript, R, Java, Bash 等环境的支持。

100% 隔离的云端沙箱环境，绝不影响 AstrBot 宿主机的安全与稳定！

---

## ✨ 核心特性

- 🔒 **安全隔离**：每次执行均在 E2B 云端专属 Python 沙箱（AsyncSandbox）中运行，物理隔离宿主机，防止任何恶意脚本破坏。
- 📊 **图表自动提取**：编写绘图代码（例如使用 `matplotlib.pyplot.show()`），插件会自动捕获生成的 PNG/JPEG 图片并发送至群聊。
- 🖨️ **多维输出捕获**：标准输出（Stdout）、错误栈（Stderr）、以及最后的表达式求值结果都会被优雅地格式化输出。
- ⚙️ **可视化后台配置**：支持在 AstrBot WebUI 面板中直接管理 E2B API Key、设置执行超时时间、控制仅管理员可用以及选择默认沙箱模板。
- 💬 **无冲突指令交互**：采用 `/code` 等显式指令触发，避免在群聊日常聊天对话时误触发机器人干扰。

---

## 🛠️ 后台配置项

在 AstrBot 管理后台 -> 插件设置中，您可以调整以下参数：

| 配置键 | 说明 | 默认值 |
| :--- | :--- | :--- |
| `e2b_api_key` | 您的 E2B 平台 API Key（建议在 [E2B Dashboard](https://e2b.dev/) 免费获取） | `(留空)` |
| `timeout_seconds` | 单次代码执行的最大超时时间（单位：秒） | `30` |
| `admin_only` | 是否限制只有 AstrBot 管理员才可以使用代码运行指令 | `false` |
| `default_template` | 自定义 E2B 沙箱模板 ID（留空则默认使用 Python 基础镜像） | `""` |

---

## 🚀 聊天指令说明

### 1. 运行 Python 代码：`/code`

支持单行及多行 Markdown 代码块格式。

#### 单行示例：
```text
/code print("Hello, AstrBot!")
```

#### 多行代码块示例：
```text
/code
def fib(n):
    return n if n <= 1 else fib(n-1) + fib(n-2)

print([fib(i) for i in range(10)])
```

#### 科学计算与绘图示例：
```text
/code
import matplotlib.pyplot as plt
import numpy as np

x = np.linspace(0, 10, 100)
plt.plot(x, np.sin(x))
plt.title("Sine Wave")
plt.show()
```
*(插件将自动捕获图表并以图片消息形式发回)*

### 2. 重置会话上下文：`/code_reset`

清除当前会话所缓存的云端沙箱环境，重置所有变量、导入的模块等上下文记忆状态。

### 3. 查看帮助：`/code_help`

显示插件的使用指南和示例。

---

## 📦 安装与依赖说明

### 自动安装（推荐）
本插件已在 [requirements.txt](file:///C:/Users/Rat/data/plugins/astrbot_plugin_e2b_code/requirements.txt) 中声明了依赖包 `e2b-code-interpreter`。
- 如果您是通过 AstrBot WebUI 插件市场一键安装的，平台会**自动为您安装**相关依赖。
- 如果您是手动安装，AstrBot 在启动并加载插件时也会尝试自动安装该依赖。

### 手动安装（备用）
如果在启动时提示缺少依赖（如 `ModuleNotFoundError`），请在您的 AstrBot 运行环境中手动执行安装：
```bash
pip install e2b-code-interpreter>=2.2.2,<3.0.0
```

### 安装步骤
1. 进入您的 AstrBot 目录 `data/plugins/`。
2. 克隆本仓库：
   ```bash
   git clone https://github.com/Rat0323/astrbot_plugin_e2b_code.git
   ```
3. 重启 AstrBot 即可自动加载并识别。

## 📄 许可证

本项目基于 [MIT](LICENSE) 许可证开源。
