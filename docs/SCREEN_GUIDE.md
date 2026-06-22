# 3D 数据驾驶舱使用指南

## 概述

3D 数据驾驶舱是项目面向演示 / 路演 / 学术报告 / 团队周会场景的实时可视化大屏。
它把后端「分类点 + 聚合 KPI + 趋势」用 Three.js 地球 + ECharts 图表 + AMap 缩略图
集中渲染在一屏，搭配快捷键 + 全屏 + 自动刷新，能直接用作「对外展示」工具。

## 访问

- 登录后 → 首页 (`/app/home`) → 第 5 张特性卡「3D 数据驾驶舱」点击进入
- 或直接访问 `/app/screen`（已登录状态）

## 功能

1. **3D 地球** — Three.js `SphereGeometry(50, 64, 64)`，自动绕 Y 轴 0.05 rad/s 旋转
2. **大气层** — `SphereGeometry(52, ...)` + 透明蓝绿渐变（`BackSide`）
3. **3 条卫星轨道环** — 不同倾斜角 + 缓慢旋转
4. **1000 颗星空** — 随机分布的星点背景
5. **分类点云** — Top-50 分类点按 10 类霓虹色散布地球表面，size 用 `sin(time + offset)` 周期呼吸
6. **4 个 KPI** — 总记录数 / 今日新增 / 活跃用户 / 平均准确率，1.2s 数字滚动
7. **2 张 ECharts** — 分类分布环形图 + 30 天趋势折线图
8. **地图热点层缩略图** — AMap 2D 全球视野（zoom=3），Top-50 蓝色脉冲点
9. **定时刷新** — 30s 自动重拉数据（`requestIdleCallback` 防抖）
10. **全屏** — F 键或顶部「全屏」按钮
11. **快捷键** — F / R / Esc
12. **角色徽章** — 顶部右侧显示当前用户角色（admin / user）
13. **退出大屏** — 顶部「退出大屏」按钮，跳回 `/app/home`

## 快捷键

- `F` — 全屏切换（`document.documentElement.requestFullscreen()` / `exitFullscreen()`）
- `R` — 手动刷新数据（重新调用 `/api/stats/dashboard`，触发数字滚动）
- `Esc` — 退出大屏（先退出全屏，再返回首页 `/app/home`）

> 键位监听在 `onMounted` 注册，`onUnmounted` 解绑，不污染全局。

## 演示场景

- **学术报告开场**：F 全屏后定格 30s，地球旋转 + KPI 滚动抓住观众
- **路演 5 分钟**：R 键手动刷数据展示活跃度（"看，刚才又有人分类了一张图"）
- **团队周会**：全屏模式作为背景墙，配合讲解今日新增 / 分类分布
- **答辩 / Demo Day**：3D 地球 + 4 KPI 一眼能讲清楚"我们在做什么"

## 视觉风格

- 深空黑底 `#0A0E1A`
- 霓虹蓝 `#00E5FF` / 青绿 `#10F2C5` 强调
- 衬线大字 + 数字辉光（`text-shadow` 模拟霓虹灯）
- 10 类颜色与项目 colorMap 对齐（`AnnualCrop` / `Forest` / ... 10 种霓虹色）

## 数据源

`GET /api/stats/dashboard`

- 30s 服务端进程内缓存（`functools` + 时间戳）
- admin 看到全平台统计；user 仅看自己
- 失败优雅降级到空数据 + 200，绝不暴露 5xx 给大屏
- 响应头 `X-Cache: HIT / MISS` + `X-Cache-TTL: <剩余秒数>`

## 性能

- 地球 50 半径 + 64×64 段，~8200 顶点，单 draw call
- 点云 50 个 `Points`，< 100 draw call
- ECharts 默认 canvas 渲染（按需可切 SVG）
- AMap 缩略图禁用拖拽 + 缩放，减轻 GPU 压力
- 单页总渲染 < 16ms（60fps 起步）
- 首屏入场 `camera.z 200→100`，1.2s `power2.out` 缓动

## 文件结构

| 路径 | 职责 |
|------|------|
| `frontend/src/views/user/BigScreenView.vue` | 主视图（HTML overlay + 模板结构） |
| `frontend/src/utils/three/EarthScene.ts` | Three.js 地球场景封装（5 个公开方法） |
| `frontend/src/utils/three/textures.ts` | 程序化地球纹理 + 大气层 shader |
| `frontend/src/utils/three/colors.ts` | 10 类 → 10 种霓虹色映射 |
| `frontend/src/api/index.ts` | `getDashboardStats()` 函数 |
| `backend/api/stats.py` | `GET /api/stats/dashboard` 聚合接口 |
| `backend/schemas/stats.py` | `DashboardStats` / `Kpi` / `TimeSeriesPoint` / `LocationPoint` Pydantic 模型 |
| `frontend/src/styles/theme.scss` | 5 个 `--color-screen-*` 大屏专用 token |

## 注意事项

1. **首次加载**：模型未训练 / DB 无数据时，KPI 全部为 0 + 分类分布全 0（空数据兜底）
2. **角色权限**：admin 看全平台，user 仅自己；权限校验在后端，token 中 role 决定返回数据范围
3. **30s 缓存**：连续按 R 键可能命中缓存，看不到实时变化是预期行为
4. **全屏 API**：部分浏览器要求用户手势触发；如果 F 键无响应，先点页面一下
5. **prefers-reduced-motion**：用户系统设置开启「减少动画」时，自动降级为 0 动画静态大屏

## 故障排查

| 现象 | 原因 | 解决方案 |
|------|------|---------|
| 地球不显示 | WebGL 未启用 | 浏览器启用硬件加速 |
| KPI 全 0 | 用户尚未分类 | 上传几张图后再来 |
| AMap 缩略图空白 | 未配置前端 VITE_AMAP_JS_KEY | 配 Key 或允许 mock 兜底 |
| F 键无效 | 浏览器要求用户手势 | 先点击页面激活 |
| 30s 后数据不刷新 | 网络断 | 状态栏会显示「最近同步 HH:MM:SS」时间定格 |

## 截图位置（建议）

> 项目暂未提供截图，开发完成后请补充以下位置：
> - 大屏首屏（地球 + 4 KPI + 2 图表 + 地图缩略图）
> - F 键全屏效果
> - admin / user 两种角色的 KPI 对比

## 相关文档

- 后端聚合接口：`backend/api/stats.py` 顶部 docstring
- E2E 验证：`reports/e2e_test.py` PART 9
- Phase 进度：`.trae/specs/core-experience-revamp/checklist.md` Phase B 段
