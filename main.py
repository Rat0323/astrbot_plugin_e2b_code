import asyncio
import base64
import os
import re
import tempfile
import time
import traceback
from collections import OrderedDict
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
        self.plan_type = "hobby"
        self.timeout_seconds = 30
        self.admin_only = False
        self.default_template = ""
        self.session_keepalive = 300
        self.max_code_length = 10000
        self.max_sessions = 20

        if config:
            self.e2b_api_key = config.get("e2b_api_key", "").strip()
            self.plan_type = config.get("plan_type", "hobby").strip().lower()
            self.timeout_seconds = config.get("timeout_seconds", 30)
            self.admin_only = config.get("admin_only", False)
            self.default_template = config.get("default_template", "").strip()
            self.session_keepalive = config.get("session_keepalive", 300)
            self.max_code_length = config.get("max_code_length", 10000)
            self.max_sessions = config.get("max_sessions", 20)

        # 会话缓存字典（LRU）：{ session_id: AsyncSandbox }
        self.sessions: OrderedDict[str, AsyncSandbox] = OrderedDict()
        self._session_times: Dict[str, float] = {}

        logger.info("E2B 云端代码运行指令插件已加载 (启用持久会话上下文模式)")

    def _is_admin(self, event: AstrMessageEvent) -> bool:
        """检查用户是否为管理员"""
        return event.is_admin()

    def _parse_code(self, text: str) -> tuple[str, Optional[str]]:
        """解析 code 消息，支持单行和多行输入并自动识别语言

        返回 (code, language)
        """
        # 移除 MSG_ID 标识
        text = re.sub(r'\s*\[MSG_ID:[^\]]+\]$', '', text)

        lines = text.split('\n')
        if not lines:
            return "", None

        first_line = lines[0].strip()
        cmd_pattern = re.compile(r'^/?e2b\s+run\s*(.*)$', re.IGNORECASE)
        match = cmd_pattern.match(first_line)
        if match:
            first_line_rest = match.group(1).strip()
            if first_line_rest:
                lines[0] = first_line_rest
            else:
                lines = lines[1:]

        parsed_text = '\n'.join(lines).strip()
        
        # 匹配 markdown 代码块，如 ```python ... ``` 或 ```javascript ... ```
        match_block = re.search(r"```([a-zA-Z0-9+#-]+)?\s*(.*?)```", parsed_text, re.DOTALL | re.IGNORECASE)
        if match_block:
            lang_tag = (match_block.group(1) or "").strip().lower()
            code_content = match_block.group(2).strip()
            
            # 语言标记规范化
            lang_map = {
                "py": "python",
                "python": "python",
                "python3": "python",
                "js": "javascript",
                "javascript": "javascript",
                "node": "javascript",
                "ts": "typescript",
                "typescript": "typescript",
                "r": "r",
                "java": "java",
                "bash": "bash",
                "sh": "bash",
                "shell": "bash",
            }
            language = lang_map.get(lang_tag, lang_tag or None)
            return code_content, language
            
        return parsed_text, None

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

    async def _cleanup_sessions(self):
        """清理过期会话和超出数量限制的会话"""
        now = time.time()
        expired = [sid for sid, t in self._session_times.items() if now - t > self.session_keepalive]
        for sid in expired:
            sandbox = self.sessions.pop(sid, None)
            self._session_times.pop(sid, None)
            if sandbox:
                try:
                    await sandbox.kill()
                    logger.info(f"[E2B Code] 已清理过期会话: {sid}")
                except Exception:
                    pass

        while len(self.sessions) > self.max_sessions:
            oldest_sid, sandbox = self.sessions.popitem(last=False)
            self._session_times.pop(oldest_sid, None)
            if sandbox:
                try:
                    await sandbox.kill()
                    logger.info(f"[E2B Code] 已清理超限会话: {oldest_sid}")
                except Exception:
                    pass

    async def _get_sandbox(self, session_id: str, api_key: str) -> AsyncSandbox:
        """获取或新建会话对应的 E2B 持久沙箱实例"""
        sandbox = self.sessions.get(session_id)
        if sandbox is not None:
            self._session_times[session_id] = time.time()
            self.sessions.move_to_end(session_id)
            return sandbox

        await self._cleanup_sessions()

        template = self.config.get("default_template", "").strip()
        sandbox_kwargs = {
            "api_key": api_key,
            "timeout": self.session_keepalive
        }
        if template:
            sandbox_kwargs["template"] = template

        logger.info(f"[E2B Code] 创建新的持久沙箱会话: {session_id} (挂机存活时间: {self.session_keepalive}秒)")
        sandbox = await AsyncSandbox.create(**sandbox_kwargs)
        self.sessions[session_id] = sandbox
        self._session_times[session_id] = time.time()
        return sandbox

    @filter.command_group("e2b")
    def e2b_group(self):
        pass

    @e2b_group.command("run")
    async def cmd_run(self, event: AstrMessageEvent):
        """e2b run - 在云端运行代码"""
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

        # 4. 检测 KEY 计划类型（仅首次）
        if self.plan_type is None:
            await self._detect_plan_type(api_key)
            self._apply_plan_defaults()

        # 4. 解析代码与识别语言
        code, language = self._parse_code(event.message_str)
        if not code:
            await event.send(MessageChain([Plain("❌ 未检测到有效代码。格式: /e2b run [代码内容]")]))
            return

        # 5. 检查代码长度
        if len(code) > self.max_code_length:
            await event.send(MessageChain([Plain(f"❌ 代码过长，最大允许 {self.max_code_length} 个字符，当前 {len(code)} 个字符。")]))
            return

        # 6. 开始在 E2B 中运行
        try:
            stdout_list = []
            stderr_list = []
            results_list = []
            session_id = event.get_session_id()

            # 获取沙箱并执行
            sandbox = None
            try:
                sandbox = await self._get_sandbox(session_id, api_key)
                run_kwargs = {
                    "code": code,
                    "on_stdout": lambda msg: stdout_list.append(self._stringify_output(msg)),
                    "on_stderr": lambda msg: stderr_list.append(self._stringify_output(msg)),
                    "on_result": lambda res: results_list.append(res),
                    "timeout": self.timeout_seconds
                }
                if language:
                    run_kwargs["language"] = language

                execution = await asyncio.wait_for(
                    sandbox.run_code(**run_kwargs),
                    timeout=self.timeout_seconds + 5
                )
            except Exception as e:
                # 缓存沙箱断开连接/过期时，尝试自动重连并重试一次
                logger.warning(f"[E2B Code] 缓存沙箱执行报错 ({e})。正在重置并创建新沙箱重新运行...")
                self.sessions.pop(session_id, None)
                self._session_times.pop(session_id, None)
                if sandbox:
                    try:
                        await sandbox.kill()
                    except Exception:
                        pass
                
                # 重建并重新运行
                sandbox = await self._get_sandbox(session_id, api_key)
                run_kwargs = {
                    "code": code,
                    "on_stdout": lambda msg: stdout_list.append(self._stringify_output(msg)),
                    "on_stderr": lambda msg: stderr_list.append(self._stringify_output(msg)),
                    "on_result": lambda res: results_list.append(res),
                    "timeout": self.timeout_seconds
                }
                if language:
                    run_kwargs["language"] = language

                execution = await asyncio.wait_for(
                    sandbox.run_code(**run_kwargs),
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

            # 运行报错提取
            if hasattr(execution, "error") and execution.error:
                err = execution.error
                err_name = getattr(err, "name", "RuntimeError")
                err_traceback = getattr(err, "traceback", "")
                err_value = getattr(err, "value", "")
                response_parts.append(f"❌ 运行错误: {err_name}\n```\n{err_traceback or err_value}\n```")

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

    @e2b_group.command("reset")
    async def cmd_reset(self, event: AstrMessageEvent):
        """e2b reset - 重置当前会话的云端沙箱环境（清除上下文状态）"""
        session_id = event.get_session_id()
        sandbox = self.sessions.pop(session_id, None)
        self._session_times.pop(session_id, None)
        if sandbox:
            try:
                await sandbox.kill()
                await event.send(MessageChain([Plain("🔄 已成功重置当前会话的云端沙箱环境。")]))
            except Exception as e:
                await event.send(MessageChain([Plain(f"⚠️ 关闭沙箱时出现异常: {e}，会话已重置。")]))
        else:
            await event.send(MessageChain([Plain("ℹ️ 当前没有活动的云端沙箱会话。")]))

    @e2b_group.command("help")
    async def cmd_help(self, event: AstrMessageEvent):
        """e2b help - 使用说明"""
        help_msg = """☁️ E2B 云端代码运行器使用说明

【执行代码】
格式:
/e2b run [代码内容]

示例:
/e2b run print("Hello from E2B!")

【上下文连贯】
本插件会自动保留您的执行上下文状态（变量、导入的模块等）。
如需重置并清除上下文状态，请发送：
/e2b reset

【绘图示例】
/e2b run
import matplotlib.pyplot as plt
plt.plot([1, 2, 3])
plt.show()

【查看计划】
/e2b plan — 查看当前 E2B 计划类型和限制。

【支持语言】
沙箱环境默认以 Python 语言运行代码。云端沙箱亦内置了 JavaScript, TypeScript, R, Java, Bash 等运行环境。"""
        await event.send(MessageChain([Plain(help_msg)]))

    @e2b_group.command("plan")
    async def cmd_plan(self, event: AstrMessageEvent):
        """e2b plan - 查看当前 E2B 计划类型和限制"""
        plan_info = {
            "hobby": {
                "name": "免费计划 (Hobby)",
                "concurrent": 20,
                "session_length": "1 小时",
                "disk": "10 GB",
            },
            "pro": {
                "name": "付费计划 (Pro)",
                "concurrent": 100,
                "session_length": "24 小时",
                "disk": "20 GB",
            },
        }
        info = plan_info.get(self.plan_type, plan_info["hobby"])

        msg = f"""📋 E2B 计划信息

计划类型: {info['name']}
最大并发沙箱: {info['concurrent']}
最大会话时长: {info['session_length']}
沙箱磁盘: {info['disk']}

当前插件配置:
并发上限: {self.max_sessions}
会话保持: {self.session_keepalive} 秒
代码长度限制: {self.max_code_length} 字符

💡 计划类型可在插件设置中修改 (plan_type)"""
        await event.send(MessageChain([Plain(msg)]))
