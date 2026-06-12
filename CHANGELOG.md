# Changelog

## v1.0.1

- 修复会话内存泄漏（LRU + 过期清理 + 数量上限）
- 指令重构为 `/e2b` 指令组（`/e2b run`, `/e2b reset`, `/e2b help`, `/e2b plan`）
- 新增 `plan_type` 配置，手动选择免费/付费计划
- 新增 `max_code_length` 和 `max_sessions` 配置项
- 新增 `/e2b plan` 指令查看计划限制
- 更新 metadata.yaml（short_desc, astrbot_version）

## v1.0.0

- 首次发布
- 支持 E2B 云端沙箱代码执行
- 自动捕获输出结果和绘图图片
- 会话持久化（变量和模块自动保留）
