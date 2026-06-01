import asyncio
import base64
import os
import re
import tempfile
import traceback
from typing import Dict, Optional

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter, MessageChain
from astrbot.api.message_components import Plain, Image
from astrbot.api.star import Context, Star, register
from astrbot.core.config.astrbot_config import AstrBotConfig

from ._version import __version__, __plugin_name__, __author__, __plugin_desc__

try:
    from e2b_code_interpreter import AsyncSandbox
except ImportError:
    try:
        from e2b import AsyncSandbox
    except ImportError:
        AsyncSandbox = None


@register(__plugin_name__, __author__, __plugin_desc__, __version__)
class E2BCodePlugin(Star):
    """E2B 云端代码运行器插件主类"""

    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        self.config = config or {}

        # 加载配置
        self.e2b_api_key = ""
        self.timeout_seconds = 30
        self.admin_only = False
        self.default_template = ""

        if config:
            self.e2b_api_key = config.get("e2b_api_key", "").strip()
            self.timeout_seconds = config.get("timeout_seconds", 30)
            self.admin_only = config.get("admin_only", False)
            self.default_template = config.get("default_template", "").strip()

        logger.info("E2B 云端代码运行指令插件已加载")

    def _is_admin(self, event: AstrMessageEvent) -> bool:
        """检查用户是否为管理员"""
        return event.is_admin()

    def _parse_code(self, text: str) -> str:
        """解析 code 消息，支持单行和多行输入

        格式:
        /code print("Hello")
        或
        /code
        print("Hello")
        """
        # 移除 MSG_ID 标识
        text = re.sub(r'\s*\[MSG_ID:[^\]]+\]$', '', text)

        lines = text.split('\n')
        if not lines:
            return ""

        first_line = lines[0].strip()
        cmd_pattern = re.compile(r'^/?code\s*(.*)$', re.IGNORECASE)
        match = cmd_pattern.match(first_line)
        if match:
            first_line_rest = match.group(1).strip()
            if first_line_rest:
                lines[0] = first_line_rest
            else:
                lines = lines[1:]

        # 去除 markdown 的代码块包裹
        parsed_text = '\n'.join(lines).strip()
        match_block = re.search(r"```(?:python)?\s*(.*?)```", parsed_text, re.DOTALL | re.IGNORECASE)
        if match_block:
            return match_block.group(1).strip()
        return parsed_text

    def _stringify_output(self, value):
        if value is None:
            return ""
        for attr in ("line", "message", "text", "name", "value"):
            attr_value = getattr(value, attr, None)
            if attr_value not in (None, ""):
                return str(attr_value)
        return str(value)

    async def _send_image(self, event: AstrMessageEvent, data: bytes, ext: str):
        """异步发送绘图图片"""
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp_file:
                tmp_file.write(data)
                tmp_path = tmp_file.name
            await event.send(MessageChain([Image.fromFileSystem(tmp_path)]))
            logger.info("[E2B Code] Image sent successfully.")
        except Exception as exc:
            logger.error(f"[E2B Code] Failed to send image: {exc}")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    @filter.command("code")
    async def cmd_code(self, event: AstrMessageEvent):
        """code 命令 - 在云端运行 Python 代码"""
        # 1. 检查权限
        if self.admin_only and not self._is_admin(event):
            await event.send(MessageChain([Plain("❌ 只有管理员可以使用此命令")]))
            return

        # 2. 获取 API Key
        api_key = self.config.get("e2b_api_key", "").strip() or os.environ.get("E2B_API_KEY", "").strip()
        if not api_key:
            await event.send(MessageChain([Plain("❌ 未检测到 E2B API Key。请前往 WebUI 插件设置页或配置文件中配置 e2b_api_key。")]))
            return

        # 3. 检查依赖
        if AsyncSandbox is None:
            await event.send(MessageChain([Plain("❌ 运行环境缺少 e2b-code-interpreter 依赖。")]))
            return

        # 4. 解析代码
        code = self._parse_code(event.message_str)
        if not code:
            await event.send(MessageChain([Plain("❌ 未检测到有效代码。格式: /code [Python代码]")]))
            return

        # 5. 开始在 E2B 中运行
        try:
            template = self.config.get("default_template", "").strip()
            sandbox_kwargs = {"api_key": api_key}
            if template:
                sandbox_kwargs["template"] = template

            stdout_list = []
            stderr_list = []
            results_list = []

            # 启动云端沙箱运行
            async with await AsyncSandbox.create(**sandbox_kwargs) as sandbox:
                execution = await asyncio.wait_for(
                    sandbox.run_code(
                        code,
                        on_stdout=lambda msg: stdout_list.append(self._stringify_output(msg)),
                        on_stderr=lambda msg: stderr_list.append(self._stringify_output(msg)),
                        on_result=lambda res: results_list.append(res),
                        timeout=self.timeout_seconds
                    ),
                    timeout=self.timeout_seconds + 5
                )

                stdout = "".join(stdout_list).strip()
                stderr = "".join(stderr_list).strip()

                # 从 logs 属性做双重保险抓取
                if hasattr(execution, "logs"):
                    if not stdout and getattr(execution.logs, "stdout", None):
                        stdout = "".join(execution.logs.stdout).strip()
                    if not stderr and getattr(execution.logs, "stderr", None):
                        stderr = "".join(execution.logs.stderr).strip()

                results = list(getattr(execution, "results", []) or [])
                if not results and results_list:
                    results = results_list

                # 构建回显文本
                response_parts = []
                if stdout:
                    response_parts.append(f"📤 标准输出:\n```\n{stdout}\n```")
                if stderr:
                    response_parts.append(f"⚠️ 标准错误:\n```\n{stderr}\n```")

                # 返回值提取
                text_result = ""
                if hasattr(execution, "text") and execution.text:
                    text_result = str(execution.text).strip()
                elif results:
                    for res in reversed(results):
                        if hasattr(res, "text") and res.text:
                            text_result = str(res.text).strip()
                            break

                if text_result and text_result != "None":
                    response_parts.append(f"📦 返回结果:\n```\n{text_result}\n```")

                if not response_parts:
                    response_parts.append("✅ 执行成功，无任何终端输出。")

                # 回传执行文本结果
                await event.send(MessageChain([Plain("\n\n".join(response_parts))]))

                # 自动提取绘制的图片并回传
                for res in results:
                    img_data = None
                    img_ext = ".png"
                    if hasattr(res, "png") and res.png:
                        img_data = res.png
                        img_ext = ".png"
                    elif hasattr(res, "jpeg") and res.jpeg:
                        img_data = res.jpeg
                        img_ext = ".jpg"
                    elif hasattr(res, "svg") and res.svg:
                        img_data = base64.b64encode(str(res.svg).encode("utf-8")).decode("utf-8")
                        img_ext = ".svg"
                    elif hasattr(res, "formats"):
                        formats = res.formats() if callable(res.formats) else res.formats
                        if isinstance(formats, dict):
                            if formats.get("png"):
                                img_data = formats["png"]
                                img_ext = ".png"
                            elif formats.get("jpeg"):
                                img_data = formats["jpeg"]
                                img_ext = ".jpg"

                    if img_data:
                        try:
                            img_bytes = base64.b64decode(img_data)
                            await self._send_image(event, img_bytes, img_ext)
                        except Exception as e:
                            logger.error(f"[E2B Code] Image decode/send error: {e}")

        except asyncio.TimeoutError:
            await event.send(MessageChain([Plain(f"❌ 执行超时，限制最长运行 {self.timeout_seconds} 秒。")]))
        except Exception as e:
            logger.error(f"[E2B Code] Exception details: {traceback.format_exc()}")
            await event.send(MessageChain([Plain(f"❌ 执行异常:\n{e}")]))

    @filter.command("ecode")
    async def cmd_ecode(self, event: AstrMessageEvent):
        """ecode 命令 - 使用帮助"""
        help_msg = """☁️ E2B 云端代码运行器 (v1.0)使用说明

【执行代码】
格式:
/code [Python代码]

示例:
/code print("Hello from E2B!")

【绘图示例】
/code
import matplotlib.pyplot as plt
import numpy as np
x = np.linspace(0, 10, 100)
plt.plot(x, np.sin(x))
plt.show()

【特点】
1. 100% 云端沙箱隔离，绝不影响宿主机安全！
2. 自动捕获绘图结果（Matplotlib/Seaborn 等）并以图片形式发送回群聊。
3. 支持常见的科学计算与联网操作。
"""
        await event.send(MessageChain([Plain(help_msg)]))

    @filter.command("code_help")
    async def cmd_code_help(self, event: AstrMessageEvent):
        """code_help 命令 - 使用帮助"""
        await self.cmd_ecode(event)
