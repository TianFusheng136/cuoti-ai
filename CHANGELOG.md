# Changelog

本项目遵循语义化版本。发布日期使用UTC。

## [Unreleased]

暂无。

## [0.1.0] - 2026-07-23

### Added

- 本地题目录入、视觉识别、人工确认和结构化分析；
- 三类变式练习、错题本、间隔复习、备份恢复与数据导出；
- Windows x64便携Release；
- 已知数学/物理题族的确定性安全生成和验算；
- Windows CI、Tag Release、构建来源证明、Dependabot和敏感信息扫描。

### Security

- Pillow升级至12.3.0，pytest升级至9.1.1；
- 增加本地Host校验和浏览器跨源写入拦截；
- 增加CSP、禁止嵌入等安全响应头；
- Windows Release默认关闭OpenAPI和Swagger UI；
- Release根目录增加许可、隐私、安全说明和SBOM。

### Changed

- 前端安装改用`npm ci`；
- Python开发和Release构建改用锁定依赖。
