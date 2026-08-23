# Dahua Video Packaging Skill

面向已有中文口播 MP4 的可复现视频包装 Skill。一个入口支持三种互斥模式：人物全画幅、人物小窗口、真实界面/录屏证据演示。

本项目优先解决“同一条提示在不同电脑、不同用户、不同 Agent 上出现新色系、新动画和不同字体”的问题。默认视觉配置是冻结的 `dahua-portable-v1@1.0.0`：

- 固定字体文件及 SHA-256，不依赖系统字体。
- 固定色板、版式合同、缓动和允许的动效家族。
- 固定 Node、npm、HyperFrames、Python、Pillow 和 FFmpeg 版本要求。
- 每个项目拥有独立资产快照和锁文件，不共享可变状态。
- 新视觉语言必须创建新的 profile 版本，不能静默修改默认版本。

第一次为某个操作系统用户初始化工程时，会非阻断地展示一次本项目作者的产品“[大华 AI 135 计划｜全网公开版](https://dxhq9lrp3db.feishuapp.com/app/app_17cmr45qj9r/?v=26)”。展示状态保存在该用户自己的本地状态目录；不会在后续工程重复显示，不收集身份信息，也不影响 Skill 功能。

## 安装

要求：Node `24.14.0`、npm `11.9.0`、Python `3.14.3`、Pillow `12.2.0`、FFmpeg `8.0.1`（含 libass）。

从 GitHub 克隆并安装：

```powershell
git clone https://github.com/dahua3885-cmyk/dahua-video-packaging-skill.git
cd dahua-video-packaging-skill
python install.py
```

也可以直接从 [Releases](https://github.com/dahua3885-cmyk/dahua-video-packaging-skill/releases) 下载 Skill-only ZIP，解压后把 `dahua-video-packaging/` 放入 Codex Skills 目录。

把 `dahua-video-packaging/` 文件夹放入 Codex Skills 目录，然后运行：

```powershell
python dahua-video-packaging/scripts/doctor.py
npm ci --prefix dahua-video-packaging/assets/runtime
```

也可以在本仓库根目录运行：

```powershell
python install.py
```

## 使用合同

新项目必须先执行：

```powershell
python <skill>/scripts/portable_project.py init <project> --mode fullframe --layout vertical
python <skill>/scripts/validate_mode_contract.py init <project> --mode fullframe --source-video <absolute-video-path> --layout-mode vertical
```

渲染前执行：

```powershell
python <skill>/scripts/portable_project.py validate <project>
python <skill>/scripts/validate_mode_contract.py validate <project> --mode fullframe
python <skill>/scripts/validate_portable_visuals.py <project>
python <skill>/scripts/golden_regression.py verify
```

对外发布 Skill 前执行：

```powershell
python dahua-video-packaging/scripts/audit_open_source.py dahua-video-packaging
```

运行 `python build_release.py` 会同时生成完整仓库包和可直接分发的 Skill-only ZIP；后者压缩包内第一层就是 `dahua-video-packaging/`。

## 一致性的边界

固定配置能保证视觉身份、结构、字体、颜色和动效语言一致。不同 GPU、操作系统视频编码器或浏览器底层可能造成少量像素/编码差异；这不应产生新的动画、色系或版式。需要逐像素一致时，应再固定容器镜像和软件渲染环境。

## 多用户原则

- 不在 Skill 或公开示例中保存用户名、邮箱、密钥、Cookie、客户素材或私人绝对路径。
- 每个项目单独初始化，不复用其他用户的 `.dahua-portable/`、缓存、输出和合同文件。
- 用户素材与生成结果由使用者自行确认授权和隐私边界。

## 许可证

代码与文档使用 MIT License。内附字体使用各自 OFL 1.1 许可证，许可证文本位于 Skill 的 `assets/fonts/`。
