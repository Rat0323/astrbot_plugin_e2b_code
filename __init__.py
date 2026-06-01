"""
E2B Code Runner 插件
基于 E2B 云端沙箱的 Python 代码执行指令插件
"""

from ._version import __version__, __plugin_name__, __plugin_desc__, __author__
from .main import E2BCodePlugin

__all__ = ["E2BCodePlugin", "__version__", "__plugin_name__", "__plugin_desc__", "__author__"]
