# Ruleset Builder

[![Build mihomo Ruleset](https://github.com/xinming7/ruleset-builder/actions/workflows/build-mihomo.yml/badge.svg)](https://github.com/xinming7/ruleset-builder/actions/workflows/build-mihomo.yml)
[![Build sing-box Ruleset](https://github.com/xinming7/ruleset-builder/actions/workflows/build-singbox.yml/badge.svg)](https://github.com/xinming7/ruleset-builder/actions/workflows/build-singbox.yml)

自动构建 mihomo (.mrs) 和 sing-box (.srs) 规则集。当源文件发生变更时，GitHub Actions 自动编译并将产物发布到 `rules` 分支。

## 目录结构

```
├── mihomo/
│   ├── domain/              # 域名规则 (.yaml/.txt) → .mrs
│   │   ├── direct.yaml      # 直连域名
│   │   ├── custom_ai.yaml   # AI 服务域名
│   │   ├── custom_direct.yaml  # 自定义直连域名
│   │   ├── custom_pcdn.yaml    # PCDN 域名屏蔽
│   │   └── custom_proxy.yaml   # 代理域名
│   └── ipcidr/              # IP-CIDR 规则 (.yaml/.txt) → .mrs
│       ├── direct-ip.yaml   # 直连 IP
│       └── custom_pcdnip.yaml  # PCDN IP 黑名单
└── singbox/
    └── rules/               # sing-box 规则 (.json) → .srs
        ├── direct.json
        ├── custom_direct.json
        ├── custom_lanip.json
        ├── custom_pcdn.json
        └── custom_proxy.json
```

产物存放在 `rules` 分支，与源码完全隔离，本地 push 不会影响产物。

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
- 校验文件格式（YAML/JSON 语法）
- 从仓库 [Release](https://github.com/xinming7/ruleset-builder/releases/tag/kernel-v1) 获取预置内核
- 编译生成 `.mrs` / `.srs`
- 将产物推送到 `rules` 分支

### 4. 引用规则集

通过 `rules` 分支的 raw URL 引用：

**mihomo 配置**:
```yaml
rule-providers:
  my-direct:
    type: http
    behavior: domain
    format: mrs
    url: https://raw.githubusercontent.com/xinming7/ruleset-builder/rules/mihomo/direct.mrs
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
        "url": "https://raw.githubusercontent.com/xinming7/ruleset-builder/rules/singbox/direct.srs",
        "update_interval": "1d"
      }
    ]
  }
}
```

## 手动触发

在 GitHub 仓库的 Actions 页面，可以手动触发构建（workflow_dispatch），支持：
- 选择指定 behavior 类型（domain/ipcidr）
- 强制打包所有文件

## 内核版本

构建所用的内核版本固定在仓库 [Release](https://github.com/xinming7/ruleset-builder/releases/tag/kernel-v1) 中：

- **mihomo**: v1.19.31 (linux-amd64)
- **sing-box**: v1.14.2 (linux-amd64)

更新内核版本时，下载新版二进制上传到新 Release，同步更新 workflow 中的 Tag 名称即可。
