# ikun 待机气泡与健康提醒实施计划

> **供执行代理使用：** 必须使用 `superpowers:subagent-driven-development`
>（推荐）或 `superpowers:executing-plans` 按任务逐项实施。步骤使用复选框跟踪。

**目标：** 实现 `ikun` 非常驻待机气泡、独立喝水提醒、23:00 睡觉提醒，
并发布 `0.2.0` Windows 程序。

**架构：** 在交互核心中增加可测试的调度常量和提醒规则，在 `App.tsx` 中用
独立定时器接入待机气泡；通过当前气泡文本校验避免待机隐藏计时器覆盖交互
气泡。睡觉提醒使用本地日期键去重。

**技术栈：** TypeScript、React、Vitest、Vite、Tauri 2、Rust。

---

### 任务一：增加交互规则测试

**文件：**
- 修改：`src/pet-core/interaction.test.ts`
- 修改：`src/pet-core/interaction.ts`

- [x] **步骤 1：编写失败测试**

验证 `ikun` 待机气泡时长为 5000 毫秒，随机间隔边界为 120000 和
180000 毫秒；验证喝水提醒独立文案；验证睡觉提醒在 23:00 后同一天只触发一次。

- [x] **步骤 2：运行测试并确认失败**

```powershell
npm test -- src/pet-core/interaction.test.ts
```

预期：新增导出或行为尚不存在而失败。

- [x] **步骤 3：实现最小交互规则**

在 `interaction.ts` 中实现待机气泡调度、喝水提醒、睡觉提醒和本地日期键函数。

- [x] **步骤 4：运行测试并确认通过**

```powershell
npm test -- src/pet-core/interaction.test.ts
```

### 任务二：接入气泡定时器

**文件：**
- 修改：`src/App.tsx`

- [x] **步骤 1：增加待机气泡定时器**

进入 `ikun` 时立即显示 5 秒，并在每次隐藏后安排 2～3 分钟后的下一次显示。

- [x] **步骤 2：保护高优先级气泡**

交互发生后，旧的待机隐藏计时器只在当前文本仍是该待机文案时才能清空气泡。

- [x] **步骤 3：拆分健康提醒**

护眼调用 `getPetCareReminderAction()`，喝水调用
`getPetWaterReminderAction()`；23:00 后优先检查睡觉提醒。

### 任务三：升级并打包 0.2.0

**文件：**
- 修改：`package.json`
- 修改：`package-lock.json`
- 修改：`src-tauri/Cargo.toml`
- 修改：`src-tauri/Cargo.lock`
- 修改：`src-tauri/tauri.conf.json`
- 修改：`src/App.tsx`
- 修改：`src/pet-core/platform.ts`
- 修改：`src/marketing/marketingContent.ts`

- [x] **步骤 1：统一版本和下载地址**

将应用版本更新为 `0.2.0`，更新检测使用 `v0.2.0`，安装包下载地址使用
`愈心桌宠_0.2.0_x64-setup.exe`。

- [x] **步骤 2：完整验证**

```powershell
npm test
npm run build
```

- [x] **步骤 3：正式打包**

```powershell
npm run tauri build
```

- [x] **步骤 4：复制并校验发布文件**

将主程序复制为 `releases/愈心桌宠.exe`，将安装包复制为
`releases/愈心桌宠_0.2.0_x64-setup.exe`，比较源文件与副本 SHA-256。
