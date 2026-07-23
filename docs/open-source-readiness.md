# 开源发布就绪检查

日期：2026-07-23

## 已完成

- Pillow升级到12.3.0，pytest升级到9.1.1；
- Python `pip-audit`和npm官方Registry审计均为0个已知漏洞；
- 服务只监听`127.0.0.1:3002`，增加Trusted Host、浏览器跨源写入拦截、CSP及其他安全响应头；
- Windows Release关闭Swagger UI和OpenAPI；
- Python和前端依赖锁定，前端构建使用`npm ci`；
- 增加CycloneDX SBOM、Python许可全文和第三方声明；
- Release根目录包含LICENSE、PRIVACY、SECURITY、第三方声明和SBOM；
- 增加Windows CI、Tag Release、构建来源证明、Dependabot、Gitleaks、Issue和PR模板；
- 删除Windows保留名文件`frontend/NUL`，测试Key改为明确假值；
- 敏感信息扫描未发现OpenAI、Gemini、GitHub、AWS或私钥格式内容；
- 无Python/Node/npm隔离模拟通过，证据见`docs/clean-windows-simulation.json`。

## 验证结果

- 后端：56 passed；
- 前端：8 passed；
- Ruff、格式、TypeScript和Vite：通过；
- Python依赖漏洞：0；
- npm依赖漏洞：0；
- PyInstaller和增强Release冒烟：通过；
- Release数据条目：0；
- Release SHA-256：`7766234ce1a716eb8775c96cac5ef3a706398b522bc73db488e840946e6c8faa`。

## 发布者仍需执行的外部动作

1. 撤销并轮换曾在聊天中暴露的MiMo API Key；
2. 创建远程GitHub仓库，检查首个提交，并启用Private Vulnerability Reporting、Dependabot和Actions；
3. 在真正全新的Windows 10/11普通用户虚拟机，从GitHub下载带Mark-of-the-Web的ZIP，验证SmartScreen和Defender；
4. 确认`docs/`中的题目、模型输出和截图拥有公开发布权且不含学生身份信息；
5. 如面向普通用户广泛分发，申请Windows代码签名证书；未签名前必须持续声明“未知发布者”限制。
