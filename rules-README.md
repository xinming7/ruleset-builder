# Rules

此分支由 GitHub Actions 自动维护，存放编译后的规则集产物。**请勿手动修改。**

## 目录结构

```
├── mihomo/       # mihomo 规则集 (.mrs)
└── singbox/      # sing-box 规则集 (.srs)
```

## 引用方式

### mihomo

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

### sing-box

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

## 更新频率

- 源文件变更时自动编译
- 每周一定时全量重新编译（使用最新版工具链）

## 源码

规则源文件和 workflow 在 [main 分支](https://github.com/xinming7/ruleset-builder)。
