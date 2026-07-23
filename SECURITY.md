# 安全策略

## 支持版本

首个公开版本发布后，仅最新的`0.1.x`版本接受安全修复。用户应优先升级到最新Release。

## 私密报告漏洞

请在GitHub仓库的 **Security → Advisories → Report a vulnerability** 中提交私密报告。维护者公开仓库时必须启用 **Private Vulnerability Reporting**。

请提供受影响版本、复现条件、影响范围和建议修复方式。不要在公开Issue、讨论、日志或截图中披露漏洞细节、API Key或真实学生数据。维护者应在7天内确认收到报告，并在完成修复和Release后协调公开说明。

## 本地安全边界

- 服务必须只绑定`127.0.0.1:3002`；
- 应用校验Host，并拒绝非本地网页发起的数据修改请求；
- Release默认关闭Swagger UI和OpenAPI文档；
- 应用没有账号系统，本机其他进程仍可能访问本地API，因此不应在不受信任的共享Windows账号中运行；
- Provider Base URL是高信任配置，可能指向互联网或本地模型服务，只应填写用户信任的地址；
- API Key使用Windows DPAPI加密，但系统管理员或当前Windows用户上下文中的恶意程序仍不在防护范围内。

备份恢复检查路径穿越、符号链接、重复文件、解压大小、数据库完整性和版本。备份、JSON及CSV导出不包含API Key；恢复后Provider默认禁用。

## 发布安全

Windows Release尚未代码签名。官方发布应附带SHA-256、CycloneDX SBOM和GitHub构建来源证明，并在受保护的Windows Runner构建。公开发布前必须运行Python/npm依赖审计和敏感信息扫描。
