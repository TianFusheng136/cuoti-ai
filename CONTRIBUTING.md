# 贡献指南

感谢参与 AI 错题复盘工作台。

## 开发环境

- Windows 10/11 x64
- Python 3.12
- Node.js 20+

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install --require-hashes -r requirements-lock.txt
.venv\Scripts\python -m pip install --no-deps -e .
cd frontend
npm ci
```

也可以直接运行根目录的 `start.bat`。

## 提交前检查

```powershell
.venv\Scripts\python -m ruff check backend scripts
.venv\Scripts\python -m ruff format --check backend scripts
.venv\Scripts\python -m pytest
cd frontend
npm test
npm run lint
npm run build
```

涉及依赖变更时还应更新 `uv.lock`、`requirements-lock.txt`、SBOM和第三方许可清单，并运行依赖安全审计。

## Pull Request要求

- 一个PR只处理一个明确问题；
- 新行为必须有自动化测试；
- 不提交API Key、真实学生数据、本地数据库、日志或上传图片；
- 不通过降低验算标准、写死审计答案或绕过确认门禁来提高通过率；
- 涉及数据格式时说明迁移和回滚方式；
- 涉及界面时附脱敏截图。

安全漏洞请按 `SECURITY.md` 私密报告，不要创建公开Issue。
