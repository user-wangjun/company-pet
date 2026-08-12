# Companion Harness V1 TODO

> 状态：Phase 1、Phase 2、Phase 3、Phase 4、Phase 5 的纯逻辑实现与验收已通过；Phase 6 当前处于 P1 收口前复核，尚未通过；App 接线、Phase 7--8 和发布验证未开始
> 审查日期：2026-08-12
> 产品：愈心桌宠
> 输入文档：`Companion Harness PRD v1.2`、`Companion Harness Technical Design v1.2`

## 1. 审查结论

两份 v1.2 输入文档已经与当前桌宠高度契合，产品方向和技术边界均无阻塞项：统一 AI 入口、Local First、One Call First、模型只提候选、真实执行后再确认、共享用户事实并隔离宠物关系、Task / Reminder 远程零外发、主动提醒先过本地策略，这些都与现有实现和数据契约一致。

下表保留 v1.1 审查时发现的问题及其处理依据；这些适配决定已经写入两份 v1.2 源文档。本 TODO 只负责把已冻结设计拆成实施、验收和发布门禁，不再充当源文档冲突的补丁层。

| v1.1 审查发现（已在 v1.2 修正） | 当前项目事实 | v1.2 / TODO 决定 |
|---|---|---|
| Harness 可能被理解成 Agent Runner / Tool Loop | 旧路线中仍有最多 4 次 Provider 调用与 Tool Call 循环的规划 | v1.2 已明确 Harness V1 是单次请求编排层；不做 Tool Loop、ReAct、Planner、Critic 或二次“修文案”调用 |
| Service 后面默认是 SQLite | 当前 Memory、Task、Outbox 已有经过恢复与删除保护验证的本地 Repository / `localStorage` 事实源 | v1.2 已改为复用现有本机持久化；不迁移 SQLite，不建立第二套 Repository |
| Provider 是 Local / Gemini / Custom Gemini | 当前已统一为 `local`、`gemini-native`、`openai-compatible` 协议，Custom Gemini 是 Profile/Endpoint 配置问题 | v1.2 已采用现有 Provider Profile + Protocol + Adapter，不退回写死厂商枚举 |
| 技术设计把 Action/Memory 提取能力和领域 Envelope 放进 Provider | 阶段 7 已冻结最小、供应商中立的传输合同；Task、Memory、Soul 不能反向耦合到 Adapter | v1.2 已将领域语义收回 Harness 自有 `CompanionModelPort` / Codec；Provider Adapter 只实现通用传输与结构化输出能力 |
| Memory scope 为 `user_global` / `pet_relationship`，类型为 profile/person/project 等 | 当前持久化契约是 `global` / `pet:<id>`，类型为 fact/relationship/episode/preference | v1.2 已直接复用现有 Memory schema，并记录产品语义映射，不复制数据 |
| 普通模型回复可产生 Memory Candidate | 当前正式契约只允许“用户明确要求”或“用户确认后”的低风险长期写入 | v1.2 已冻结候选默认不落盘；只有 explicit / confirmed 且通过隐私、作用域、重复、冲突、时效检查后才保存 |
| TaskService 与 ReminderService 看似是两个事实源 | 当前 Reminder 是 `TaskDatabase` 中绑定 Task 的子实体，Task 是唯一任务事实源 | v1.2 已明确 Reminder facade 复用现有 Task Store，不新建 Reminder 数据库 |
| Context 可选择“相关或近期到期”Task | 正式远程白名单没有 Task/Reminder；现行 Context/Provider 请求也不携带这些事实 | v1.2 已冻结不向远程 Context 注入任何 Task/Reminder 投影；相关性、近期到期或优先级均不是外发理由 |
| Context 可包含 User Profile 与 Conversation History | 当前个人资料中的性别、邮箱、电话明确不得进入远程 Provider；完整原始聊天默认不长期保存 | v1.2 已改为穷举白名单、当前运行时 Session 安全片段，且不新增完整聊天持久化 |
| 技术设计 Action 示例缺少 PRD 中的 `update_reminder` | PRD 必做项包含它，现有代码已具备延期/改期能力 | v1.2 Action 合同已补齐 `update_reminder`；现有 cancel/postpone/reschedule 继续作为受控本地兼容动作 |
| `CompanionInput` 只有业务字段 | 当前 UI 已有 request id、`AbortSignal`、停止回复、切宠物和迟到结果保护 | v1.2 已补入 request/session/source-message identity、当前时间与取消信号；取消后不得产生新副作用 |

### 本 TODO 的范围权威

- 本文件是 Companion Harness V1 唯一有效的实施、验收和发布门禁清单；V1 的所有后续开工项只从本文件领取。
- [Agent / Memory / Task TODO](agent-memory-todo.md) 阶段 0--7 继续作为已验收底座的权威记录，正文不由本文件改写；[数据与隐私合同](agent-memory-data-contract.md) 继续有效。
- [Agent / Memory / Task TODO](agent-memory-todo.md) 原阶段 8--11 已被本文件整体替代，只保留历史路线背景，不再提供可执行勾选项；其中多次 Provider Tool Loop、Tool Registry 和 `pet.express` 均不是 Harness V1 要求。
- 输入文档中的推荐目录只是参考。V1 不做大规模搬目录；新增纯逻辑继续放在 `src/pet-core/`，复用 `src/task-core/`、`src/storage/` 和现有 Tauri 模块。

## 2. V1 冻结边界

### 必须成立

- 所有聊天发送最终只走 `UI -> CompanionHarness -> Harness-owned CompanionModelPort / Local Domain -> UI`。
- 模型边界固定为 `CompanionHarness -> Harness-owned CompanionModelPort -> Provider Adapter`；领域 Envelope 的组装、解析和校验属于 Harness，Provider Adapter 不认识 Action、Memory、Task 或 Soul 语义。
- 能由本地确定性规则完成的请求使用 0 次外部模型调用。
- 需要远程模型的普通聊天最多 1 次外部调用。
- Reply、Action Candidates、Memory Candidates 在同一次远程响应中返回；不再调用模型修正回复。
- Model 只能提出候选；Schema、权限、明确意图、业务规则、去重、执行和最终成功确认都归 Harness / Domain Service。
- Action 只有在领域写入成功后才能显示成功；写入失败、目标歧义、重复、取消和超时均不得包装成成功。
- V1 的 `REMINDER_DUE` 与 `TASK_DUE_SOON` 始终使用本地宠物文案，0 次模型调用；AI Enhanced 仅保留为未来非 Task / Reminder 事件的扩展边界，不在 V1 接远程路径。
- Scheduler 只产生事件，现有 Proactive Gate 决定是否允许表达，Harness 不能绕过勿扰、冷却、次数、幂等和宠物路由。
- API Key 仍只从系统安全存储进入 Provider Adapter 的短生命周期调用参数，不进入 Prompt、Harness Response、普通日志或持久化对象。
- 当前用户输入、历史、Soul、Preference 和已确认 Memory 在远程调用前继续经过统一 fail-closed 隐私过滤；Task、Reminder、ReminderInstance 及其派生投影不进入 V1 远程 Context。

### 明确不做

- 不做 Agent Loop、Tool Calling 循环、Decision LLM、Planner、Critic、Multi-Agent 或后台自由思考。
- 不做 Browser、Email、Calendar、文件、Shell、系统控制或任意外部工具。
- 不新增 SQLite、Vector DB、Embedding Pipeline、云同步、远程 Outbox Transport 或账号系统。
- 不持久化完整 Prompt、完整原始聊天、模型原始响应或敏感 Context。
- 不用 Harness 重写现有 Task Scheduler、Memory Repository、Task Store、Provider 安全存储或宠物资源边界。

## 3. 目标运行流程

```text
CompanionInput
  -> Turn / cancellation guard
  -> LocalRequestHints + current deterministic route
  -> local-only request? -> Action/Memory Domain -> ResponseFinalizer
  -> ContextBuilder + ContextBudget + privacy projection
  -> Harness-owned CompanionModelPort
     -> Harness Model Codec
     -> domain-neutral Provider Adapter -> one Provider request
  -> normalized CompanionModelResponse
  -> ActionPolicy -> existing Domain Service -> ExecutionResult
  -> MemoryPolicy -> existing MemoryRepository
  -> ResponseFinalizer (local, deterministic)
  -> current runtime Session + UI
```

主动事件固定为：

```text
TaskDatabase / ReminderInstance
  -> existing Scheduler / scan
  -> stable CompanionEvent
  -> existing Proactive Gate
  -> ignore | local expression
  -> existing pet delivery route
```

## 4. 核心合同 TODO

### 4.1 Harness 输入输出

- [ ] 新增 `src/pet-core/companionHarnessTypes.ts`，定义由 Harness 拥有且与 Provider Adapter 解耦的 `CompanionInput`、`CompanionResponse`、`CompanionEvent`、`CompanionModelResponse`、`ActionCandidate`、`ActionExecutionResult` 和 `MemoryPolicyResult`。
- [ ] `CompanionInput` 至少携带 `requestId`、`sessionId`、`sourceMessageId`、`petId`、`message`、`source`、当前时间、IANA timezone（可得时）、offset 和 `AbortSignal`。
- [ ] 当前产品是单机单用户，不为满足设计稿而虚构账号系统；如合同保留 `userId`，V1 只能使用稳定的本地默认值，不能据此声称已支持多账号隔离。
- [ ] `CompanionResponse` 返回最终文本、Provider 披露、Action/Memory 结果摘要、是否降级和本轮外部调用次数；不得返回 Key、完整 Prompt 或原始敏感参数。
- [ ] Action Result 使用可表达真实领域结果的状态：`succeeded`、`duplicate`、`not_found`、`ambiguous`、`confirmation_required`、`rejected`、`failed`、`cancelled`，不只使用一个含糊的 boolean。

### 4.2 Harness 编排器

- [ ] 新增 `src/pet-core/companionHarness.ts`，以依赖注入方式接收 Context、`CompanionModelPort`、Task、Memory、Proactive 和安全日志接口；文件本身不读写 SQL / `localStorage`，不直接依赖 Provider Adapter，也不发 HTTP。
- [ ] 暴露 `respond(input)` 与 `handleEvent(event)`；两条路径共享安全、Provider 和可观测性边界，但主动事件不得进入聊天 Action 执行路径。
- [ ] 每个 Session 同时只允许一个活动 Turn；新发送、停止、退出、换宠物时取消旧 Turn。
- [ ] Provider 返回后、每个副作用执行前、写入最终 UI 前都检查 request identity 与 `AbortSignal`。
- [ ] 为已开始的写操作定义明确边界：写入前取消则不执行；写入已经成功则记录真实结果，不能伪装成“未发生”或重复执行。
- [ ] 本地显式路由与模型候选使用统一去重键，保证同一句话不会被本地 Extractor 和模型各执行一次。

### 4.3 LocalRequestHints

- [ ] 保留并复用 `resolveCompanionChatPipelineRoute()`、Task/Memory/Preference Extractor 和主动偏好解析器，把结果规范化为 hints / local candidate，而不是再写一套中文意图识别。
- [ ] 本地路由只提供确定性证据和本地完成能力；不得因为关键词存在就提升模型候选权限。
- [ ] 明确低风险、时间完整的 Task/Reminder 继续 0 API 创建；含糊时间、敏感内容、高风险或目标不唯一时进入确认/拒绝，不交给模型越过门禁。
- [ ] 对本地路由、模型候选和 Provider text-only fallback 增加“唯一所有者”测试，确保每轮最多执行一条等价写操作。

## 5. 分阶段实施

### Phase 1：纯 Harness 骨架与 Turn 安全

目标：先建立不依赖 React 的单次编排器，不改 UI 行为。

- [x] 完成 Harness 类型、依赖接口和最小 `respond()` 骨架。
- [x] 复用当前 Provider 错误分类、15 秒超时、远程失败后至多一次本地降级与降级披露。
- [x] 加入 request/session/message identity、取消、迟到结果丢弃和调用次数计数。
- [x] 建立 Fake `CompanionModelPort` / Fake Domain Services，覆盖纯文本成功、超时、取消、畸形回复、领域失败与本地降级；Phase 1 不修改 Provider 协议。
- [x] 普通聊天允许无 Action、无 Memory Candidate 直接结束。

验收门：

- [x] 纯文本远程聊天恰好 1 次 Provider 调用；本地聊天 0 次外部调用。
- [x] 取消后的迟到响应不能写 UI、Memory 或 Task。
- [x] Harness 纯逻辑测试通过后才进入 App 接线。

### Phase 1 实施记录（2026-08-11，严格收口复验）

- 进度：5/5；验收门：3/3。
- 新增纯逻辑 Harness、Harness-owned `CompanionModelPort` 合同和 Fake 测试；Turn 以 request/session/source-message/user/pet identity 绑定，支持取消、15 秒超时、迟到丢弃、0/1 外部调用计数和至多一次本地降级。
- 严格收口：fallback 只有 `info.kind === "local"` 才允许调用；通用 Model Attempt 边界把 remote 外部调用硬限制为每 Turn 1 次；异步 Sink 必须通过 Harness Turn Guard 在最后一刻提交，Harness 在 `await commit()` 后再次检查有效性。
- 对抗证据：主远程失败且 fallback 为 remote 时，fallback `generate()` 0 次、`external=1`、结果非成功降级；合法 Local fallback 为 `external=1/local=1/fallback=1`；旧 Turn 被 supersede 或取消后 Sink 写入数为 0。
- 证据（Phase 1 收口时）：Harness 定向测试 24/24；相关 Companion Provider/Runtime/Pipeline/Context/Privacy 回归 74/74；`npm run build` 通过；`git diff --check` 通过。
- 范围声明：本轮没有接入 `App.tsx` 或 React UI，没有修改 Gemini-native、OpenAI-compatible 或 Local Provider 协议，没有实现真实 Task、Reminder、Memory Action，没有实现 Context Budget 或 Proactive Event，也没有进入 Phase 2。
- Fake/纯逻辑测试不等同于真实 Provider、Tauri 实机或可发布验证；本记录不表示整个 Harness V1 已完成。

### Phase 2：ContextBuilder 与全局 Budget

目标：扩展现有 `companionContext.ts`，不重写已有 Soul、Preference、Memory 和隐私过滤。

Phase 2 前置门禁（2026-08-11 已完成）：

- [x] 正式数据合同已把远程允许内容改为穷举白名单，并明确排除 Task、Reminder、ReminderInstance、Task 派生摘要和 Outbox Task Event。
- [x] 现行 `CompanionContextAssemblerInput`、Provider 输入和 Gemini-native / OpenAI-compatible 请求体均未携带 Task/Reminder 字段，未发现需要保留的既有外发兼容行为。
- [x] Context 与双远程协议请求体 fixture 已覆盖相关、近期到期、无关、已完成、已取消、已删除 Task 以及 Reminder/ReminderInstance sentinel；当前边界通过后才允许实施以下 Budget 工作。

- [x] 新增可测试的全局 Context Budget；以字符数/保守 token 估算控制总量，而不是只靠各数组固定条数。
- [x] 新增纯逻辑 ContextBuilder；可注入 Harness、遵守 AbortSignal，并在 Context 完成后保持 provider-neutral 的最终隐私门禁。
- [x] 固定优先级：平台安全与权限 > 当前用户输入 > 当前宠物 Soul > 当前运行时 Session > 相关已确认 Memory；Task/Reminder 不参与远程 Context Budget。
- [x] 保留 `global` 与 `pet:<id>` 检索；宠物关系 Memory 只进入对应宠物 Context。
- [x] Harness V1 不读取 `TaskDatabase` 来构造远程 Context，也不发送 Task、Reminder、ReminderInstance、Task 摘要或 Outbox Task Event；“相关”“近期到期”“高优先级”均不能触发例外。
- [x] 用户明确讨论某个任务时，当前用户输入仍按普通输入白名单处理，但不得据此 join 本地 Task 事实；现有明确 Task/Reminder 本地确定性路由保持不变，本轮未改动其领域执行。
- [ ] 未来如确需最小 Task 投影，必须先修订 `docs/agent-memory-data-contract.md`，冻结明确讨论条件、逐字段 allowlist、终态/删除语义和用户披露，并先完成双远程协议隐私 fixture；不得只修改本 TODO 或先写实现。
- [x] `currentTime`、IANA timezone（可得时）和当前 offset 只进入 `CompanionInput` 的本地 Task Extractor / Handler；V1 Model Codec 不把它们编码进远程 Context，也不直接信任模型时间。
- [x] User Profile 只允许昵称等已经授权的低风险投影；邮箱、电话、性别和其他未授权字段不进入 Provider Context。
- [x] 远程发送前执行最终 privacy pass；当前输入命中敏感规则时不发起远程请求。
- [x] Budget 裁剪产生可测试的非敏感摘要元数据，但不记录被裁掉的原文。

验收门：

- [x] Global Memory 跨宠物可见，Relationship Memory 不跨宠物。
- [x] 超预算时按固定优先级裁剪，永不裁掉安全规则和当前用户输入。
- [x] 密码、Token、Key、证件、卡号、精确地址、医疗/用药及历史敏感消息均不进入远程请求 fixture。
- [x] 相关、近期到期、无关、已完成/取消和已删除 Task，以及 Reminder/ReminderInstance sentinel，均不出现在 Gemini-native 或 OpenAI-compatible 请求体；已有确定性 Task 路由测试保持 Provider 分支之外。

### Phase 2 实施记录（2026-08-11）

- 进度：Phase 2 实施项 10/10；验收门 4/4。条件性的未来 Task 最小投影门禁未触发，继续保留为未勾选的变更前置条件。
- 新增 provider-neutral 全局 Budget：默认上限为 12,000 Unicode code points 与 8,000 个保守 token 估算；保护平台安全规则和当前输入，按 Memory → 旧 History → Preference → 可选系统指令 → Soul 的固定顺序裁剪，Soul 只在 code-point 边界裁剪，超出必需内容预算则 fail closed。
- 新增纯逻辑 ContextBuilder：可注入 Soul、Preference、Memory、History 或现有 `MemoryRepository.search` 边界；在构建前后检查 `AbortSignal`，Memory 按 `global` / 当前 `pet:<id>` 隔离，global relationship fail closed；最终远程 privacy pass 在两种协议之前再次执行。
- 隐私与时间证据：昵称等低风险 Profile 投影可保留；性别、邮箱、电话以及密码、Bearer Token、Key、证件、卡号、精确地址、医疗/用药和历史敏感内容均在远程发送前拒绝或过滤。`currentTime`、timezone、offset 只保留在本地输入边界，Budget metadata 仅含计数、枚举和裁剪原因，不含原文。
- Task/Reminder 证据：ContextBuilder 与 Budget 无 Task/Reminder import 或读取；相关、近期到期、无关、已完成、已取消、软删除、物理删除 Task，Reminder、ReminderInstance、Task projection、Tombstone、Outbox 和时间 sentinel 均未进入 Gemini-native 或 OpenAI-compatible body。现有确定性 Task 路由测试仍在 Provider 分支之前；本轮未改动 Task 领域执行。
- 测试与构建：Harness `27/27`；Context/Budget/Privacy 定向组 `51/51`；Provider/Pipeline 定向组 `35/35`；全量 `npm test` 为 `69` 个文件、`660` 个测试全部通过；`npm run build` 通过（仅保留既有大 chunk warning）；`git diff --check` 与本轮 10 个范围文件的空白/冲突标记检查通过。
- 范围声明：本轮只修改 Companion Harness、Context/Budget/Privacy 相关逻辑、测试和本 TODO；未接入 `App.tsx` 或 React UI，未开始 Phase 3，没有真实远程凭据/网络冒烟、Tauri 实机或视觉 QA，没有 Rust 改动或 Cargo 验证，没有 commit、push 或发布。

### Phase 2 强制收口复验（2026-08-11）

- 进度确认：Phase 2 实施项 10/10；验收门 4/4；此前条件性的 Task 最小投影门禁仍未触发，继续保持未勾选。
- A1 允许列表：远程 Preference / Profile 改为 exact allowlist；只保留已授权的全局昵称、replyStyle、companionStyle、eyeCare，以及当前宠物的 nickname / favorite / relationshipStyle；未知 key、其他宠物 scope、邮箱、电话、性别和伪装后的 Profile 敏感值均在最终门禁丢弃。完整 `CompanionUserProfile` 不进入 ContextBuilder 或 Provider 请求。
- A2 Trusted Context：正式 `assembleCompanionContext()` 输出带运行时 trust marker 并冻结；远程 `filterCompanionContextForRemote()`、Model Codec 和 Model Port 对手写/伪造/不匹配 Context fail closed，未通过时 Adapter / fetch 调用数为 0；本地 Adapter 仍可只接收当前用户输入。
- A3 token / CJK / emoji：`estimateCompanionTokens()` 使用 UTF-8 byte 数作为 provider-neutral 的保守代理，不假装等同厂商 tokenizer；`A=1`、`你=3`、`🙂=4`、`A你🙂=8`、组合字符 `e\u0301=3` 均有断言，字符上限与 token 上限分别计数并记录裁剪原因。
- 证据：Phase 2 定向组 `113/113`；Phase 2 + Phase 3 定向组 `145/145`；全量 `npm test` 为 `73` 个文件、`699` 个测试全部通过；`npm run build` 通过；`git diff --check` 通过。
- 范围声明：本次收口没有修改 `App.tsx`、Task / Reminder / Memory 执行、宠物资源、Live2D、Rust 或发布产物；没有真实 Provider 凭据、网络冒烟、Tauri 实机或视觉 QA 证据，不表示 Harness V1 已完成或可发布。

### Phase 3：Harness-owned CompanionModelPort 与领域中立 Provider Adapter

目标：由 Harness 拥有领域响应合同；现有 Adapter 只负责协议与传输，不引入 Tool Loop，也不重新耦合 Task / Memory 语义。

- [x] 在 Harness 侧新增 `CompanionModelPort`；它接收 Harness 模型请求并返回 `CompanionModelResponse`，是 `replyDraft`、`actions[]`、`memoryCandidates[]` 和非敏感 metadata 的唯一领域边界。
- [x] 新增 Harness-owned Model Codec，把安全 Context 转成通用 Provider 请求，并把 text / structured payload 解码成 `CompanionModelResponse`；Envelope 的 Prompt、Schema、解析与校验都不得下沉到 Provider Adapter。
- [x] Provider 能力只允许描述通用协议/传输事实，例如 text generation、已验证的 structured output / JSON Schema、取消、超时和 usage metadata；不得增加 `actionCandidates`、`memoryCandidates`、`memoryExtraction` 或其他桌宠领域 capability flag。
- [x] 保留现有 `send()` 作为迁移期兼容入口；如新增通用 `generate()`，其输入输出只能包含 system/messages、通用输出格式、文本/结构化 payload 和传输 metadata，不能导入 `ActionCandidate`、`MemoryCandidate`、Task、Memory 或 Soul 类型。
- [x] 未知/自定义协议默认 text-only 并 fail closed；结构化能力必须由 Adapter 明确验证，不能从 Provider 名称、Endpoint 或 Model 名称猜测。
- [x] 对 Harness Envelope 做严格运行时校验、长度限制、枚举校验和多余字段丢弃；畸形 candidate 一律不执行。
- [x] `local` Adapter 明确只提供文本；Task/Memory 核心能力由本地 Extractor 保持可用，不伪造模型候选。
- [x] `gemini-native` 只在通用 Adapter 能力确认支持时请求 structured payload；厂商请求字段不泄漏到 `CompanionModelPort`。
- [x] `openai-compatible` 的自定义 Endpoint 不假定支持某个厂商专属 `response_format`；能力未知时退回 text-only，不把解析失败当 Action。
- [x] Provider 连接测试继续是用户主动操作，且不经过领域 Envelope，不触发 Memory/Action；本轮保留 App 既有连接测试入口，未进行 App 接线迁移。
- [x] Key 只作为短生命周期 Adapter 参数使用；错误对象、metadata 和测试快照不得包含凭据或完整请求体。

验收门：

- [x] Local、Gemini-native、OpenAI-compatible 共用一套只验证通用请求、协议映射、取消、超时、错误和安全 metadata 的 Provider Adapter 合同测试。
- [x] `CompanionModelPort` / Model Codec 单独覆盖 text-only、合法 Envelope、畸形 Envelope、超长字段、未知 Action 和结构化能力降级。
- [x] 增加 import/类型边界检查：Provider Adapter 模块不得依赖 Harness 的 `ActionCandidate`、Memory Candidate、Task、Memory 或 Soul 领域类型。
- [x] 超时、取消、401/403、429、5xx 和网络失败均有覆盖；普通远程 Turn 的 Provider 请求数始终 `<= 1`。

### Phase 3 实施记录（2026-08-11）

- 进度：Phase 3 实施项 11/11；验收门 4/4。这里的“完成”仅指本阶段的纯逻辑 Model Port / Codec / Provider Adapter / Resolver 合同，不表示 App 已接管聊天或 Harness V1 可发布。
- Model Port / Codec：新增 Harness-owned `CompanionModelPort` 与 `companionModelCodec`；安全 Context 只编码为通用 system/messages/output/timeout/generation，内部 request/session/source-message/pet/time/budget 元数据不进入 Provider 请求；text-only 不从普通文本猜 Action / Memory，structured Envelope 严格校验 source id、scope、枚举、长度、数量、敏感字段和多余字段，畸形 structured 只使用同响应安全文本降级，不发第二次请求。
- Adapter / Resolver：新增领域中立 `companionProviderAdapter.ts` 与 `companionProviderResolver.ts`，统一 Local、Gemini-native、OpenAI-compatible 的通用协议映射；Local 强制 text-only 且 0 网络调用，远程 structured 仅接受显式 verified capability，未知协议/能力 fail closed；Key 只在 Adapter 闭包和请求 Header 的短生命周期内存在。
- 兼容与连接边界：旧 `send()` 保留为迁移兼容入口并复用通用 Adapter / Codec 的 wire mapping；连接测试仍由用户主动触发，使用 text-only 请求，不进入领域 Action / Memory 执行；未修改 `App.tsx`，未宣称 App 已接线。
- 对抗证据：覆盖远程手写/伪造/输入不匹配 Context 的 0 Adapter 调用、本地不可信 Context 的当前输入最小路径、Provider 失败分类、Abort/timeout、401/403/429/5xx/network/malformed、凭据 sentinel 不出现在错误/metadata/快照，以及每个普通远程 Turn 仅 1 次 Adapter 调用。
- 测试与构建：Phase 3 新增定向组 `32/32`；Phase 2 + Phase 3 定向组 `145/145`；全量 `npm test` 为 `73` 个文件、`699` 个测试全部通过；`npm run build` 通过（仅保留既有大 chunk warning）；`git diff --check` 通过。
- 范围声明：本轮未修改 `App.tsx`、Task / Reminder / Memory Action Pipeline、Proactive、宠物资源、Live2D、Rust 或发布产物；没有真实 Provider 凭据/网络冒烟、Tauri 实机或视觉 QA、`cargo test` / `cargo check`、commit、push 或发布证据。

### Phase 2 / Phase 3 继续收口复核（2026-08-11）

- ContextBuilder 的历史投影现在只保留 `id`、`speaker`、`text` 和合法的内部 `contextEpoch`；本地 `sound`、`status` 以及任意附加 Task / Reminder 字段不会进入受信 Context，也不会进入 Codec 映射。
- Preference allowlist 对运行时异常对象继续 fail closed；Model Codec 对 `MemoryCandidate.expiresAt` 和 Provider metadata 做类型、长度与安全投影，畸形字段只丢弃候选，不重试 Provider。
- Phase 2 / Phase 3 九文件定向矩阵：`9` 个文件、`155/155`；全量 `npm test`：`73` 个文件、`708` 个测试；`npm run build` 通过（仅保留既有大 chunk warning）；`git diff --check` 及未跟踪范围文件空白、冲突标记、非预期 secret sentinel 和 Adapter import 边界检查通过。
- 本轮新增的受信 Context 对抗测试把 `petId` 与已提供的 `contextEpoch` 绑定到当前 Turn；旧 `send()` 兼容入口与新 `CompanionModelPort` 都会在 Adapter/fetch 前拒绝跨宠物或 epoch 不匹配的上下文。Provider Resolver 读取安全存储异常时只返回静态安全错误，不回显底层错误或 credential sentinel。
- 本轮仍未接入 `App.tsx`，未开始 Phase 4，未执行真实 Action / Memory 写入、真实 Provider 网络冒烟、Tauri 实机或视觉 QA；未修改 Rust，无 Cargo 证据；未 commit、push 或发布。

### Phase 3 P1 最终收口复核（2026-08-11）

- per-Turn Provider Snapshot 合同：`CompanionModelPort` 构造阶段不解析 Resolver；有效 Turn 通过 `beginTurn()` 只解析一次，并返回冻结的 `ResolvedCompanionModelTurn`，其中 `adapter`、复制冻结的 `info`、复制冻结的 `capabilities` 和捕获该 Adapter 的 `generate()` 同源。Harness 在该 Turn 的隐私门禁、Context 路径、trusted Context 检查、调用计数、远程上限、fallback、错误与最终披露中只使用该 snapshot；下一 Turn 才读取 Provider 新配置。兼容 `port.generate()` 也只创建一个自己的 snapshot，不使用动态 `info` getter。
- Snapshot 对抗测试已覆盖：构造时不解析；Local→Remote（Remote Adapter 1 次、external=1、local=0、Remote disclosure）；Remote→Local（Remote Adapter/fetch=0、external=0、local=1、Local disclosure）；Turn 中途切换保持旧 snapshot、下一 Turn 使用新 Provider；不同 Provider 下两个并发 Session 的结果、metadata、计数与 disclosure 互不污染；Remote 失败后只解析一次 Local fallback，external=1、local=1、fallback=1，且 fallback 非 Local 时在调用前 fail closed。
- Fail-closed 对抗测试已覆盖敏感输入、不受信 Context、`petId` / `contextEpoch` 不匹配：Adapter generate 与 fetch 均为 0，返回安全分类，不把 Context、credential 或 sentinel 带入响应。
- 完整 response body 生命周期：`fetchJsonWithTimeout()` 用同一个 `AbortController` 和 timeout 覆盖 fetcher、响应头和 `response.json()`；成功必须消费 body 后才清理 timer/listener/controller。`json()` 执行时 signal 保持未 abort；body 延迟但在期限内完成可成功；body 永不完成分类为 `timeout`；body 等待期间 parent abort 分类为 `cancelled`；普通 JSON 解析失败为 `malformed-response`；HTTP 401/403/429/500 即使错误 body 非 JSON 仍按 HTTP 分类。每个场景 fetcher 只调用一次，未回显底层异常或凭据。
- 真实验证证据：第一组定向命令 `5` 个文件、`80/80`；第二组定向命令 `9` 个文件、`172/172`；全量 `npm test` 为 `73` 个文件、`725` 个测试；`npm run build` 通过（仅保留既有大 chunk warning）；本轮文档变更后的 `git diff --check` 通过（Git 仅提示既有工作区文件的 LF/CRLF 转换 warning）。
- 范围与未验证项：本轮没有进入 Phase 4，没有接入 `App.tsx`，没有修改 Task / Reminder / Memory 执行、Action Pipeline、ResponseFinalizer、宠物资源、Live2D、Rust 或发布产物；没有真实 Provider 网络冒烟、真实 API Key、App 接线、Tauri 实机、视觉 QA、`cargo test` / `cargo check`、commit、push 或发布验证。未创建临时交付文件；构建产生的 `dist/` 仅为既有构建输出目录。

### Phase 4：Action Pipeline 与 ResponseFinalizer

目标：把“候选”和“真实执行”彻底分开，消灭虚假成功。

- [x] Action discriminated union 至少覆盖 `create_task`、`create_reminder`、`complete_task`、`update_reminder`。
- [x] 将现有 `cancel`、`postpone`、`reschedule` 保留为受控本地兼容动作；主动提醒偏好独立为 Harness-owned 本地领域请求，不进入 ActionCandidate / Model Codec / Provider Schema；未授权模型不能借未知 Action 名称调用这些本地能力。
- [x] Candidate 必须携带原始 source message id、明确性、时间信息和可验证目标；Provider 给出的 `intent: explicit` 不能单独作为自动执行依据。
- [x] `ActionPolicy` 同时检查：本地明确意图证据、Schema、隐私、时间、权限、业务规则、目标唯一性、重复和取消状态。
- [x] `create_task` / `create_reminder` 复用 `taskDraftFromCandidate()`、`createTask()`、`writeTaskDatabase()` 和现有重复检测。
- [x] `complete_task` 复用 `findTaskReference()` / `completeTask()`；模型提供的 task id 或标题都必须在当前活动 Task snapshot 中重新解析。
- [x] `update_reminder` 映射到现有 Task/Reminder 改期能力；过去时间、缺时区、模糊时间、无目标和多目标必须拒绝或要求确认。
- [x] 所有 Handler 只调用现有事实源；不得直接操作 React state 作为成功依据。
- [x] Action 幂等键至少绑定 session/message/action type/规范化目标；重试、双击或相同模型候选不得重复创建。
- [x] `ResponseFinalizer` 使用本地模板处理 Action 结果，不再请求模型。
- [x] Action-bearing Turn 在失败、歧义、拒绝或取消时必须覆盖 draft 中任何“已经完成”表述；不能只在后面追加一句失败说明。
- [x] 写入成功后再生成成功文案；写入失败时 UI、pending state 和 Task/Reminder 状态保持可恢复。

验收门：

- [x] 明确低风险提醒成功创建；模糊表达不自动创建；过去时间拒绝；重复提醒不重复写入。
- [x] complete/update 的目标不存在或不唯一时不修改数据库。
- [x] 领域写入失败、Provider 乱报成功、取消和迟到候选的“虚假成功确认”均为 0。
- [x] 每个支持 Action 同时断言最终文案、数据库事实和 Provider 调用次数。

### Phase 4 实施记录（2026-08-11）

- 进度：实施项 `12/12`；验收门 `4/4`。本记录只覆盖 Phase 4 纯逻辑 Action Pipeline 与 ResponseFinalizer，不代表 App 已接线或 Phase 5--8 已完成。
- 新增/修改：`src/pet-core/companionActionTypes.ts`、`companionActionPolicy.ts`、`companionActionPipeline.ts`、`companionResponseFinalizer.ts`、`companionPrivacy.ts`；收紧 `companionHarnessTypes.ts`、`companionModelCodec.ts`、`companionHarness.ts`；新增 `companionProactivePreference.ts`；新增/扩展对应 Pipeline、Harness、Codec、Finalizer、主动偏好和联合验收测试，并调整 Phase 1 Action fake 使用正式四类合同。
- Action 合同：模型 Envelope 仅允许 `create_task`、`create_reminder`、`complete_task`、`update_reminder`；每种 payload 与 `additionalProperties: false` Schema 均为 discriminated union。`cancel_task`、`postpone_task`、`reschedule_task` 仅作为本地兼容 union，不进入 Codec/Provider Action 名单。
- 唯一所有权：Harness 先重跑 `resolveCompanionChatPipelineRoute()` 及现有 Task Extractor；明确低风险 Task/Reminder 在 Provider snapshot 前执行，成功路径 `model=0/external=0`。模型 intent/evidence 不填充 Local Evidence；ActionPolicy 在 Schema、隐私、时间、时区、目标状态、重复和幂等检查任一失败时 fail closed。
- 主动提醒偏好唯一所有权：`mute`、`reduce`、`switch_pet` 复用 `parseProactivePreferenceCommand()`、`resolveProactiveTaskControlTarget()`、最近一次主动投递上下文、既有 TaskDatabase 和 Trigger Engine `setTaskPreference()`；通过注入的本地服务执行一次写入，不创建第二套偏好 Store，不进入四类模型 Action 合同。唯一目标、缺失/多目标、无最近上下文、无可切换宠物、依赖缺失、写入失败和取消分别返回真实的本地结果，并在所有这些路径保持 Provider / model begin / model generate 为 `0`。
- 事实与幂等：Handler 通过注入的 `CompanionTaskRepository.read/write` 使用现有 `readTaskDatabase()`、`writeTaskDatabase()`、`createTask()`、`updateTask()`、`completeTask()`、`taskDraftFromCandidate()`、`findTaskReference()`、`findDuplicateTask()` 和 `applyCompanionTaskOperationToDatabase()`；Handler Registry 串行执行，成功写入后才记录 `sessionId + sourceMessageId + action type + 规范化目标/时间` 幂等键。未引入第二套 Task/Reminder Store。
- 文案与长回复联合断言：ResponseFinalizer 完全本地且 `0` 次模型调用；Action-bearing Turn 忽略模型成功 draft，依据 `succeeded/duplicate/not_found/ambiguous/confirmation_required/rejected/failed/cancelled` 逐项生成诚实文案。普通无 Action 回复单独保留 Harness/Codec 已校验的最长 `2000` 字符，不再套用 Action 展示字段的 `120` 字符上限；Action 的 title/reference/triggerTime 继续严格限长和敏感过滤。写入失败、Handler throw、Policy reject、取消和 stale/late Turn 均不产生虚假成功文本；写入成功后取消保留数据库事实且阻止迟到 UI commit。
- 验证证据：`companionPhase4Acceptance.test.ts` 以同一场景联合覆盖 `create_task`、`create_reminder`、`complete_task`、`update_reminder`、`cancel_task`、`postpone_task`、`reschedule_task` 的最终文案、ExecutionResult、Task/Reminder/ReminderInstance 事实、Provider begin/generate、写入次数、重试/equivalent candidate 幂等、取消前不写和写入后迟到 UI commit；`companionProactivePreference.test.ts` 覆盖 mute/reduce/switch_pet、唯一/缺失/多目标、最近上下文、重试/双击、依赖缺失、写入失败、取消和 Provider 零调用；`companionResponseFinalizer.test.ts` 覆盖 121/2000 字符保留、超限/空回复 fail closed、Action-specific 文案和敏感展示过滤；`companionModelCodec.test.ts` 覆盖超限 malformed fail closed 及未知主动偏好 Action 不进入 Codec 合同。Phase 4 六文件定向组为 `111/111`；Harness / Codec / Task Extractor / Task Store / Proactive / Action 相关扩展定向组为 `12` 个文件、`194/194`；最终全量 `npm test` 为 `77` 个文件、`794` 个测试全部通过；`npm run build` 通过，仅有既有大 chunk warning。
- 未完成/未验证项：本轮未接线 `App.tsx`，未实现 Phase 5 Memory Candidate Policy，未开始 Phase 6 Proactive Event、Phase 7 App 收敛或 Phase 8 发布门禁；未接真实 Provider 网络/API Key，未做 Tauri 实机和视觉 QA，未做 Rust/Cargo 验证，未 commit、push 或 release。`update_reminder` 的正常 Task-bound Handler、主动提醒偏好和 ResponseFinalizer 均已有纯逻辑证据；真实 App 入口与未来明确 recurring-instance UI 解析仍留待后续阶段。

### Phase 4 P1 最终收口（2026-08-12）

- 状态：两个 P1 已修复并完成真实 storage 竞态复验；Phase 4 实施项 `12/12`、验收门 `4/4` 通过。此结论只覆盖纯逻辑 Action / ResponseFinalizer / 主动提醒偏好，不代表 App 接线或后续 Phase 已开始。
- Offset 约定已冻结：`CompanionInput.utcOffsetMinutes` 表示“当地时间减 UTC”（Asia/Shanghai `+480`、America/Los_Angeles 夏令时 `-420`）；旧 `TaskExtractorOptions.timezoneOffsetMinutes` 与 `TaskDatabase.settings.timezoneOffsetMinutes` 保留 JavaScript `Date#getTimezoneOffset()` 的“UTC 减当地时间”约定（上海 `-480`、洛杉矶夏令时 `+420`）。Harness 只在 `toLegacyTaskExtractorTimezoneOffsetMinutes()` 适配边界转换，不修改旧 Extractor / TaskDatabase 约定。
- 已检查 `buildLocalRequestHints()`、`TaskCandidate` / `TaskOperationCandidate` 构造、`localOperationFromCandidate()`、duplicate candidate、`currentLocalDateKey()` 和 create/update/postpone/reschedule Handler 输入；`currentLocalDateKey()` 继续直接使用 Harness 的当地时间减 UTC 约定，旧 offset 不再被直接赋给旧 Extractor。
- 精确时区证据：上海 `currentTime=2026-08-11T12:00:00.000Z`、`timezone=Asia/Shanghai`、`utcOffsetMinutes=480`，“明天下午四点”得到 `2026-08-12T08:00:00.000Z`，最终本地显示为 `8/12 16:00`（8 月 12 日 16:00）；UTC `utcOffsetMinutes=0` 得到 `2026-08-12T16:00:00.000Z`；洛杉矶 `currentTime=2026-08-12T06:30:00.000Z`、`utcOffsetMinutes=-420`（本地 8 月 11 日 23:30）下，“今天晚上十一点”得到 `2026-08-12T06:00:00.000Z` 并按过去时间拒绝，“明天早上八点”得到 `2026-08-12T15:00:00.000Z`，最终本地显示 `8/12 8:00`，日期-only “明天”得到 `2026-08-12`。
- writer 合同已冻结：`setProactiveTaskPreference()` 先计算 candidate，再调用现有 `writeProactiveExpressionState()`；只有其返回 `true` 才返回该 post-write state，返回 `false` 时抛出明确的 `ProactivePreferencePersistenceError`。因此服务层只把 writer 已确认的 state 当作 authoritative persisted state；writer 抛错或防御性 state 校验失败均为 `failed`，不会被 late abort 改写为成功。验证 read 抛错时保留已由 writer 确认的成功事实。
- 真实竞态矩阵已覆盖：A 写入前取消时 `setTaskPreference=0`、storage 写入不增加、Provider/model=0；B 实际 `storage.setItem()` 抛错时领域 `failed`、原偏好不变、无成功文案；C 实际 storage 抛错且 writer wrapper 在 `finally` abort 时仍为领域 `failed`，顶层 `cancelled`、`committed=false`、UI commit=0、无成功文案；D 实际写入成功后立即 abort 时领域 `succeeded`、顶层 `cancelled`、`committed=false`、UI commit=0，独立读取可见目标偏好；E 新 requestId 重试为 `duplicate` 且不增加写入；F writer 确认成功但 verification read 抛错仍保留 `succeeded`，独立 storage 读取可见目标偏好。A--F 的 Provider/model/external 调用均为 `0`。
- 新增/强化测试：`matrix A: aborts before the writer without invoking storage or Provider`、`matrix B: reports failed when the real storage writer throws`、`matrix C: keeps a storage failure failed when the writer aborts in finally`、`matrix D ... matrix E ...`、`matrix F: keeps writer-confirmed success when verification read fails`，并增加 Trigger Engine writer rejection 的直接断言；A 直接断言实际 `setTaskPreference()` 调用为 `0`，B--F 覆盖实际 writer 调用、storage 原始事实、写入次数、领域/顶层状态、UI commit、成功文案和 Provider/model 调用次数。
- 本轮验证：目标要求的 Phase 4 定向组 `7` 个文件、`127/127`；全量 `npm test` 为 `77` 个文件、`800` 个测试全部通过；`npm run build` 通过，仅保留既有大 chunk warning。
- 范围与未验证项：本轮未修改 `App.tsx`，未实现 Memory Candidate Policy，未开始 Phase 5--8；未接真实 Provider/API Key，未做 App 接线、Tauri 实机、视觉 QA、Rust/Cargo、commit、push 或 release。上述纯逻辑测试和构建不等同于运行时或可发布验证。

### Phase 5：Memory Candidate Policy

目标：在同一模型响应中接收候选，但继续遵守当前显式/确认写入契约。

- [x] Candidate 增加 source/evidence、scope、candidate category、lifetime、expiresAt、confidence、importance、explicitness 和 confirmation 状态。
- [x] Candidate 直接使用现有 `global` / `pet:<activePetId>` 作用域；模型不得指定另一只宠物的关系作用域，也不得引入 `user_global` / `pet_relationship` 第二套持久化值。
- [x] 将 PRD category 映射到现有持久化类型：profile/person/project/goal -> fact，event -> episode，preference -> preference，宠物共同经历 -> relationship。
- [x] 只有当前输入明确要求“记住”或用户确认后的候选才可保存；普通聊天推断、情绪、假设、敏感信息和模型自行提高 confidence 均不落盘。
- [x] 在 `MemoryPolicy` 中实现规范化、隐私检查、scope 检查、精确/近似重复、冲突、temporal 过期和 insert/update/ignore 决策。
- [x] 冲突只有在当前用户明确纠正或确认时才能 supersede/update；模型不能凭自己的推断覆盖旧事实。
- [x] 复用现有 `MemoryRepository`、Tombstone、Outbox 和删除保护；不创建第二个 Memory Store。
- [x] Memory 保存失败不阻塞正常聊天或已完成 Action，但必须给出诚实且不含原文的安全结果。

验收门：

- [x] 覆盖 global、pet relationship、duplicate、conflict、temporal expiration、敏感拒绝和保存失败。
- [x] “我今天好累”不保存；“我喜欢桂花茶，请记住”只保存一条；跨宠物关系不泄漏。
- [x] Memory Candidate 数量不能改变本轮 Provider 调用次数。

### Phase 5 基础实施记录（2026-08-12，已由 P1 最终收口记录取代）

- 进度：这是 P1 最终收口复验前的基础实现记录，不作为当前 Phase 5 最终通过数字。本轮只完成 Memory Candidate Policy 纯逻辑实现与验收，没有进入 Phase 6。
- Candidate/Codec：收紧 `MemoryCandidate` 合同，加入 source/evidence/sourceMessageId、scope、category/candidateCategory、lifetime/expiresAt、confidence/importance、explicitness 和 confirmationStatus；Schema 使用 `additionalProperties: false`、枚举/长度/数量/有限数值范围，并拒绝跨消息、跨宠物、category/type 不一致、非法 ISO、敏感字段和矛盾布尔确认。非法候选按原始 index 丢弃，不补发 Provider 请求；text-only 回复不猜测 Memory。
- MemoryPolicy：模型字段只作为候选，不构成授权；Policy 重新分析当前 `CompanionInput.message` 的本地显式“记住”证据，或接受由注入式 verifier 绑定当前确认消息、原 sourceMessageId、稳定候选 id、session/pet 的可信 proof。类别在本地映射为现有 `fact` / `episode` / `preference` / `relationship`，关系只写当前 `pet:<input.petId>`，不创建第二个 Store。
- 领域与持久化：使用现有 `MemoryRepository`、`yuxin-companion-memory-v1`、Tombstone 和 Local Repository journal/Outbox；新增同一 `writeState` 事务内的 atomic `supersede`，冲突替换失败时旧事实保持 active。精确/保守近似 duplicate 不新增 Outbox，过期 temporal 不参与写入、重复或冲突，删除后的 Tombstone 不可被重试复活。Outbox 只保留安全投影，不含敏感信息、完整聊天、原始 evidence 或错误文本。
- Harness/Finalizer：明确本地 Memory 路由先于 Provider snapshot，Provider begin/model/generate/external 均为 `0`；普通远程回复的 `0/1/4` 个候选共用一次模型响应和一次远程调用。真实 Memory 写入成功后才报告 succeeded；保存失败只使领域结果 failed/degraded，不撤销已成功 Action；模型伪造“已经记住”由本地结果覆盖；cancelled/stale 不提交 UI 文案，写入成功后的 late abort 保留领域事实但 `committed=false`，重试得到 duplicate。
- 验证证据：这是 P1 复验前的基线结果；最终数字与 P1-A 至 P1-D 的新增对抗证据见下方收口记录。
- 范围声明：本轮未触碰 `App.tsx` 的旧 Memory 分支，未做 App 接线或 Phase 6--8；未接真实 Provider/API Key，未做 Tauri 实机、视觉 QA、Rust/Cargo、commit、push、package 或 release。纯逻辑测试和 Web 构建不等同于真实 Provider、Tauri 或可发布验证。

### Phase 5 P1 最终收口（2026-08-12）

- 状态：P1-A 至 P1-D 已完成实现并复验；Phase 5 实施项 `8/8`、验收门 `3/3` 恢复为已通过。本记录仍只覆盖纯逻辑 Memory Candidate Policy，不代表 App 接线或可发布完成。
- P1-A 容量边界：`supersede()` 在任何 Repository 写入前检查 `MAX_COMPANION_MEMORY_ENTRIES=200`；`198 -> 199`、`199 -> 200` 成功，`200 -> supersede` 返回失败。失败时旧事实仍为 active，主记录、Outbox、journal、删除守卫和 sync counter 均不变；原始状态不超过 200 条，重新创建 Repository 后 200 条仍可读。
- P1-B 冲突槽位：Preference 使用规范化对象和正/负极性，覆盖 `喜欢/不喜欢`、`爱吃/不吃`、`爱喝/不喝`、`爱/不爱` 等现有 extractor 表达；Profile name 统一为 `profile:name`，支持“我叫”和“我的昵称是”。同对象反极性、同 profile 槽位不同名字才 supersede；同极性等价表达为 duplicate，咖啡/茶、香菜/芹菜、不同 person/project/shared experience 不误判。只有当前输入 explicit 或可信 confirmation proof 才能更正。
- P1-C 身份与版本：Candidate confirmation 使用不回显原文的 SHA-256 opaque fingerprint；Memory Entry 使用独立、由 candidate fingerprint 与 `supersedesId` 派生的 revision id。Repository 对相同 ID 的不同 scope/type/content fail closed，正常重试不新增写入，删除 Tombstone 不复活；已知 32 位碰撞对 `用户我叫i6adqy1cr8o0r` / `用户我叫1jpie37tfrvh` 得到不同 Candidate ID。`A -> B -> A` 生成不同 revision，最终只有最后一个 A active，且每次 `supersedesId` 正确指向前一版本。
- P1-D 混合结果：Finalizer 按 inserted/superseded/updated、duplicate、confirmation_required、failed、rejected、expired 分别计数；例如 `1 inserted + 1 confirmation_required` 为“已记住 1 条；另有 1 条尚未保存，需要你确认。”，`1 inserted + 1 failed` 为“已记住 1 条；另有 1 条保存失败。”。Action 成功文案保留，Memory failed 使顶层 degraded；模型 draft 不再覆盖逐项本地结果，也不回显 candidate content、evidence、sourceMessageId 或底层错误。
- 验证证据：Phase 5 定向组为 `8` 个文件、`160/160`；全量 `npm test` 为 `79` 个文件、`844/844`；`npx tsc --noEmit` 通过；`npm run build` 通过，仅保留既有 Vite 大 chunk warning；最终 `git diff --check` 通过。新增证据覆盖 200 条容量和重启、Outbox/journal/delete guard 稳定性、Preference/Profile conflict slot、已知碰撞对、A→B→A revision chain、Tombstone、ID collision fail-closed、mixed-result Finalizer 和 Action+Memory partial success。
- 范围声明：没有进入 Phase 6；没有修改 `App.tsx`、真实 Provider、Tauri/Rust、Live2D、宠物资源或发布产物；没有 commit、push、package 或 release。纯逻辑测试、类型检查和 Web 构建不等同于真实 Provider、Tauri 实机或可发布验证。

### Phase 6：Proactive Event 适配

目标：让 Harness 接管“允许后的表达”，不接管或复制 Scheduler。

- [x] 将现有 `TriggeredReminder` / due-soon candidate 适配为带稳定 id 的 `REMINDER_DUE` / `TASK_DUE_SOON` 事件。
- [x] 复用 `proactiveTriggerEngine.ts`、`proactiveExpressionGate.ts`、`proactiveDelivery.ts` 的勿扰、冷却、每日上限、聚合、幂等、忽略退避和宠物路由。
- [x] 明确 formal system notification、Task reminder stack 和宠物主动表达的职责，避免同一事件被当成两个新事实或重复气泡。
- [x] 默认使用宠物包本地模板，0 API；没有 Provider 也能提醒。
- [x] V1 不接 AI Enhanced Provider 路径；如已有相关设置，仅保留不外发的兼容读取与用户说明，未来非 Task / Reminder 事件必须另行修订 PRD、隐私合同和测试后才能启用。
- [x] Task/Reminder 触发的主动表达在 V1 始终使用本地模板；即使用户开启 AI Enhanced，也不发送任务标题、时间、状态或其他 Task/Reminder 投影，不为此发起远程调用。
- [x] 主动 AI 响应中的 Action / Memory Candidate 一律忽略；主动表达不能创建任务、改设置或绕过用户关闭状态。
- [x] Provider 失败时回到本地文案，不影响 Reminder 的 triggered / handled 事实，不重复触发。

验收门：

- [x] 覆盖正常到期、due soon、重复事件、DND、关闭主动、每日上限、聚合、App Restart、Sleep/Resume 和目标宠物不可用。
- [x] 所有 V1 主动事件外部调用数为 0，且每个有效事件只投递一次本地表达。

### Phase 6 实施记录（2026-08-12）

- 状态：这是 P1 收口前记录；既有实施项 `8/8` 与验收门 `2/2` 仅表示原始实现基线，暂不作为 Phase 6 最终通过证据。本记录只覆盖 Phase 6 纯逻辑主动事件适配，不代表 App 已接线、Tauri 已运行或已进入 Phase 7。
- 独立行为探针随后复现了 P1-A 至 P1-E：不同事件并发可绕过全局门禁、超过 256 条确认后幂等失效、eligible fallback 伪造 `lastDeliveryContext`、唯一 Harness 入口丢失聚合/宠物路由，以及 legacy `evaluate/deliveries` 被固定为空。P1 全部闭环前不得恢复本记录的最终状态或开始 Phase 7。
- 事件与边界：新增严格的 `CompanionEvent` 联合（`REMINDER_DUE`、`TASK_DUE_SOON`），通过 `companionProactiveEvent.ts` 生成基于 Reminder/Instance 或 Task/规范化 scheduledAt 的稳定 SHA-256 id；解析器拒绝未知字段、非法时间窗口和不完整事件。`CompanionHarness.handleEvent()` 只转发合法事件到注入的本地主动事件服务，不创建聊天 Turn，不调用 `CompanionModelPort`，不生成 Action/Memory Candidate。
- 唯一所有权：`Scheduler`/既有 Task Store 继续负责 ReminderInstance 的 triggered/missed/handled 事实；formal system notification 与 `TaskReminderStack` 继续负责可操作提醒；Phase 6 服务只负责一次非操作型宠物表达。没有新 Task/Reminder/Proactive 事实源，也没有修改 `App.tsx`、Provider 或 Tauri/Rust。
- 投递事务：策略评估只产生 `eligibleDeliveries`，不再把允许误报为已投递；`reserveDelivery()` 先写入持久化 reservation，随后才调用本地 sink；只有 sink 明确返回 `true` 才由 `confirmDelivery()` 增加计数、记录 delivered key 和 last delivery context。失败、异常、不可用宠物、重复、重启和确认写失败均 fail closed，并保留可恢复/不可重复的 reservation 语义。
- 本地降级：任务/提醒事件始终使用宠物包本地 `TaskFeedbackPackage`，不向 Provider 或远程 Context 发送 Task/Reminder 投影；模板读取失败时使用安全本地文案。AI Enhanced、远程 Model、Action、Memory 的 throwing spy 联合测试均保持 `0` 次调用。
- 验证证据（P1 收口前基线，非最终通过证据）：`companionProactiveEvent.test.ts` 覆盖稳定 id、正常/due-soon、重复、DND、关闭主动、每日上限、聚合、App Restart、Sleep/Resume、目标宠物不可用、writer/sink/confirmation failure 和外部调用隔离；Phase 6 相关定向组为 `8` 个文件、`152/152`；全量 `npm test` 为 `80` 个文件、`855/855`；`npx tsc --noEmit` 和 `npm run build` 均通过，仅保留既有 Vite 大 chunk warning。新增 P1 对抗测试与最终数字待收口后补录。
- 范围声明：未修改 `App.tsx`，未接真实 Provider/API Key，未做浏览器/Tauri 实机、视觉 QA、Rust/Cargo、commit、push、package 或 release。纯逻辑测试、类型检查和 Web 构建不等同于 App/Tauri 运行时或可发布验证；P1-A 至 P1-E 全部通过前不得开始 Phase 7。

### Phase 7：App 接线与旧分支收敛

目标：Harness 成为唯一聊天编排入口，同时保留现有桌宠体验。

- [ ] 在纯逻辑阶段验收后，把 `App.tsx` 的聊天发送大分支收敛为构造 `CompanionInput`、调用 Harness、渲染 `CompanionResponse`。
- [ ] React 继续负责气泡、输入、pending、停止、重试、Session UI 和 Provider 披露；领域判断、Provider 调用、Action/Memory 执行迁出组件。
- [ ] 保留 `companionChatRuntime.ts` 的现有状态机与 90 秒退出规则，不重写聊天交互。
- [ ] 保留当前运行时会话列表行为；本阶段不把完整原始聊天写入长期 Repository。
- [ ] 切宠物时切换 Soul 和 `pet:<id>` Memory，取消旧 Turn；Task 仍为用户级唯一事实，`createdByPetId` 只作 provenance。
- [ ] 远程失败允许一次已披露的本地降级；不能在本轮继续偷偷请求远程 Provider。
- [ ] 接线完成后删除/收敛 App 内重复编排分支，不能长期同时保留两条会产生副作用的执行路径。
- [ ] Provider 设置、连接测试、系统安全存储和现有兼容迁移不因 Harness 改写。

验收门：

- [ ] 本地聊天、远程 text-only、远程 structured、明确 Task/Reminder、确认、Memory、forget、主动偏好、停止、重试、换宠物全部走唯一 Harness 入口。
- [ ] 退出、停止、换宠、超时和新请求覆盖旧请求均无幽灵回复或迟到副作用。
- [ ] 用户切 Provider 后 Soul、Preference、Memory、Task、主动设置和当前宠物身份不迁移、不丢失、不重复。

### Phase 8：可观测性、评测与发布门禁

- [ ] 只记录脱敏后的 request id、provider profile id、protocol、latency、call count、action type/result、memory candidate count、event type/decision 和 error kind。
- [ ] 不记录完整 Prompt、用户消息、Memory content、Task note/evidence、API Key、原始 Provider body 或完整模型回复。
- [ ] 建立固定评测集，至少覆盖普通陪伴、明确/模糊任务、提醒创建/改期、完成任务、记住/忘记、冲突 Memory、敏感内容、Provider 故障、取消和主动提醒。
- [ ] 每个评测同时检查三层：用户最终文案、领域事实、外部调用/隐私副作用。
- [ ] 将 Task/Reminder 远程零外发作为独立隐私矩阵：相关、近期到期、无关、完成/取消、软删除/物理删除和主动提醒均不得把本地事实放进请求体。
- [ ] 为 Local、Gemini-native、OpenAI-compatible 跑相同的领域中立 Provider Adapter 合同测试，并单独运行 `CompanionModelPort` / Model Codec 合同测试；真实远程冒烟只在用户已经主动配置凭据后执行，不进入 CI，不记录正文。
- [ ] 运行 Harness 相关测试、现有 Companion/Memory/Task/Proactive/Provider 回归、全量 `npm test`、`npm run build`、`cargo test`、`cargo check` 和 `git diff --check`。
- [ ] Tauri 实机验证本地完整路径；涉及聊天 UI 改动时检查正常显示尺寸与 2x 显示尺寸。
- [ ] 更新 README、正式数据契约和旧路线状态，明确支持能力、降级、隐私、未实现项和 Harness 已接管的入口。

## 6. V1 最终验收指标

| 指标 | 通过标准 | 证据 |
|---|---:|---|
| 普通远程聊天外部请求 | 每 Turn `<= 1` | Fake Provider 计数 + Adapter 合同测试 |
| 可本地完成的明确操作 | 外部请求 `= 0` | Task/Memory 集成测试 |
| V1 主动提醒外部请求 | 每事件 `= 0` | Proactive 测试 |
| 明确 Task / Reminder 操作成功率 | 支持语料集 `>= 95%` | 固定中文 fixture 报告 |
| 虚假成功确认 | `0` | Provider 乱报 + 各类领域失败矩阵 |
| 重复 Reminder / Action 写入 | `0` | 重试、双击、重复候选、重启 fixture |
| 业务层直接依赖具体厂商 | `0` | import/协议边界检查 |
| Provider Adapter 依赖 Harness / Task / Memory / Soul 领域类型 | `0` | import/类型边界检查 |
| 本机 Task / Reminder 事实或投影进入远程请求 | `0` | Context fixture + 双协议请求体快照 |
| 敏感 Context / Key 泄漏 | `0` | 请求快照、日志快照与隐私 fixture |
| 取消后的新副作用 | `0` | Abort / stale request 集成测试 |

## 7. 硬停线条件

出现以下任一情况时，不得进入下一 Phase，也不得宣称 Harness 已完成：

- 同一用户输入可能同时由旧 App 分支和 Harness 执行副作用。
- 普通聊天为了 Action、Memory、Finalizer 或自检发生第二次模型调用。
- 新建了第二套 Task、Reminder、Memory 或 Proactive 事实源。
- 模型输出未经本地明确意图、Schema、权限和领域验证就触发写操作。
- Action 失败或持久化失败后仍出现成功文案。
- 停止、换宠或退出后，迟到响应仍可写 Task / Memory / UI。
- Context 或日志中出现 Key、完整敏感字段、完整 Prompt 或未裁剪原始历史。
- 以相关、近期到期、优先级或主动提醒为理由，把任何本机 Task/Reminder 事实或投影放入远程 Context。
- Provider Adapter 增加 Action/Memory 领域能力标记，或直接依赖 Harness、Task、Memory、Soul 类型。
- 任一 V1 主动事件绕过 Proactive Gate，或产生 Provider 调用。
- 只通过单元测试而没有 App/Tauri 真实运行证据，却把状态写成可发布。

## 8. 建议的第一开工单元

第一轮只完成 Phase 1，不同时接 App、不改 Provider 协议、不动 Task/Memory schema：

1. 增加 Harness types 与依赖接口；
2. 实现纯 `respond()` 单次生命周期；
3. 用 Fake `CompanionModelPort` 验证 0/1 次调用、取消、超时、迟到结果和本地降级；
4. 通过 Phase 1 验收门后，再进入 Context Budget。

这样第一轮就能得到可验证的编排核心，同时不会碰用户当前未提交的 UI、宠物资产、发布产物或 Live2D 工作线。

## 9. 输入文档指纹

- `Companion Harness PRD.md`：SHA-256 `5B77EE7D981313263375198F7A0475C970E5F17E03802592815491AD3C3B7E96`
- `Companion Harness Technical Design.md`：SHA-256 `533160387A92B852B4D8FF49D250781F5A80D7E97346DF738E9DD210A1992CD2`

后续如果输入文档变化，先对比指纹并重新审查受影响条目，不默认沿用旧结论。
