# Third-Party Notices

AI 错题复盘工作台使用并在 Windows 便携包中分发若干第三方开源组件。
这些组件仍分别受其原始许可证约束；项目自身的 MIT 许可证不会替代第三方许可证。

随源码和 Release 提供以下机器可读及完整许可资料：

- `sbom/python.cdx.json`：Python 运行时依赖 CycloneDX SBOM；
- `sbom/frontend.cdx.json`：生产前端依赖 CycloneDX SBOM，包含可获取的许可文本证据；
- `sbom/python-licenses.md`：构建环境中 Python 组件的许可证、项目地址和许可/NOTICE全文。

主要运行时组件包括 FastAPI、Starlette、Uvicorn、Pydantic、SQLAlchemy、Alembic、HTTPX、Pillow、React、React Router、TanStack Query、React Markdown、KaTeX 及其传递依赖。准确版本以对应 SBOM 为准。

便携包还包含：

- Python 3.12 运行时，依据 Python Software Foundation License；
- OpenSSL 运行库，依据 Apache License 2.0；
- SQLite，属于公共领域；
- Microsoft Visual C++ Runtime 可再发行文件，依据 Microsoft 的可再发行条款；
- PyInstaller bootloader，依据 GPL 2.0 与 PyInstaller Bootloader Exception。

维护者发布新版本前应重新生成 SBOM 和许可清单，并检查本文件所述组件与实际打包内容一致。
