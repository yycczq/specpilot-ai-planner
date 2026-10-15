# 界面参考与实现说明

本项目观察公开产品的交互方式，再围绕“需求澄清与人工审阅”独立设计。参考页面只用于理解信息层级和工作流；SpecPilot 的文案、配色、组件、图标和代码均为本项目自行实现，没有复用参考产品的品牌素材、截图或源代码。

## 参考来源

1. **Linear：工作区导航与任务组织**
   [Linear Features](https://linear.app/features) · [Linear Display Options](https://linear.app/docs/display-options) · [Linear Issues](https://linear.app/docs/creating-issues)
   参考点：侧栏组织工作区入口、突出当前任务、用状态标记帮助定位。SpecPilot 将这些常见模式用于需求工作台、需求档案和人工审阅状态。

2. **Vercel v0：提示输入与模板入口**
   [v0 首页](https://v0.app/) · [v0 Quickstart](https://v0.app/docs/quickstart)
   REA 于 **2026-10-15** 对公开首页 `https://v0.app/` 做了被动页面观察。页面标题为 “v0 by Vercel - Build Full-Stack Web Apps with AI”；首屏以居中的创建提示框为主操作，提示框下方有快捷示例，继续向下是模板类别和卡片。

   观察证据来自本地 REA 6.4.0 CLI，通过隔离 Chrome 配置和 loopback CDP 连接获得：

   - 页面与无障碍树：`ev_824c41089eee54d100334319df2eb72356fbbb1d5c52091a13fee5df5f3ea808`
   - 视口截图：`ev_d9cc28a87c6b6db44c7a93ca93cf7e17bffc292416ff2a3f52077a31fa3f8ffb`（SHA-256：`6bdb053706e3635aa3f752fa3136daac3a675ae7f9b82e4d3a635a6112590297`）
   - 目标来源确认：`ev_dceab1f9988cc97ad03d40e151e4bbffa2e045440239f21799dd3c1acb98ffe1`

   采集范围限定为 `https://v0.app`；环境为 Chrome 155，截图视口 2400×1310。采集了 DOM 结构、无障碍名称和一张视口截图，没有读取脚本源码、存储值、响应体或账户信息。观察对象是未登录的公开首页，不是登录后的编辑器。SpecPilot 借鉴的是“先聚焦主要输入，再给可选起点”的通用布局：把需求输入放在工作台中心，并在下方提供可点击、可继续修改的场景模板。没有复制 v0 的按钮文案、标识、模板图片或 CSS。

3. **REA：网页行为研究工具**
   [REA GitHub 项目](https://github.com/morluto/rea)
   REA 用于采集并归档以上公开页面证据。本项目只将观察到的页面结构用于设计讨论，不从参考页面提取或复用其源代码与专有素材。

## 本项目的设计决定

- 用轻量侧栏保留工作区、需求档案和协作流程入口。
- 首屏聚焦需求输入；场景模板提供开始写需求的快捷入口。
- 把生成结果拆成概览、验收标准、接口草案、测试用例和待确认问题，支持逐项查看。
- 以“AI 草案 / 待人工确认”提醒使用者复核；审阅后的改动保留版本快照。
- 所有实现使用本项目自建的 CSS、图标和文案，不包含参考产品的 logo、截图或专有视觉素材。
