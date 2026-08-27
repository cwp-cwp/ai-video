# AI视频创作平台

一套基于 AI 驱动的全流程视频创作系统，覆盖从小说创作、剧本生成、分镜设计到视频生成的全链路。采用前后端分离架构，后端基于 Spring Boot 3 + LangChain4j，前端基于 Vue 3 + Element Plus，整合 ComfyUI 实现本地 AI 图片和视频生成。

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Java](https://img.shields.io/badge/java-17-orange.svg)](https://adoptium.net/)
[![Vue](https://img.shields.io/badge/vue-3.4-green.svg)](https://vuejs.org/)
[![Spring Boot](https://img.shields.io/badge/spring--boot-3.2.4-brightgreen.svg)](https://spring.io/projects/spring-boot)

## 视频案例

以下是用本系统全自动创作出的 6 分钟连续短片：

👉 [点击观看 - Bilibili](https://www.bilibili.com/video/BV1Lh8Z6AEHB/?vd_source=f53e58e282c88f94f9851bd38cd22cde)

---

## 目录

- [功能特性](#功能特性)
- [系统截图](#系统截图)
- [快速开始](#快速开始)
- [环境要求](#环境要求)
- [ComfyUI 工作流安装（重要）](#comfyui-工作流安装重要)
- [使用指南](#使用指南)
- [技术栈](#技术栈)
- [项目结构](#项目结构)
- [系统更新](#系统更新)
- [常见问题](#常见问题)

---

## 功能特性

### 核心创作流程

```
小说创作 → 剧本生成 → 分镜设计 → 视频生成
  Step0      Step1      Step2      Step3
```

- **小说创作**：输入主题/想法，AI 流式生成小说内容，或直接粘贴已有小说
- **剧本生成**：基于小说 AI 生成结构化剧本（含角色、场景、对白），支持人工编辑修改
- **分镜设计**：AI 生成分镜脚本，支持分镜编辑、首帧图片生成、视频提示词优化
- **视频生成**：批量生成视频片段，支持单个镜头和批量生成

### 资产管理

- **角色资产**：AI 生成角色形象图，支持三视图（正脸、侧面、背面）
- **场景资产**：AI 生成场景背景图，支持多种风格和光照
- **道具资产**：AI 生成道具图片，丰富视频画面细节

### AI 模型支持

- **大语言模型**：阿里百炼（通义千问）、火山引擎（豆包）、DeepSeek、本地 Ollama
- **图片生成**：火山引擎、阿里百炼、ComfyUI（本地）
- **视频生成**：火山引擎、阿里百炼、ComfyUI（本地 LTX / MiniMax H3）

### 辅助工具

- **语音克隆**：VoxCPM2 多角色语音克隆，为视频角色配音
- **音乐创作**：AI 音乐生成，支持提示词/歌词生成背景音乐
- **宫格图像分割**：将全景图/四视图自动分割为独立图片
- **图像编辑**：支持参考图引导的 AI 图像编辑

---

## 系统截图

### 系统设置

配置 AI 大模型、图片生成、视频生成等供应商的 API 密钥和参数。

![系统设置](images/01系统设置.png)

![保存设置](images/02保存设置.png)

### 项目创建

创建项目，设置项目名称、题材、视觉风格、画面尺寸等。

![创建项目](images/03创建项目.png)

### 小说创作

输入主题或直接粘贴小说内容，AI 辅助生成。

![输入小说](images/04输入小说.png)

### 剧本生成

AI 异步生成结构化剧本，包含角色信息、场景描述、对白内容，支持人工编辑。

![剧本生成](images/05剧本生成.png)

### 资产图片生成

为角色、场景、道具生成 AI 图片，建立资产库保证视频一致性。

![生成资产图](images/06生成资产图.png)

### 分镜设计

AI 生成分镜脚本，支持首帧图片生成、视频提示词优化、批量生成。

![生成分镜](images/07生成分镜.png)

### 音乐创作

AI 生成背景音乐，支持文本提示词和歌词输入。

![音乐创作](images/08音乐创作.png)

### 在线听歌

内置音乐播放器，在线试听生成的音乐。

![在线听歌](images/09在线听歌.png)

### 宫格图像分割

将生成的 360 全景图或四宫格图片自动分割为独立图片。

![宫格图像分割](images/10宫格图像分割.png)

### 导演台视频生成

多图参考视频生成，支持 LTX-2.3 和 MiniMax H3 模型，首帧/首尾帧模式。

![LTX导演台生视频](images/11LTX导演台生视频.png)

---

## 快速开始

### 下载便携安装包

前往 [Releases](https://github.com/cwp-cwp/ai-video/releases) 页面下载最新版本的便携安装包 `apache-tomcat-10.1.59.zip`。

### 安装步骤

1. **解压** `apache-tomcat-10.1.59.zip` 到任意目录（路径不要包含中文和空格）
2. **双击运行** `start.bat`，等待服务启动完成
3. 浏览器自动打开 `http://localhost:18080`，注册账号即可使用

> 便携安装包已内置 JDK 17、MySQL 8.0、Tomcat 10，无需额外安装任何环境。

---

## 环境要求

| 组件 | 最低要求 | 推荐配置 |
|------|---------|---------|
| 操作系统 | Windows 10/11 64 位 | Windows 11 64 位 |
| 内存 | 16 GB | 32 GB |
| 显卡 | NVIDIA GTX 1060 6GB | NVIDIA RTX 3060 12GB+ |
| 硬盘 | 20 GB 可用空间 | 50 GB SSD |

---

## ComfyUI 工作流安装（重要）

> **本系统依赖 ComfyUI 实现本地图片和视频生成，请务必在启动系统前完成 ComfyUI 的安装和工作流配置。**

### 1. 安装 ComfyUI

请参考 [ComfyUI 官方仓库](https://github.com/comfyanonymous/ComfyUI) 完成安装。

**推荐安装方式**（Windows 便携版）：

```bash
# 下载 ComfyUI_windows_portable 并解压
# 下载地址：https://github.com/comfyanonymous/ComfyUI/releases
```

### 2. 安装必需插件和模型

本系统依赖以下 ComfyUI 自定义节点和模型，请确保全部安装：

**自定义节点（通过 ComfyUI Manager 安装）：**
- `ComfyUI-LTXVideo` — LTX 视频生成
- `ComfyUI-KJNodes` — 图像处理节点
- `ComfyUI-Vextra-Nodes` — 扩展节点
- `ComfyUI_essentials` — 基础工具节点
- `rgthree-comfy` — 增强节点集
- `ComfyUI-Chibi-Nodes` — 图像处理
- `ComfyUI-Impact-Pack` — 图像处理增强
- `ComfyUI-Kolors-MZ` — 图像编辑
- `ComfyUI-WanVideoWrapper` — Wan 视频生成
- 其他依赖节点（请根据工作流加载时的报错提示逐个安装）

**必需模型（下载后放入对应目录）：**
- LTX-Video 模型（用于视频生成）
- Qwen-Image 模型（用于图片生成）
- VoxCPM2 模型（用于语音克隆）
- 其他模型请根据工作流中的节点要求下载

### 3. 导入工作流

将本仓库 `comfyui工作流/` 目录下的所有 JSON 文件拖入 ComfyUI 界面，逐个加载并验证是否能正常运行。

**工作流文件清单：**

| 文件 | 用途 |
|------|------|
| `文生图_qwen_image_2512_with_2steps_lora.json` | 资产图片生成（角色/场景/道具） |
| `图像编辑_qwen_Image_edit_subgraphed.json` | 首帧图片生成（支持参考图） |
| `图像编辑-krea2_image_edit.json` | 首帧图片生成（Krea2） |
| `视频-LTX-2.3-首帧-低显存版.json` | 视频生成（首帧模式，低显存） |
| `视频-LTX-2.3-首尾帧-量化版.json` | 视频生成（首尾帧模式） |
| `LTX-2.3_MSR_多图参考视频生成.json` | 多图参考视频生成 V1 |
| `LTX-2.3_MSR_多图参考视频生成_V2.json` | 多图参考视频生成 V2 |
| `LTX-2.3-MSR-V2-8G显存版本.json` | 多图参考视频（8G 显存优化） |
| `LTX导演台无字幕.json` | 导演台视频生成 |
| `video_minimax_h3_r2v.json` | MiniMax H3 视频生成 |
| `video_minimax_h3_r2v_导演台多段衔接.json` | H3 导演台多段衔接 |
| `文生图_image_ideogram4.json` | 图片生成（Ideogram4） |
| `文生图-Qwen-Image-GGUF-Q4KS-4步极速生图.json` | 极速生图模式 |
| `文生图-image_krea2_turbo_t2i.json` | 图片生成（Krea2 Turbo） |
| `F2K-高清重绘.json` | 高清重绘 |
| `F2K_高清重绘_可调整宽高.json` | 高清重绘（可调尺寸） |
| `image_z_image_turbo.json` | 图生图 Turbo |
| `VoxCPM2-语音克隆.json` | 语音克隆 |
| `VoxCPM2-语音生成.json` | 语音生成 |
| `VoxCPM2-多人对话语音克隆.json` | 多人对话语音克隆 |
| `音乐生成_audio_ace_step_1_5_split.json` | AI 音乐生成 |
| `音乐生成（提速版）_audio_ace_step_1_5_split.json` | AI 音乐生成（提速版） |
| `360全景图生成.json` | 360 全景图生成 |
| `360全景图生成全景视频.json` | 全景图转视频 |
| `360全景图预览.json` | 全景图预览 |
| `360全景视频截取多张图.json` | 全景视频截图 |
| `宫格图像切分.json` | 宫格图像分割 |
| `人声伴奏分离.json` | 人声/伴奏分离 |
| `语音文字提取-Qwen3-ASR.json` | 语音转文字 |
| `音频时长截取.json` | 音频时长截取 |

> **重要提示：请在 ComfyUI 中逐一加载上述工作流，确保所有节点不报红、所有模型已下载，能够正常执行工作流后再启动本系统。** 工作流加载报错通常是因为缺少对应的自定义节点或模型文件，请根据报错信息补充安装。

### 4. 配置 ComfyUI 连接

启动系统后，进入 **系统设置 → 图片生成/视频生成** 页面，将 ComfyUI 的 API 地址填入对应配置项：

- ComfyUI 默认地址：`http://127.0.0.1:8188`
- 确保 ComfyUI 启动时添加了 `--enable-cors-header` 参数，允许跨域访问

---

## 使用指南

### 注册与登录

1. 打开 `http://localhost:18080`，点击"注册"
2. 输入邮箱和密码完成注册
3. 登录后进入工作台

### 创作流程

1. **新建项目**：点击"新建项目"，输入项目名称、描述、题材、视觉风格
2. **小说创作**：输入主题或直接粘贴小说内容，AI 辅助生成
3. **剧本生成**：选择风格后 AI 自动生成结构化剧本，可在编辑模式下修改
4. **资产管理**：为剧本中的角色、场景生成 AI 图片，建立资产库
5. **分镜设计**：AI 生成分镜脚本，优化提示词，生成首帧图片
6. **视频生成**：批量生成视频片段，预览并导出

### 模型配置

进入 **系统设置** 页面，配置以下内容：

- **AI 模型**：选择大语言模型供应商（阿里百炼/火山引擎/DeepSeek/Ollama），填入 API Key
- **图片生成**：选择图片生成供应商（火山引擎/阿里百炼/ComfyUI），配置 API 地址
- **视频生成**：选择视频生成供应商，配置 API 地址
- **默认配置**：设置各步骤默认使用的模型供应商

---

> ⚠️ **文本模型建议使用 DeepSeek**，其他模型（阿里百炼、火山引擎等）在结构化输出方面不够稳定，可能出现剧本格式错误、分镜生成异常等问题。

> ⚠️ **图片和视频生成建议使用 ComfyUI**，其他厂商的模型未经过充分测试，适配度不高，可能出现生成失败或效果不佳的问题。

## License

MIT License