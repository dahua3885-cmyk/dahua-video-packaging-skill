---
name: dahua-video-packaging
description: 'Unified Dahua video-packaging workflow for existing Chinese talking-head MP4s. Use whenever the user says 做包装、用剪辑包装 Skill、完整做一下、人物不要缩小、人物缩到右下角、小窗口包装、Skill／网站／软件／工作流演示、网页全屏人物放角落、同一条视频展示多种包装, or asks to revise an already-packaged video. Automatically choose exactly one mode: fullframe for the default full-size speaker treatment, small-window for information-card-led layouts with a corner speaker, or evidence-demo when real interfaces, recordings, reports, products, or packaged examples are the main visual evidence.'
---

# 大华统一视频包装

只保留一个用户入口。先判断内容证据和人物构图，再锁定一个模式；不得在同一版里临时混用三套母版规则。默认使用 `dahua-portable-v1@1.0.0` 严格视觉配置，换电脑、换用户和换 Agent 都不得自行改变色系、字体、构图令牌或动效语言。

## 可复现开工门

首次在一台电脑使用时先运行：

```powershell
python scripts/doctor.py
npm ci --prefix assets/runtime
```

每个新工程先建立项目隔离快照：

```powershell
python scripts/portable_project.py init <工程目录> --mode <fullframe|small-window|evidence-demo> --layout <vertical|landscape>
```

工程只能使用 `.dahua-portable/` 内的字体、CSS、动效令牌和布局合同。禁止从旧工程、系统字体目录、用户主目录或 npm 全局缓存借用同名资源。`portable_project.json` 不得写用户名、邮箱、密钥或共享状态。

## 模式路由

按以下优先级选择，命中后停止：

1. `evidence-demo`：真实网页、软件、工作流、报告、录屏、产品或旧成片是主要视觉证据；或同一条横屏视频需要展示多种包装方案。即使人物在右下角，也优先此模式。
2. `small-window`：没有连续真实界面作为主画面，但用户明确要求人物缩到角落、上方或左侧使用大信息卡。
3. `fullframe`：默认模式。人物保持原有主体尺寸，包装只做辅助，不长期遮挡或缩小人物。

偶尔插入一两张截图，不等于 `evidence-demo`；只有真实证据连续承担主要叙事时才升级。

## 加载规则

每次都完整读取 [共享核心规则](references/shared-core.md)，然后只读取一个模式文件：

- `fullframe`：[全画幅模式](references/mode-fullframe.md)
- `small-window`：[小窗口模式](references/mode-small-window.md)
- `evidence-demo`：[真实界面演示模式](references/mode-evidence-demo.md)

不要同时加载另外两个模式的详细规则，以免版式、字幕区和封面规则互相覆盖。

实际创建、编辑、动画或渲染视频时，还必须先使用 `hyperframes-read-first`。本 Skill 默认只授权视觉包装，不自动授权删口误、改音频、重排口播或大幅裁剪原片；这些动作需要用户明确要求。

## 开工前锁定模式

在工程根目录初始化统一合同：

```powershell
python scripts/validate_mode_contract.py init <工程目录> --mode <fullframe|small-window|evidence-demo> --source-video <原片绝对路径> --layout-mode <vertical|landscape>
```

返修已包装视频时再加：

```powershell
--baseline-video <上一版成片绝对路径>
```

完成需求解析后填写 `packaging_mode.json` 的 `authorizedScope`、`frozenLayers`，确认无误后把 `locked` 设为 `true`。渲染前执行：

```powershell
python scripts/validate_mode_contract.py validate <工程目录> --mode <当前模式>
```

合同不通过，不得正式渲染。

渲染前还必须运行：

```powershell
python scripts/portable_project.py validate <工程目录>
python scripts/validate_portable_visuals.py <工程目录>
python scripts/golden_regression.py verify
```

调用 HyperFrames 时只使用 `assets/runtime/package-lock.json` 锁定的版本，不使用 PATH、全局安装或 npm 缓存中的“最新版”。

## 模式专属质量门

- `fullframe`：执行 `scripts/validate_package.py`，并遵守 V10 首稿与增量返修合同。
- `small-window`：执行 `scripts/validate_first_pass_gate.py --workflow small-window`。
- `evidence-demo`：先执行 `scripts/fixed_layout_contract.py`，再执行 `scripts/validate_first_pass_gate.py --workflow evidence-demo`。

## 统一硬规则

- 原片、转写、用户给定标题、参考视频和真实素材是事实源；不凭印象编造画面或文案。
- 先冻结用户未授权变化的层：音频、剪切、字幕、人物位置、封面、卡片、素材、调色分别记录。
- 视觉必须跟随口播语义建立；并列项按口播逐项出现，不能提前把整页答案铺满。
- 严格配置只允许 `assets/portable-profile.json` 中登记的颜色、字体、缓动和动效家族；禁止弹跳、回弹、弹簧、粒子、彩纸、抖动、呼吸缩放、色相旋转、无限循环和无语义漂移。
- 新颜色、新字体、新动效家族或固定坐标变化不能直接加入默认配置。只有用户明确要求改变视觉系统时，创建新的 profile ID 或提升版本，并保留旧版本供既有工程复现。
- 涉及网站、Skill、软件、工作流、账号、报告或案例成果时，优先使用真实截图、录屏、文件或旧成片，示意图不能冒充证据。
- 封面只是发布选帧层，不得偷走正文时间；用户指定原片前几帧时必须原样复用。
- 用户确认某一版后，后续只修改明确点名的层；不能顺手重做已确认区域。
- 发布版默认输出 2K 或用户指定分辨率，并完成全片解码、关键帧、字幕安全区和音轨一致性检查。
- 对外发布前必须执行 `python scripts/audit_open_source.py`；任何私有绝对路径、用户身份、密钥、不可再分发字体或缺失许可证都会阻断发布。

## 旧名称兼容

`dahua-fullframe-overlay-packaging`、`dahua-talking-head-packaging`、`dahua-skill-demo-video-packaging` 已合并到本 Skill。旧名称只用于识别历史工程，不再作为新的并列入口。
