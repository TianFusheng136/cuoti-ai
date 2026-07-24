# AI 错题复盘工作台

把一道错题转化为“知识点、错因、讲解、复习卡片和变式训练”的本地 AI 学习工具。

> 第一版核心闭环已完成验收：题目录入、确认、分析、三类变式、错题本、复习和 Windows 独立打包均已通过测试。变式题对可精确计算的已知题族使用本地确定性校验，其他题型继续使用独立 AI 复核；具体能力边界见审计文档。

## 已完成

- React + Vite 中文工作台骨架；
- FastAPI `/api/v1/health` 健康检查；
- FastAPI 托管生产版前端；
- SQLite 和本地数据目录自动初始化；
- 文字题目创建与本地持久化；
- JPG、PNG、WebP 上传、预览、拖拽和截图粘贴；
- 图片扩展名、文件签名、尺寸及 15MB 大小限制校验；
- 题目查询、列表、图片读取和删除 API；
- 删除题目时同步清理本地图片；
- OpenAI 兼容接口和 Gemini 原生接口配置；
- 文本、视觉模型能力分离；
- Windows DPAPI 加密保存 API Key；
- 模型连接测试、编辑和删除；
- OpenAI 兼容与 Gemini 视觉题目识别；
- 识别结果使用 Pydantic/JSON Schema 严格校验；
- 保存模型名、耗时和 `recognition-v1` 提示词版本；
- 图片与识别文字双栏确认页面；
- 低可信度、裁切和缺失信息警告；
- 用户明确确认前保持题目未确认状态；
- 确认文本哈希和识别快照分开保存；
- OpenAI 兼容与 Gemini 结构化文本分析；
- `analysis-v1` 提示词和 `analysis-schema-v1` 输出 Schema；
- 确认哈希异常时在调用模型前阻止分析；
- 信息不足时禁止输出答案、思路和步骤；
- 知识点、答案、整体思路、详细步骤、候选错因和三步清单；
- Markdown 与本地 KaTeX 公式渲染；
- 简单算术确定性复核及答案冲突警告；
- 学生自主选择并补充真实错因；
- 同知识点、换场景、提高难度三类结构化变式题；
- 三类变式题分别生成、分别验算，失败原因定向反馈且只重试失败类型；
- 抛物线面积、绝对值、坐标中点/面积、功和功率题族的确定性安全生成与公式验算；
- 其他题型的盲解、学生版答案整理和独立 AI 终审，不通过时不保存；
- 答案默认折叠的变式练习卡片；
- 支持搜索、学科、知识点、掌握状态和收藏筛选的本地错题本；
- 待复习、复习中、已掌握状态及本地间隔复习计划；
- 首页最近错题、知识点和今日待复习概览；
- Alembic 数据库迁移及旧版数据库自动升级；
- 不含 API Key 的 ZIP 完整备份、重启恢复与恶意路径校验；
- 错题本 JSON、CSV 导出；
- PyInstaller Windows x64 独立 Release，无需安装 Python 或 Node.js；
- 未配置视觉或文本模型时的明确降级提示；
- 浅色/深色模式基础界面；
- Windows 开发版启停脚本；
- 前后端自动化测试。

## 开发版启动（Windows）

开发环境需要：

- Python 3.12；
- Node.js 20 或更高版本。

双击：

```text
start.bat
```

脚本会在首次启动时创建本地 Python 环境、构建前端，并固定使用 `127.0.0.1:3002` 打开浏览器。停止应用请双击：

```text
stop.bat
```

Windows 独立 Release 内置运行环境，普通用户不需要安装 Python 或 Node.js。

## 第一次使用与模型配置

1. 启动后打开“设置”；
2. 至少添加一个文本分析模型；使用图片时还需添加一个视觉识别模型；
3. 选择服务商声明支持的 OpenAI 兼容接口，或 Gemini 原生接口；
4. 按服务商官方文档填写 Base URL、模型名称和 API Key；
5. 保存后点击“测试连接”，再录入题目。

已实际验证的小米 MiMo 按量付费示例：Base URL 为 `https://api.xiaomimimo.com/v1`，文本可使用 `mimo-v2.5-pro`，视觉可使用 `mimo-v2.5`。Token Plan 必须使用套餐页面给出的专属 Base URL 和密钥，不能与按量付费配置混用。本项目与小米、Google、OpenAI及其他模型服务商不存在隶属或背书关系。

一次图片识别通常调用视觉模型一次；一次分析通常调用文本模型一次，兼容接口结构异常时可能追加一次格式修复。命中本地确定性安全题型的变式操作不调用模型生成；其他题型会分别执行题干设计、盲解、答案整理和独立终审，失败类型可能定向重试。三类变式通常约30秒到3分钟，遇到定向重试可能更久；文本模型建议使用默认的600秒（10分钟）超时。实际Token和费用由题目长度、模型输出及服务商价格决定，本应用当前不统计账单。

## Windows 独立 Release

维护者在 Windows x64 构建机上执行：

```powershell
scripts\build-release.ps1
```

产物位于：

```text
packaging\output\AIErrorReviewWorkbench-windows-x64.zip
```

构建脚本使用前端和Python锁定依赖，完成前端构建、后端回归、PyInstaller打包和独立程序冒烟测试。用户解压整个文件夹后双击 `start.bat`，使用 `stop.bat` 停止。学习数据保存在Release文件夹旁的`data/`中。Release默认关闭Swagger UI和OpenAPI文档，并在根目录附带项目许可、隐私/安全说明、第三方许可清单和CycloneDX SBOM。

## 手动开发

### 后端

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install --require-hashes -r requirements-lock.txt
.venv\Scripts\python -m pip install --no-deps -e .
.venv\Scripts\python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

API 文档：<http://127.0.0.1:8000/api/docs>

### 前端

```powershell
cd frontend
npm ci --include=dev
npm run dev
```

前端开发地址：<http://127.0.0.1:5173>

## 测试

```powershell
.venv\Scripts\python -m pytest
cd frontend
npm test
npm run lint
npm run build
```

## 本地数据

运行数据位于 `data/`：

```text
data/
├── app.db
├── uploads/
├── exports/
├── logs/
└── runtime/
```

这些内容不会提交到 Git。上传文件使用 UUID 文件名并按年月存放。API Key 由后端使用当前 Windows 用户的 DPAPI 加密，页面和配置列表不会返回明文。数据库启动时自动迁移并保留已有记录。完整备份始终排除 API Key，恢复后需要重新填写。详见 [模型服务配置指南](docs/provider-guide.md)、[题目识别与确认机制](docs/recognition-safety.md)、[结构化分析安全机制](docs/analysis-safety.md)、[学习闭环说明](docs/learning-loop.md) 和 [数据备份与恢复](docs/data-portability.md)。

## 安全与隐私

所有学习记录默认保存在本机。只有调用用户自行配置的模型API时，相关题目内容才会发送给对应服务商。服务只监听`127.0.0.1:3002`，校验Host并拒绝非本地网页发起的数据修改；但本机其他进程仍可能访问本地API，本工具不是共享账号中的多用户安全边界。详见[PRIVACY.md](PRIVACY.md)和[SECURITY.md](SECURITY.md)。

## 参与和许可证

贡献方式见[CONTRIBUTING.md](CONTRIBUTING.md)，版本变化见[CHANGELOG.md](CHANGELOG.md)。项目代码采用[MIT](LICENSE)许可证，第三方组件仍受各自许可证约束，详见[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)和`sbom/`。
