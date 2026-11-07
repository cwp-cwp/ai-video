# 接口手册（自包含）

> 本文件是这套系统的**完整接口参考**，不依赖任何外部文档。所有字段、坑位都经过源码或实测核对。

---

## 通用约定

| 项 | 说明 |
|---|---|
| Base URL | 便携版 `http://localhost:18080/video-service/api`；本地开发 `http://localhost:8090/api`；线上 `https://<域名>/video-service/api` |
| 认证 | 每个请求带 **`X-Token: <token>`**（不是 `Authorization: Bearer`） |
| 响应包装 | `{"code":200,"msg":"success","data":...}` |
| 成功判定 | **`code` 为 200 或 0 都算成功**（文档写 0，实测返回 200）；其余一律失败 |
| 时间格式 | `yyyy-MM-dd HH:mm:ss`（字符串） |
| 分页 | `?page=1&size=20`（仅 `/list` 的分页版接口） |
| 文件地址 | 返回的 `imageUrl`/`videoUrl` 是可直接访问的绝对 URL |
| 异步任务 | 立即返回 `taskId`，用对应 `/task/{taskId}` 轮询（见第 11 节） |

命令行客户端（推荐，省掉手写 curl 与轮询）：

```bash
python <skill>/scripts/drama.py login --base <base> --email a@b.c --password xxx
python <skill>/scripts/drama.py get project/list           # 路径不要带前导斜杠
python <skill>/scripts/drama.py post storyboard/save/9 --json '{...}'
python <skill>/scripts/drama.py wait storyboard <taskId>
```

---

## 1. 认证

| 方法 | 路径 | body | 返回 |
|---|---|---|---|
| POST | `/auth/login` | `{email,password}` | `{id,email,nickname,avatar,token}` |
| POST | `/auth/register` | `{email,code,nickname,password}` | 同登录 |
| POST | `/auth/send-code` | `{email}` | - |
| GET | `/auth/me` | - | 当前用户 |

> Token 有效期约 7 天；响应头 `X-New-Token` 会做滑动续期，脚本已自动处理。

---

## 2. 项目与分集

| 方法 | 路径 | body / query |
|---|---|---|
| GET | `/project/list` | 当前用户全部项目 |
| GET | `/project/{id}` | 项目详情 |
| POST | `/project/create` | `{name,description,type,visualStyle,imageSize,parentId}` |
| PUT | `/project/update/{id}` | 同上（不传的字段会被覆盖成 null，先 GET 再改） |
| DELETE | `/project/delete/{id}` | - |
| PUT | `/project/{id}/step` | **裸整数**，如 `3`（不是 `{"currentStep":3}`） |
| **GET** | **`/project/{parentId}/children`** | 分集列表 |
| **POST** | **`/project/{parentId}/children`** | **`{"name":"第1集 xxx"}` → 返回子项目** |
| DELETE | `/project/children/{id}` | 删除某一集 |

### 创建项目的枚举（必须传原值）

`type`：`连续剧` · `AI短剧` · `AI长视频`

`visualStyle`（13 项）：
`真人写实` · `日系动漫` · `3D国风动漫` · `神话仙侠` · `卡通` · `油画` · `水彩` · `像素风` · `赛博朋克` · `古风` · `奇幻` · `电影感` · `其他风格`

`imageSize`（5 项）：
`16:9` 横屏 · `9:16` 竖屏 · `1:1` 方形 · `4:3` 传统 · `3:4` 竖版

### 项目对象（主要字段）

```
id, userId, name, description, type, currentStep,
novelContent, novelGenre, novelLength, novelModel,
scriptContent, scriptModel, storyboardContent,
visualStyle, imageSize, videoWorkflow, parentId, episodeNumber,
createTime, updateTime, deleted
```

> ⚠️ **连续剧流程有固定顺序：建项目 → 建分集 → 写内容**。
> 父项目只是容器，页面不显示它的剧本/分镜/视频。**没建分集之前不要写任何内容**（小说/剧本/分镜一律用分集 id）。
> 资产父子共享（用分集 id 查询会自动带出父 + 全部分集），剧本/分镜/视频则是 per-project。

---

## 3. 小说

| 方法 | 路径 | body | 返回 |
|---|---|---|---|
| PUT | `/novel/save/{projectId}` | `{"content":"全文"}` | - |
| GET | `/novel/content/{projectId}` | - | `{content,genre,length}` |
| POST | `/novel/generate/{projectId}` | `{genre,length,requirement}` | `taskId` |
| POST | `/novel/generate/stream/{projectId}` | 同上 | SSE 流 |

> ⚠️ 保存字段是 **`content`**（接口文档写成 `key`，是生成错误，已核对源码）。
> 单次 PUT 不超过约 2 万字。

---

## 4. 剧本

| 方法 | 路径 | body |
|---|---|---|
| POST | `/script/generate/{projectId}` | `{novelContent,style,episodeCount}` → `taskId`（双 Agent，异步） |
| GET | `/script/task/{taskId}` | 轮询 |
| GET | `/script/content/{projectId}` | 取 ScriptData |
| PUT | `/script/save/{projectId}` | ScriptData（整包覆盖） |

### ScriptData

```json
{
  "title": "第1集 集名",
  "summary": "一句话概括",
  "characters": [{
    "name": "", "description": "", "role": "主角|配角", "gender": "男|女",
    "age": "青年|中年|老年", "appearance": "", "hairstyle": "", "clothing": "", "personality": ""
  }],
  "scenes": [{
    "name": "", "locationType": "室内|室外", "description": "",
    "lighting": "", "atmosphere": "", "style": "", "colorTone": "",
    "timeOfDay": "白天|黄昏|夜晚"
  }],
  "props": [{
    "name": "", "propType": "物品|交通工具", "description": "",
    "material": "", "color": "", "style": ""
  }],
  "plots": [{
    "plotNumber": 1, "location": "场景名", "time": "白天",
    "description": "本场发生什么",
    "dialogues": [{"character": "角色名", "text": "台词", "action": "动作提示"}]
  }]
}
```

> `plots[].location` 必须与 `scenes[].name` 逐字一致；`dialogues[].character` 必须与 `characters[].name` 一致。
> 生成剧本时平台会**自动建好对应的资产**（角色/场景/道具），不用手工再建一遍。

---

## 5. 资产

### 角色 CharacterAsset

| 方法 | 路径 |
|---|---|
| GET | `/asset/character/list/{projectId}`（可选 `?keyword=`） |
| GET | `/asset/character/list-all`（当前用户全部） |
| POST | `/asset/character/create` |
| PUT | `/asset/character/update/{id}` |
| DELETE | `/asset/character/delete/{id}` |

创建体：

```json
{"projectId":9,"name":"林夕","roleType":"主角","gender":"女","age":"青年",
 "description":"","appearance":"","hairstyle":"","clothing":"","personality":""}
```

字段：`id, projectId, name, roleType, gender, age, description, appearance, hairstyle, clothing,
pendingAppearance, pendingHairstyle, pendingClothing, personality, voiceAudioUrl,
imagePrompt, imageUrl, threeViewImageUrl, modelUrl, referenceCount, sortOrder, imageMode`

### 场景 SceneLocation

| 方法 | 路径 |
|---|---|
| GET | `/asset/scene/list/{projectId}` |
| POST | `/asset/scene/create` |
| PUT | `/asset/scene/update/{id}` |
| DELETE | `/asset/scene/delete/{id}` |

创建体：

```json
{"projectId":9,"name":"时辰公司楼下咖啡店","locationType":"室内",
 "description":"","timeOfDay":"下午","lighting":"","atmosphere":"","colorTone":"","style":""}
```

字段：`id, projectId, name, locationType, description, timeOfDay, lighting, atmosphere, style, colorTone,
frontImageUrl, rightImageUrl, backImageUrl, leftImageUrl,
panoramaPrompt, panoramaImageUrl,
frontPrompt, rightPrompt, backPrompt, leftPrompt,
wideAnglePrompt, wideAngleImageUrl,
referenceImageUrl, modelUrl, referenceCount, sortOrder, workflow, imageMode`

> ⚠️ **场景没有 `imagePrompt` 字段**，提示词按视角分开存：
> `frontPrompt` / `rightPrompt` / `backPrompt` / `leftPrompt` / `panoramaPrompt` / `wideAnglePrompt`。
> 当前默认 `imageMode = wideangle`，所以只有 `wideAnglePrompt` 有值，图在 `wideAngleImageUrl`。
> 分镜里 `selectedSceneView` 要跟实际有图的视角一致。

### 道具 PropAsset

| 方法 | 路径 |
|---|---|
| GET | `/asset/prop/list/{projectId}` |
| POST | `/asset/prop/create` |
| PUT | `/asset/prop/update/{id}` |
| DELETE | `/asset/prop/delete/{id}` |

创建体：

```json
{"projectId":9,"name":"诊断报告","propType":"物品","description":"","material":"","color":"","style":""}
```

字段：`id, projectId, name, propType, description, material, color, style,
imagePrompt, imageUrl, referenceImageUrl, modelUrl, referenceCount, sortOrder`

### 生成提示词 / 生成图片

| 方法 | 路径 | body |
|---|---|---|
| POST | `/asset/character/generate-image-prompt/{id}` | 单条（异步） |
| POST | `/asset/character/batch-generate-image-prompt` | `[id,...]` → `{taskIds:[...],count}` |
| POST | `/asset/character/generate-image/{id}` | 单条（异步） |
| POST | `/asset/character/batch-generate-image` | `[id,...]` → `{taskIds:[...]}` |
| POST | `/asset/character/generate-voice/{id}` | 按人物特征生成音色（异步） |

场景/道具把 `character` 换成 `scene` / `prop` 即可，路径结构一致。

> 批量接口返回的是 **`taskIds` 数组**（每个资产一个任务），不是单个 `taskId`。
> 系统**串行**处理：ComfyUI 单队列，一次只跑一张图，21 张图约 25 分钟。

### 任务查询

| 类型 | 路径 |
|---|---|
| 资产图片 | `GET /asset/image-task/{taskId}` |
| 人物音色 | `GET /asset/voice-task/{taskId}` |
| 对白克隆 | `GET /storyboard/voice-task/{taskId}` |

---

## 6. 分镜

| 方法 | 路径 | body |
|---|---|---|
| POST | `/storyboard/generate/{projectId}` | 无（双 Agent，异步）→ `taskId` |
| GET | `/storyboard/task/{taskId}` | 轮询 |
| GET | `/storyboard/content/{projectId}` | 取 StoryboardData |
| PUT | `/storyboard/save/{projectId}` | StoryboardData（**整包覆盖**） |
| GET | `/storyboard/running-tasks/{projectId}` | 找回在跑的任务 |
| POST | `/storyboard/batch-optimize-dialogue/{projectId}` | 批量精修台词标点与 action（异步） |
| POST | `/storyboard/change-prompt-language/{projectId}` | `{language,shotIndices}`，只翻译 `<d>` 里的台词 |

### StoryboardData

```json
{
  "title": "第1集 集名",
  "summary": "一句话概括",
  "shots": [{
    "shotNumber": 1,
    "description": "画面里发生什么（可拍摄的可见内容）",
    "shotType": "大远景|远景|全景|中景|中近景|近景|特写|大特写",
    "cameraMovement": "固定|推|拉|摇|移|跟|升降",
    "characters": ["角色名"],
    "location": "场景名",
    "propNames": ["道具名"],
    "duration": 4,
    "dialogue": [{"character":"角色名","text":"台词","action":"动作"}],
    "soundEffect": "具体声源",
    "mood": "情绪",
    "selectedSceneView": "wideangle|front|right|back|left|panorama",
    "firstFramePrompt": "",
    "videoPrompt": "",
    "msrVideoPrompt": "",
    "msrGlobalPrompt": "",
    "h3VideoPrompt": "",
    "characterAssetIds": [55],
    "sceneAssetId": 271,
    "propAssetIds": [59],
    "firstFrameUrl": "",
    "videoUrl": "",
    "videoStatus": "pending|generating|completed|failed",
    "videoProviderTaskId": "",
    "videoLastFrameUrl": "",
    "videoUrlPreUpscale": "",
    "usePrevVideoRef": true,
    "prevVideoFrames": 5,
    "videoWorkflow": "",
    "seed": 0,
    "staging": {"segments": [
      {"fromSec":0,"toSec":2.5,"shotType":"","camera":"",
       "chars":[{"name":"","facing":"","gaze":"","distance":""}]}
    ]},
    "storyboardSketchUrl": "",
    "storyboardSketchPrompt": ""
  }]
}
```

**保存前的硬性要求**（否则数据会写坏或被后端拒）：

1. `shots` 非空
2. 每镜 `description` 非空
3. `characters` / `location` / `propNames` 与资产名**逐字一致**
4. `characterAssetIds` / `sceneAssetId` / `propAssetIds` 要对得上（否则生成时没有参考图，出图无参考）
5. `shotNumber` 从 1 连续递增

> ⚠️ **有默认值的字段不要显式写**：`usePrevVideoRef`（默认 **true**）、`prevVideoFrames`（默认 **5**）、
> `selectedSceneView`（按场景模式）。写死会覆盖系统行为——踩过这个坑：给全部镜头写 `usePrevVideoRef: false`，
> 系统默认的"上一镜末 5 帧续接"被关掉，成片全是硬切。
>
> ⚠️ `videoUrl` / `firstFrameUrl` / `videoStatus` 等**由平台写回**，保存时原样保留，不要自己编。

---

## 7. 场面调度

| 方法 | 路径 | body |
|---|---|---|
| POST | `/storyboard/generate-staging/{projectId}/batch` | `[shotIndex,...]`（**0 起**） |
| POST | `/storyboard/generate-staging/{projectId}/shot/{shotIndex}` | 单镜（流式） |
| GET | `/storyboard/task/{taskId}` | 轮询 |

产物写入 `shots[i].staging.segments[]`：

```json
{"fromSec":0,"toSec":2.5,"shotType":"中景",
 "camera":"侧后方 45°，齐腰机位略仰",
 "chars":[{"name":"林夕","facing":"朝向画左，身体侧对镜头","gaze":"看向画外右侧","distance":"距镜头 3 米"}]}
```

> 没有独立保存接口，调度结果**通过 `/storyboard/save` 落库**。
> body 是**镜头下标数组（0 起）**，不是 shotNumber。

---

## 8. 视频提示词

| 方法 | 路径 | body |
|---|---|---|
| POST | `/storyboard/batch-generate-msr-prompt/{projectId}` | `[shotIndex,...]`（0 起） |
| POST | `/storyboard/generate-msr-prompt/{projectId}/shot/{shotIndex}` | 单镜 |
| GET | `/storyboard/task/{taskId}` | 轮询 |

产物写在 `shots[i].h3VideoPrompt`（H3 结构化英文格式：`subject_definitions` / `summary` /
`retention_analysis` / `detailed_description` / `overall_soundscape` / `non_diegetic_music`）。
`msrVideoPrompt` 在部分工作流下为空，**以 `h3VideoPrompt` 为准**。

> 同样没有独立保存接口，结果通过 `/storyboard/save` 落库。

---

## 9. 视频生成

| 方法 | 路径 | query / body |
|---|---|---|
| POST | `/storyboard/generate-msr-video/{projectId}/shot/{shotIndex}` | `?megapixels=0.2`（抽卡）|
| POST | `/storyboard/batch-generate-msr-video/{projectId}` | `?megapixels=0.2`（抽卡）+ `[shotIndex,...]` |
| GET | `/storyboard/task/{taskId}` | 轮询 |

### 工作流

| 方法 | 路径 | body |
|---|---|---|
| GET | `/storyboard/{projectId}/video-workflow/options` | - |
| PUT | `/storyboard/{projectId}/video-workflow/default` | `{workflow}` |
| PUT | `/storyboard/{projectId}/shot/{idx}/video-workflow` | `{workflow}`（空串=跟随项目） |

| 值 | 名称 | 适合 |
|---|---|---|
| `h3_r2v` | 官方参考图生视频 | 通用、单遍采样、最快 |
| `h3_ercai` | 二采 | 对话/情绪/细节，画质最好、最慢 |
| `h3_wuxi` | 武戏 | 动作/打斗 |

### 分辨率档位 `megapixels`（16:9 时）

| 档位 | 分辨率 | 用途 |
|---|---|---|
| 0.2 | 608×352 | **抽卡/快速验证（首选，最快）** |
| 0.4 | 864×480 | 草稿（比 0.2 慢，判断构图不需要） |
| 0.5 / 0.6 | 960×544 / 1056×608 | 中间档 |
| 0.7 | 1152×640 | 平衡 |
| 1.0 | 1376×768 | 接近原生 |
| 2.0 | 1920×1088 | 高清（显存吃紧） |

> 平台允许 0.1–4.0（步长 0.1），超出会被拦下回退默认。不做后期超分，要高清就换档重出。
> **抽卡一律 0.2**：判断构图/动作/表演对不对，0.2 与 0.4 结论一样，但快得多。

---

## 10. 导出

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/storyboard/export-videos/{projectId}` | 打包 ZIP（二进制流） |

---

## 11. 任务状态

```json
{"taskId":"...","taskType":"...","projectId":9,
 "status":"pending|running|completed|failed",
 "progress":0,"message":"...","result":{},"createTime":0,"updateTime":0}
```

| 任务类型 | 查询接口 |
|---|---|
| 剧本 | `/script/task/{taskId}` |
| 分镜 / 视频 / 调度 / 提示词 | `/storyboard/task/{taskId}` |
| 资产图片 | `/asset/image-task/{taskId}` |
| 人物音色 | `/asset/voice-task/{taskId}` |
| 对白克隆 | `/storyboard/voice-task/{taskId}` |

- `status` 出现 `running` / `processing` 都算在跑，终态是 `completed` / `failed`
- 轮询间隔 6–10 秒；剧本/分镜 2–15 分钟，单镜视频 ~2 分钟（0.2 档）/ 2.5–3.5 分钟（0.4 档）
- 批量任务有一个总 taskId，内部串行；**判定完成要同时看总任务 + 逐镜状态 + ComfyUI 队列**

---

## 12. 已核实的文档偏差（必读）

官方自动生成的接口文档有六处错误，**以本文件为准**：

| 位置 | 文档写的 | 实际 |
|---|---|---|
| 所有响应 | `code: 0` 成功 | **`code: 200` 成功**（0 也兼容） |
| `PUT /novel/save/{id}` | `{"key":"..."}` | **`{"content":"..."}`** |
| `POST /project/{id}/children` | `{"key":"..."}` | **`{"name":"第1集 xxx"}`** |
| `PUT /project/{id}/step` | `{"currentStep":3}` | **裸整数 `3`** |
| 场景提示词 | `imagePrompt` | **按视角分开**：`wideAnglePrompt` / `frontPrompt` / … |
| 批量生成接口 | 返回 `taskId` | 返回 **`{taskIds:[...], count}`** |
