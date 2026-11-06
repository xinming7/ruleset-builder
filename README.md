# Ruleset Builder

[![Build mihomo Ruleset](https://github.com/xinming7/ruleset-builder/actions/workflows/build-mihomo.yml/badge.svg)](https://github.com/xinming7/ruleset-builder/actions/workflows/build-mihomo.yml)
[![Build sing-box Ruleset](https://github.com/xinming7/ruleset-builder/actions/workflows/build-singbox.yml/badge.svg)](https://github.com/xinming7/ruleset-builder/actions/workflows/build-singbox.yml)

自动构建 mihomo (.mrs) 和 sing-box (.srs) 规则集。当源文件发生变更时，GitHub Actions 自动编译并将产物发布到 `rules` 分支；构建所用内核由 `Update Kernel` workflow 每周自动从上游同步（见[内核版本与自动更新](#内核版本与自动更新)）。

## 目录结构

```
├── .github/
│   ├── workflows/
│   │   ├── build-mihomo.yml      # 规则变更 → 编译 .mrs → 推送 rules 分支
│   │   ├── build-singbox.yml     # 规则变更 → 编译 .srs → 推送 rules 分支
│   │   ├── update-kernel.yml     # 每周从上游同步内核到 kernel-v1 Release
│   │   └── validate.yml          # 只读校验：lint / 规则语义 / 发布契约
│   ├── actions/publish-rules/    # 两个构建流程共用的发布逻辑
│   ├── keep-rulesets.txt         # 允许保留的"无源文件产物"白名单
│   └── dependabot.yml
├── scripts/
│   ├── fetch-kernel.sh           # 内核下载 / 解包 / 自检 / canary / 上传
│   └── validate_rules.py         # 规则语义校验
├── requirements.txt              # 校验脚本依赖（pyyaml）
├── mihomo/
│   ├── domain/              # 域名规则 (.yaml/.txt) → .mrs
│   │   ├── custom_ai.yaml          # AI 服务域名
│   │   ├── custom_direct.yaml      # 自定义直连域名
│   │   ├── custom_fakeip_filter.yaml  # fake-ip 过滤域名
│   │   ├── custom_pcdn.yaml        # PCDN 域名屏蔽
│   │   └── custom_proxy.yaml       # 代理域名
│   └── ipcidr/              # IP-CIDR 规则 (.yaml/.txt) → .mrs
│       ├── custom_direct_ip.yaml   # 直连 IP
│       └── custom_pcdnip.yaml      # PCDN IP 黑名单
└── singbox/
    └── rules/               # sing-box 规则 (.json) → .srs
        ├── custom_direct.json
        ├── custom_fakeip_filter.json
        ├── custom_lanip.json
        ├── custom_pcdn.json
        └── custom_proxy.json
```

产物存放在 `rules` 分支，与源码完全隔离，本地 push 不会影响产物。

产物与源文件严格对应：删除源文件后，`rules` 分支上对应的孤儿产物会在下一次构建时**自动清理**（`mihomo/domain|ipcidr/*.yaml|txt` → `mihomo/<name>.mrs`，`singbox/rules/*.json` → `singbox/<name>.srs`）。若某个产物需要长期保留但 main 上没有对应源文件，把名字（产物文件名去掉扩展名）写进 [`.github/keep-rulesets.txt`](.github/keep-rulesets.txt)，每行一个。清理前会校验源文件集合非空，解析异常时只报错不删任何东西。

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
  "version": 5,
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
- 检测变更的文件（按 push 事件的 base commit 做全区间 diff，不只最后一条 commit）
- 校验文件格式（YAML/JSON 语法）与内核 SHA256
- 从仓库 [Release](https://github.com/xinming7/ruleset-builder/releases/tag/kernel-v1) 获取预置内核（版本由 `Update Kernel` workflow 自动维护）
- 编译生成 `.mrs` / `.srs`
- 清理孤儿产物、同步分支 README，再把产物推送到 `rules` 分支（只在构建**成功**时发布）

同时 `Validate` workflow 会跑只读校验：`actionlint`、规则语义（域名/CIDR 格式、重复项、behavior 与目录一致性、产物命名冲突），以及每日一次的"源文件 ↔ 产物"契约与 raw URL 可达性检查。

### 4. 引用规则集

通过 `rules` 分支的 raw URL 引用：

**mihomo 配置**:
```yaml
rule-providers:
  my-custom-direct:
    type: http
    behavior: domain
    format: mrs
    url: https://raw.githubusercontent.com/xinming7/ruleset-builder/rules/mihomo/custom_direct.mrs
    interval: 86400
    path: ./ruleset/custom_direct.mrs

rules:
  - RULE-SET,my-custom-direct,DIRECT
```

**sing-box 配置**:
```json
{
  "route": {
    "rule_set": [
      {
        "type": "remote",
        "tag": "custom_direct",
        "format": "binary",
        "url": "https://raw.githubusercontent.com/xinming7/ruleset-builder/rules/singbox/custom_direct.srs",
        "update_interval": "1d"
      }
    ]
  }
}
```

## 校验与测试

`Validate` workflow 在 PR、push 到 main、以及每天 UTC 04:00 运行，全程只读，不写 `rules` 分支：

| job | 触发 | 内容 |
|---|---|---|
| `lint-workflows` | 全部 | `actionlint`（版本 + SHA256 双重固定）+ 所有 YAML/JSON 可解析性 |
| `validate-rules` | 全部 | `scripts/validate_rules.py`：域名格式、CIDR 合法性、重复项、`behavior` 与目录一致性、未知字段、产物命名冲突 |
| `contract` | 定时 / 手动 | 源文件 ↔ `rules` 分支产物双向比对（keep 清单豁免）+ 所有产物 raw URL 返回 200 |

本地等价命令：

```bash
pip install -r requirements.txt
python3 scripts/validate_rules.py -v      # 语义校验，退出码 1 = 有 error
bash scripts/fetch-kernel.sh mihomo       # 只下载/校验内核到 dist/，不上传
```

输出前缀 `::warning::` 不会让流水线失败，`::error::` 才会。新增规则前建议本地先跑一遍。

## 手动触发

在 GitHub 仓库的 Actions 页面，可以手动触发构建（workflow_dispatch），支持：
- 选择指定 behavior 类型（domain/ipcidr）
- 强制打包所有文件

内核更新有自己的入口：Actions → **Update Kernel** → Run workflow，可选择只更新 `mihomo` / `sing-box`，或勾选 `force` 忽略版本比对强制重新下载。

校验流水线：Actions → **Validate** → Run workflow（会连带跑一次"源文件 ↔ 产物"契约检查与 URL 可达性检查）。

## 内核版本与自动更新

构建内核不再手工上传，由 `.github/workflows/update-kernel.yml`（**Update Kernel**）维护。产物是两个**固定名、无版本号**的 Release 资产，两个构建 workflow 用固定 URL 拉取，因此内核升级不需要改构建 workflow。

| 内核 | Release 资产 | 上游来源 | 定时策略 |
|---|---|---|---|
| mihomo | `mihomo-linux-amd64` ← `mihomo-linux-amd64-v1-<ver>.gz` | [MetaCubeX/mihomo](https://github.com/MetaCubeX/mihomo) | 每周一 UTC 02:00 自动升级**同 minor** 的 patch 版本 |
| sing-box | `sing-box-linux-amd64` ← `sing-box-<ver>-linux-amd64.tar.gz` | [SagerNet/sing-box](https://github.com/SagerNet/sing-box) | 同上 |

发布位置：<https://github.com/xinming7/ruleset-builder/releases/tag/kernel-v1>

执行流程：`prepare` 读 `kernel-manifest.json` 并生成 matrix → `fetch`（两个内核并行、`fail-fast: false`，一个失败不影响另一个）逐内核查上游 `releases/latest` → 比对版本 → `scripts/fetch-kernel.sh` 下载、解包、`-v`/`version` 自检、**canary 编译**一条真实规则 → 覆盖资产 → `publish` 汇总结果、写回 manifest、重渲染 Release 描述、`gh workflow run` 触发对应构建 workflow 全量重建。

两个内核的差异（资产命名、解包方式、自检与 canary 命令）都收敛在 `scripts/fetch-kernel.sh` 的 `case` 分支里；本地可以直接 `bash scripts/fetch-kernel.sh sing-box` 只做下载与校验、不上传。

同一 Release 内的 `kernel-manifest.json` 记录当前生效版本、SHA256 与更新时间：

```json
{
  "mihomo": "v1.19.33",
  "sing-box": "v1.14.4",
  "updated_at": "2026-11-06T12:00:00Z",
  "assets": {
    "mihomo": { "sha256": "..." },
    "sing-box": { "sha256": "..." }
  }
}
```

安全闸门与注意事项：

- 定时任务只接受**同 minor** 的 patch 升级；跨 minor / major 需手动触发并勾选 `force`
- 上游资产名匹配失败、二进制无法运行、canary 编译失败 → 直接失败退出，**不覆盖**现有内核
- mihomo 固定取 GOAMD64 **v1** 变体（`-v1-`），避免 `v2`/`v3` 在部分 runner 上 SIGILL
- `GITHUB_TOKEN` 产生的 release/push 事件不会触发其它 workflow，因此必须显式 `gh workflow run` 下发重建
- 资产被 `--clobber` 覆盖后旧二进制不在 Release 中保留（不可回溯），历史版本只存在于上游
- Release **描述**由本 workflow 按 manifest 重渲染（顶部带"自动生成"标记），每次运行都会覆盖，不要手工改

回滚方式：从上游下载对应旧版本资产后手工覆盖，并同步修正 manifest。

```bash
gh release upload kernel-v1 mihomo-linux-amd64 --clobber   # 文件需先从上游对应 tag 下载并解压
```
