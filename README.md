# DSH Computer Use Fish · 鲸鱼娘电脑操作插件

独立维护的 DeepSeek Harness 社区插件，将电脑控制与鲸鱼娘桌宠动画组合在一个插件包中。当前版本 `0.3.2-fish.6`；本仓库主开发分支为 `main`，拥有独立 Git 数据库，不依赖原项目工作树。

## 工作方式

Harness → 插件编排 → cua-driver 执行截图与鼠标键盘操作。
插件通过本地私有 socket 启动 Python/GTK 桌宠，依次呈现靠近、准备、执行和结果动作。动画程序只接收操作类别、状态与位置，不接收输入内容或截图，不执行真实输入。

桌宠可关闭；电脑控制继续可用。一次真实点击不会因动画变体增加次数。

## 当前能力与范围

- 12 个电脑操作工具，Linux 前台输入审批重试、坐标换算与快照保护。
- 每类工具三个动作候选，包含奔跑、跳拍、转身拍、交替双拍、搬运、推拉、划水、观察、输入与等待。
- 完整角色姿势与已有动画组合；目前不是 36 段独立绘制动画。
- 已验证 Ubuntu/GNOME Wayland + XWayland、单屏 200% 缩放、Node 22.23.3、Harness 0.2.1-rc.2、cua-driver 0.37.0。其他桌面和多屏尚需验证。

## 本地开发

需要 Node >=22.18、npm 和 Python 3。纯逻辑测试不需要图形会话：

```sh
npm ci
npm test
npm run check
python3 -m unittest discover -s companion -p 'test_*.py'
```

实际桌宠另外需要当前图形会话的 GTK3、PyGObject、Cairo 和 XWayland；真实电脑控制还需要独立安装并运行 cua-driver。浏览器/桌面实测会产生真实输入，应使用仓库中的隔离测试窗口。

## 安装与配置

仓库名称为 `dsh-computer-use-fish`，为兼容现有配置，包名和 bundle 标识仍是 `dsh-computer-use`。不要在同一 profile 同时加载原版和此版本，否则工具名称会冲突。

已有本机安装仍从 `~/.local/share/dsh/plugins/dsh-computer-use-fish` 加载，不因源代码迁移而改变。更换部署来源后需显式部署代码；修改本仓库不会自动替换运行版本。

插件配置：`companionEnabled`、`companionSize`（200–420）、`companionReducedMotion`。已配置本机显示命令时，`dsh-fish show/hide/status` 只控制显示；隐藏不会取消任务。

原版 `install.sh` 面向 harness-desktop 的 home patch 布局，不是当前 Linux profile 的通用迁移器。新设备应先确认 Harness profile 和依赖布局、备份配置，再配置本地包路径与 bundle；不要直接照搬本机绝对路径。

## 维护与来源

- [独立仓库维护说明](docs/MAINTENANCE.md)
- [第三方来源与许可](THIRD_PARTY.md)
- [动画实现与版本记录](companion/README.md)
- [设计方案](docs/fat-fish-companion-plan.md)
- [上游原始说明存档](docs/UPSTREAM-README.md)（仅作历史参考，里面的下载、商店与发布信息属于上游）

程序代码使用 MIT 许可；角色素材另有非商业与相同方式共享要求，不能按 MIT 代码许可处理。本项目不是 DeepSeek 官方产品。目前只建立本地仓库，尚未创建远程仓库或发布 npm 包。
