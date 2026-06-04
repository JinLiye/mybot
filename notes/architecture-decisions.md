# mybot 架构取舍

这份笔记专门记录一个问题：参考 `nanobot` 时，我们到底取什么，舍什么。

## 保留

- 小核心，大扩展边缘
- 显式的 turn 生命周期
- provider 抽象
- tool registry
- session 持久化
- channel 与 agent 解耦

## 简化

- 先只支持一个 provider
- 先只支持一个 channel
- 先只支持少量工具
- 先不做复杂 memory consolidation
- 先不做 WebUI
- 先不做 MCP / subagent

## 暂不引入

- 多层 fallback provider
- 丰富 runtime events
- 各平台特化展示逻辑
- 大规模配置系统

## 当前判断

`nanobot` 最有价值的不是“功能全集”，而是它的分层方式。

所以 `mybot` 第一阶段应该复制的是：

- 模块边界
- 数据流
- 抽象层次

而不是直接复制全部功能面。
