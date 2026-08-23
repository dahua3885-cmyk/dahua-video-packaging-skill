# 口播—页面—动作映射模板

制作前建立一份单一时间轴。字幕、页面、动作、故事板和验收时点均从该表派生。

## 场景表

| 字段 | 要求 |
| --- | --- |
| `sceneId` | 稳定、唯一、kebab-case |
| `presentationMode` | `evidence-demo / packaging-comparison`；全片冻结，不逐场景切换 |
| `startSec / endSec` | 绑定真实口播时间 |
| `spokenText` | 当前完整口播语义 |
| `triggerCue / triggerFrame` | 当前对象第一次被说出的字词与播放帧；证据必须从这里进入，最多提前约 `0.2s` 建立上下文 |
| `captionVerified` | `yes/no`；否定词、专有名词和数字已回听并对照页面 |
| `sceneType` | `operation / evidence / conclusion / transition` |
| `sectionBoundary` | `intro / case-start / case-body / case-end / conclusion` |
| `visualSource` | 真实页面、Markdown、软件界面、报告、数据页或明确留白 |
| `evidenceCategory` | `profile / works-grid / original-video / old-finished-video / interface / semantic-page` |
| `sampleRole` | 比较模式填写 `overview / style-01 / style-02 / style-03 / past-gallery`；标准模式填写 `none` |
| `sourceSafeRange` | 辅助录屏允许使用的起止时间；已排除 OBS 与隐私画面 |
| `whyThisVisual` | 说明该画面怎样证明或解释当前句子 |
| `shot` | `full-page / cropped-focus / static-section / operation / long-scroll` |
| `scale / x / y` | 当前页面场景的稳定构图；只允许调整页面层 |
| `speakerPosition` | 横屏固定填写 `210×352 @ (1676,690)`，不得逐场景变化 |
| `captionText` | 单行显示字幕 |
| `action` | `cut / crossfade / click / annotate / scroll / hold` |
| `actionCue` | 动作对应的口播字词和开始时间 |
| `requiredStates` | 当前语义需要展示的真实状态序列；无过程时填写 `none` |
| `highlightTarget` | 需要黄框时填写目标证据；页面已明确时填写 `none` |
| `highlightBox` | 黄框目标外扩后的 `x1,y1,x2,y2`；不得进入人物或字幕占位区 |
| `holdSec` | 画面停留时间 |
| `persistUntil` | 同一证据跨多句应持续到哪里；字幕换句不得自动重建画面 |
| `truthSource` | 页面路径、URL、截图或数据真源 |
| `frozenLayers` | 当前场景已经确认、后续不得随局部返修改动的层 |
| `checkpoints` | 要抽帧或连续播放检查的时间 |

## 滚动附加字段

```json
{
  "direction": "down",
  "contentMotion": "up",
  "startPosition": "标题或 y 坐标",
  "endPosition": "标题或 y 坐标",
  "triggerCue": "口播第一个字",
  "triggerSec": 19.54,
  "endSec": 29.20,
  "reason": "连续展示一份长文档的深度"
}
```

## 缩放分段表

| 时间段 | 页面类型 | 比例 | 目的 |
| --- | --- | --- | --- |
| 开头操作段 | 完整操作 | 按内容确定 | 看全路径和上下文 |
| 核心分析段 | 正文／图表 | 按内容确定 | 看清关键内容 |
| 结尾成果段 | 完整成果／CTA | 按内容确定 | 模块和 CTA 不被裁切 |

比例不能照抄黄金参考的 `1.35 / 1.62 / 1.45`；必须根据新页面重新测量。只复用“分段自适应”的方法。

## 映射验收

逐场景回答：

1. 删除这个页面后，当前口播是否失去证据或理解增益？
2. 页面是否准确对应当前句子，而不是上一句或下一句？
3. 当前动作是否有明确语义？
4. 页面是否已经停留到观众能看清？
5. 数据是否来自真实页面？
6. 人物和字幕是否保持固定合同，没有为了当前页面临时移动或缩放？
7. 黄框是否只定位当前句的关键证据，而不是为了让画面“更丰富”？
8. 当前画面是否越过了案例边界，提前进入案例或在总结段继续复用案例？
9. 口播描述多个状态时，`requiredStates` 是否全部由真实运动或真实状态承担？
10. 字幕中的否定词、专有名词和数字是否已经回听确认？
11. 账号、作品墙、具体案例和结果是否使用了各自对应的真实证据，而不是复用近似页面？
12. 当前证据是否从触发帧进入，并在跨字幕切句时保持同一容器？
13. 切换点前后各 `3` 帧是否无重影、重复叠层和跳动？

任一问题答不上来时，重做映射，不进入渲染。

