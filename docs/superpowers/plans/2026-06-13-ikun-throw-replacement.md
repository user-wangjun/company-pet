# ikun 丢球动作替换实施计划

> **供执行代理使用：** 必须使用 `superpowers:subagent-driven-development`
>（推荐）或 `superpowers:executing-plans` 按任务逐项实施。步骤使用复选框
> 跟踪。

**目标：** 将用户参考图 09-16 八帧提取为新的 `ikun` 单击丢球动作，
修复白色地面残留，再追加一张无球收尾帧，并生成通过验证的 Windows EXE
与安装包。

**架构：** 使用包内 QA 脚本对参考图、元数据和图集第 6 行进行确定性检查；
使用 Pillow 按固定面板切分、背景分离、组件筛选和待机锚点对齐生成透明帧；
仅覆盖图集第 6 行。第 9 个收尾帧作为宠物包内独立透明图片，由 `pet.json`
声明路径，运行时只追加到 `ikun` 的 `gnawFish` 动画。

**技术栈：** Python、Pillow、JSON、WebP/GIF、Vitest、Vite、Tauri 2、Rust。

---

### 任务一：建立丢球动作验收检查

**文件：**
- 新建：`public/pets/ikun/qa/tools/check_throw_replacement.py`
- 检查：`public/pets/ikun/spritesheet.webp`
- 检查：`public/pets/ikun/actions.json`
- 检查：`public/pets/ikun/pose-map.json`

- [x] **步骤 1：编写失败检查**

检查脚本必须验证：包内存在 `throw-09-16-ref.png`；第 6 行有八个有效透明
单元格；动作元数据引用 09-16；篮球状态不再使用旧版 0-3 可见、4-7 隐藏
规则。

- [x] **步骤 2：运行检查并确认失败**

运行：

```powershell
python public/pets/ikun/qa/tools/check_throw_replacement.py
```

预期：因为包内新参考图和新元数据尚不存在而失败。

### 任务二：提取并替换第 6 行

**文件：**
- 新建：`public/pets/ikun/references/throw-09-16-ref.png`
- 新建：`public/pets/ikun/qa/throw-v14/frames/frame-00.png` 至 `frame-07.png`
- 新建：`public/pets/ikun/qa/throw-v14/row-6-throw-v14.png`
- 修改：`public/pets/ikun/spritesheet.webp`

- [x] **步骤 1：复制用户参考图到宠物包**

使用包内相对路径保存参考图，运行时和文档不得引用下载目录绝对路径。

- [x] **步骤 2：按 09-16 顺序提取八帧**

切分两行四列面板，移除浅灰背景、编号、地面阴影和脱离角色的白色动效线，
保留角色主体及完整篮球组件。

- [x] **步骤 3：用待机第 08 帧校准衔接**

统一角色视觉高度、脚底基线和身体中心；对高举或飞出的篮球保留安全边距。

- [x] **步骤 4：只替换图集第 6 行**

保存替换前图集副本用于比较，确认第 0-5、7-8 行像素完全不变。

### 任务三：同步元数据和说明

**文件：**
- 修改：`public/pets/ikun/actions.json`
- 修改：`public/pets/ikun/action-board.json`
- 修改：`public/pets/ikun/pose-map.json`
- 修改：`public/pets/ikun/README.md`
- 修改：`public/pets/ikun/SOURCES.md`

- [x] **步骤 1：将包修订号更新为 v13**

记录第 6 行使用用户参考 09-16，并替换旧的短丢球说明。

- [x] **步骤 2：逐帧记录动作语义**

八帧依次记录低位持球、托球、指尖旋球、旋球保持、旋球收势、回到持球、
出手和篮球飞离。

- [x] **步骤 3：更新中文说明**

明确第 6 行使用 `references/throw-09-16-ref.png`，旧丢球帧已全部移除。

### 任务四：重建 QA 并验证

**文件：**
- 修改：`public/pets/ikun/qa/contact-sheet.png`
- 新建：`public/pets/ikun/qa/contact-sheet-v14.png`
- 修改：`public/pets/ikun/qa/previews/row-6.gif`
- 新建：`public/pets/ikun/qa/throw-v14/validation.json`
- 新建：`public/pets/ikun/qa/throw-v14/transition-08-09.gif`

- [x] **步骤 1：运行丢球动作检查**

运行：

```powershell
python public/pets/ikun/qa/tools/check_throw_replacement.py
```

预期：通过。

- [x] **步骤 2：运行图集验证并重建视觉产物**

运行 `validate_atlas.py`、`make_contact_sheet.py`，并生成第 6 行 GIF 与
待机 08 到丢球 09 的过渡 GIF。

- [x] **步骤 3：视觉检查**

检查接缝、透明边缘、角色尺度、脚底基线、篮球完整性和动作顺序。

- [x] **步骤 4：运行项目验证**

运行：

```powershell
npm test -- src/pet-core/petAssets.test.ts src/pet-core/animationRows.test.ts src/pet-core/interaction.test.ts
npm run build
```

预期：测试和构建均成功。

### 任务五：打包 Windows EXE

**文件：**
- 生成：`src-tauri/target/release/yuxin-desktop-pet.exe`
- 生成：`src-tauri/target/release/bundle/nsis/愈心桌宠_0.1.0_x64-setup.exe`
- 修改：`releases/愈心桌宠.exe`
- 修改：`releases/愈心桌宠_0.1.0_x64-setup.exe`

- [x] **步骤 1：运行 Tauri 打包**

运行：

```powershell
npm run tauri build
```

预期：生成 Windows 主程序和 NSIS 安装包。

- [x] **步骤 2：复制发布产物**

将新主程序和安装包复制到 `releases/` 的现有稳定文件名。

- [x] **步骤 3：校验发布产物**

比较源产物与 `releases/` 中对应文件的 SHA-256，并确认时间戳来自本次构建。

### 任务六：修复白色残留并追加无球收尾帧

**文件：**
- 修改：`public/pets/ikun/qa/tools/build_throw_v14.py`
- 新建：`public/pets/ikun/references/throw-finish-ref.png`
- 新建：`public/pets/ikun/throw-finish.png`
- 修改：`public/pets/ikun/pet.json`
- 修改：`src/pet-core/petAssets.ts`
- 修改：`src/App.tsx`
- 修改：`src/pet-core/petAssets.test.ts`
- 修改：`src/pet-core/animationRows.test.ts`

- [x] **步骤 1：编写失败测试**

验证清单声明相对路径 `throwFinishPath`，且 `ikun` 的丢球动画可以在八帧
图集后追加一个独立纹理。

- [x] **步骤 2：修复白色地面残留**

在角色脚底基线以下删除低饱和浅色区域，不删除鞋子、裤腿、眼白和吊坠。

- [x] **步骤 3：提取第 17 帧**

从新参考图保留人物指向姿势，移除篮球、白色动作线、背景和地面阴影，
输出透明 192x208 `throw-finish.png`。

- [x] **步骤 4：实现运行时追加**

加载可选的独立收尾图片，仅在 `petId === "ikun"` 且播放 `gnawFish`
时将它追加到图集八帧之后。

- [x] **步骤 5：重建 QA 和验证**

生成九帧 GIF，验证最后一帧无篮球、所有帧无白色地面残留，运行完整测试、
构建和 Tauri 打包。
