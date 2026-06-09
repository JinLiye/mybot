# mybot

这个目录用于基于 `nanobot` 的设计思想，逐步实现一个我们自己的 bot。

当前目标不是立刻开写全部代码，而是先把“哪些设计值得继承，哪些复杂度可以先不做”想清楚。

## 设计目标

`mybot` 的第一阶段目标：

- 保留清晰的 Agent 主链路
- 保留 provider / tool / channel 的边界
- 保留 session 持久化能力
- 先做最小可运行版本

不追求一开始就拥有 `nanobot` 这么多扩展面。

## 先继承什么

从 `nanobot` 里，最值得直接继承的是这几个思想：

1. 用统一的 `InboundMessage` / `OutboundMessage` 作为边界对象。
2. 用 `MessageBus` 解耦 channel 和 agent。
3. 用 `AgentLoop` 管 turn 生命周期。
4. 用 `AgentRunner` 管 LLM + tool 循环。
5. 用 `LLMProvider` 隔离不同模型实现。
6. 用 `ToolRegistry` 挂接能力，而不是写死。
7. 用 `SessionStore` 处理长期对话，而不是临时内存变量。

## 第一版不要照搬什么

`nanobot` 现在已经是一个完整项目了，其中有不少能力对 `mybot` 初版来说是过重的：

- 大量 channel 接入
- 完整 WebUI
- MCP 生态
- 子 agent 管理
- provider failover 链
- 很多运行时事件和展示细节
- 大量平台兼容性处理

如果第一版把这些也一起搬过来，复杂度会立刻失控。

## 建议的最小目录

后续我们可以按这个方向逐步搭：

```text
mybot/
  README.md
  notes/
  core/
    bus.py
    events.py
    loop.py
    runner.py
    context.py
    session.py
  providers/
    base.py
    openai.py
  tools/
    base.py
    registry.py
  channels/
    base.py
    cli.py
```

## 开发策略

建议顺序：

1. 先把 nanobot 主链路读透。
2. 从里面抽出最小骨架。
3. 再在 `mybot` 里做一个只支持单 provider、单 channel、少量工具的版本。
4. 跑通后再决定哪些高级能力值得补。

## 当前参考文档

源码学习文档在：

- [`docs/source-study/README.md`](/home/asus/nanobot/docs/source-study/README.md)
- [`docs/source-study/reading-path.md`](/home/asus/nanobot/docs/source-study/reading-path.md)
- [`docs/source-study/request-lifecycle.md`](/home/asus/nanobot/docs/source-study/request-lifecycle.md)

## 当前已实现的最小骨架

现在已经有一版可继续扩展的 Python 骨架：

- `events.py`: 统一的入站/出站消息
- `bus.py`: 最小异步消息总线
- `session.py`: JSON 持久化会话
- `context.py`: system prompt + history + runtime context
- `providers/openai_compat.py`: OpenAI-compatible provider
- `runner.py`: LLM + tool 循环
- `loop.py`: 主编排层
- `cli.py`: 最小本地命令行聊天入口

## 当前支持的模型接入

### 1. 本地 vLLM

默认就是 vLLM 配置：

```bash
export MYBOT_PROVIDER=vllm
export MYBOT_VLLM_API_BASE=http://127.0.0.1:8000/v1
export MYBOT_VLLM_API_KEY=EMPTY
export MYBOT_VLLM_MODEL=Qwen/Qwen3-8B
```

### 2. 阿里百炼

```bash
export MYBOT_PROVIDER=bailian
export MYBOT_BAILIAN_API_KEY=你的百炼API_KEY
export MYBOT_BAILIAN_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
export MYBOT_BAILIAN_MODEL=qwen-plus-latest
```

## 运行方式

在仓库根目录执行：

```bash
.venv/bin/python -m mybot.cli
```

也可以显式指定 provider：

```bash
.venv/bin/python -m mybot.cli --provider vllm
.venv/bin/python -m mybot.cli --provider bailian
```

## GitHub 维护

这个目录现在已经补了独立仓库需要的最小文件：

- `.gitignore`
- `pyproject.toml`
- `.env.example`
- `tests/`

如果你要把它当成一个单独项目维护，可以直接在这个目录里初始化 git，然后推到 GitHub。


## CLI 常用命令

```text
/help              查看命令菜单
/resume            恢复历史会话
/rename <name>     重命名当前会话
/tools             查看工具状态
/permissions       查看工具权限模式
/trace             查看最近一次 Agent Trace
/trace full        查看完整工具结果
/trace json        输出 JSON Trace
/memory            查看当前会话 memory summary
/memory refresh    手动刷新 memory summary
/memory clear      清空 memory summary
```

## Memory Summary

`mybot` 会在会话变长后自动压缩旧消息。原始历史仍保存在 session JSON 中，模型上下文使用：

```text
system prompt + memory summary + 未压缩的最近消息 + 当前用户输入
```

相关配置：

```env
MYBOT_MEMORY_SUMMARY_TRIGGER_MESSAGES=24
MYBOT_MEMORY_SUMMARY_KEEP_MESSAGES=12
MYBOT_MEMORY_SUMMARY_MAX_TOKENS=512
```

默认数据目录取决于启动位置。如果从 `/home/asus/nanobot` 启动，session、trace、memory summary 会保存在：

```text
/home/asus/nanobot/.data/sessions/*.json
```


## 当前工具能力

`mybot` 当前内置工具：

```text
list_dir       列目录
read_file      读取 UTF-8 文本文件
search_text    简单文本搜索
find_files     按 query/glob/type 查找文件
grep           结构化文本/正则搜索
apply_patch    结构化多文件编辑，支持 dry-run
shell_exec     一次性 shell 命令执行
```

写代码时建议优先使用：

```text
find_files -> read_file/grep -> apply_patch -> shell_exec 跑测试
```
