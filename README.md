# Ruleset Builder

自动构建 mihomo (.mrs) 和 sing-box (.srs) 规则集。当源文件发生变更时，GitHub Actions 自动编译并提交产物。

## 目录结构

```
├── mihomo/
│   ├── domain/       # 域名规则 (.yaml/.txt) → .mrs
│   └── ipcidr/       # IP-CIDR 规则 (.yaml/.txt) → .mrs
├── singbox/
│   └── rules/        # sing-box 规则 (.json) → .srs
└── output/           # CI 编译产物（自动生成）
    ├── mihomo/       # *.mrs 文件
    └── singbox/      # *.srs 文件
```

## 使用方法

### 1. 添加 mihomo 规则

在 `mihomo/` 对应子目录下创建 `.yaml` 或 `.txt` 文件：

**domain 类型** (`mihomo/domain/`):
```yaml
payload:
  - '.example.com'
  - 'exact.example.com'
```

**ipcidr 类型** (`mihomo/ipcidr/`):
```yaml
payload:
  - '10.0.0.0/8'
  - '192.168.0.0/16'
```

> **注意**：mrs 格式仅支持 domain 和 ipcidr 两种 behavior，不支持 classical。
> 参考：https://wiki.metacubex.one/config/rule-providers/#format

### 2. 添加 sing-box 规则

在 `singbox/rules/` 下创建 `.json` 文件：

```json
{
  "version": 2,
  "rules": [
    {
      "domain_suffix": [".example.com"],
      "domain_keyword": ["keyword"],
      "ip_cidr": ["10.0.0.0/8"]
    }
  ]
}
```

### 3. 推送即自动编译

```bash
git add .
git commit -m "add new rules"
git push
```

GitHub Actions 会自动：
- 检测变更的文件
- 下载对应工具链（自动获取最新版本）
- 编译生成 `.mrs` / `.srs`
- 将产物提交到 `output/` 目录

### 4. 引用规则集

编译完成后，通过 raw URL 引用：

**mihomo 配置**:
```yaml
rule-providers:
  my-direct:
    type: http
    behavior: domain
    format: mrs
    url: https://raw.githubusercontent.com/<你的用户名>/ruleset-builder/main/output/mihomo/direct.mrs
    interval: 86400
    path: ./ruleset/direct.mrs

rules:
  - RULE-SET,my-direct,DIRECT
```

**sing-box 配置**:
```json
{
  "route": {
    "rule_set": [
      {
        "type": "remote",
        "tag": "direct",
        "format": "binary",
        "url": "https://raw.githubusercontent.com/<你的用户名>/ruleset-builder/main/output/singbox/direct.srs",
        "update_interval": "1d"
      }
    ]
  }
}
```

## 手动触发

在 GitHub 仓库的 Actions 页面，可以手动触发构建（workflow_dispatch），支持选择指定 behavior 类型。

## 工具版本

- mihomo: 自动获取 GitHub 最新 release
- sing-box: 自动获取 GitHub 最新 release
