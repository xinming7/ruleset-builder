#!/usr/bin/env python3
"""规则集语义校验。

构建流程只做 YAML/JSON 语法检查（能解析就算过），本脚本补上"内容是否合法"这一层：
条目格式、CIDR 合法性、重复项、behavior 目录一致性、产物命名冲突、keep 清单有效性。

用法：
    python3 scripts/validate_rules.py            # 校验整个仓库
    python3 scripts/validate_rules.py -v         # 额外打印统计

退出码：0 = 通过（可能有 warning），1 = 有 error。
"""

from __future__ import annotations

import ipaddress
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIHOMO_DIR = ROOT / "mihomo"
SINGBOX_DIR = ROOT / "singbox" / "rules"
KEEP_FILE = ROOT / ".github" / "keep-rulesets.txt"

# mihomo payload 里域名条目的合法形态：example.com / .example.com / *.example.com / +.example.com
_LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
DOMAIN_RE = re.compile(rf"^{_LABEL}(?:\.{_LABEL})+$")
DOMAIN_PREFIXES = ("+.", "*.", ".")

# sing-box 规则支持的字段（本项目实际用到的 + 常用扩展）
SINGBOX_LIST_KEYS = {
    "domain",
    "domain_suffix",
    "domain_keyword",
    "domain_regex",
    "ip_cidr",
    "src_ip_cidr",
}
SINGBOX_SCALAR_KEYS = {
    "port",
    "port_range",
    "network",
    "protocol",
    "clash_mode",
    "process_name",
    "process_path",
    "package_name",
    "query_type",
    "ip_is_private",
    "invert",
}

errors: list[str] = []
warnings: list[str] = []
stats: dict[str, int] = defaultdict(int)


def err(msg: str) -> None:
    errors.append(msg)


def warn(msg: str) -> None:
    warnings.append(msg)


def strip_prefix(entry: str) -> str:
    for p in DOMAIN_PREFIXES:
        if entry.startswith(p):
            return entry[len(p) :]
    return entry


def check_domain(entry: str, where: str) -> None:
    base = strip_prefix(entry)
    if not base:
        err(f"{where}: 域名条目为空（{entry!r}）")
        return
    if not DOMAIN_RE.match(base):
        hint = ""
        if "://" in entry:
            hint = "，看起来是 URL，请只写域名"
        elif "/" in entry:
            hint = "，带路径/斜杠，请只写域名"
        elif " " in entry:
            hint = "，含空格"
        err(f"{where}: 域名格式非法 {entry!r}{hint}")
        return
    if entry != entry.lower():
        warn(f"{where}: 建议改成小写 {entry!r}")


def check_cidr(entry: str, where: str) -> None:
    try:
        net = ipaddress.ip_network(entry, strict=False)
    except ValueError:
        err(f"{where}: 不是合法 IP/CIDR {entry!r}")
        return
    if "/" in entry:
        try:
            strict = ipaddress.ip_network(entry, strict=True)
        except ValueError:
            warn(f"{where}: {entry!r} 主机位不为 0，已按 {net} 处理")
            return
        if strict != net:  # pragma: no cover - 上面已经提前 return
            warn(f"{where}: {entry!r} 规范化后为 {net}")


def collect_yaml_entries(path: Path, behavior: str) -> list[str]:
    import yaml  # 只有校验时需要

    text = path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        err(f"{path.relative_to(ROOT)}: YAML 解析失败 {exc}")
        return []

    if not isinstance(data, dict):
        err(f"{path.relative_to(ROOT)}: 顶层必须是映射（含 behavior / payload）")
        return []

    unknown = set(data) - {"behavior", "payload"}
    if unknown:
        err(f"{path.relative_to(ROOT)}: 未知顶层字段 {sorted(unknown)}")

    declared = data.get("behavior")
    if declared != behavior:
        err(
            f"{path.relative_to(ROOT)}: behavior 应为 {behavior!r}（目录决定），实际 {declared!r}"
        )

    payload = data.get("payload")
    if not isinstance(payload, list) or not payload:
        err(f"{path.relative_to(ROOT)}: payload 必须是非空列表")
        return []

    entries: list[str] = []
    for i, item in enumerate(payload):
        if not isinstance(item, str):
            err(f"{path.relative_to(ROOT)}: payload[{i}] 不是字符串（{item!r}）")
            continue
        value = item.strip()
        if not value:
            err(f"{path.relative_to(ROOT)}: payload[{i}] 为空字符串")
            continue
        if value != item:
            warn(f"{path.relative_to(ROOT)}: payload[{i}] 首尾有空白 {item!r}")
        entries.append(value)
    return entries


def collect_txt_entries(path: Path) -> list[str]:
    entries: list[str] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        value = line.strip()
        if not value:
            continue
        if value.startswith("#"):
            err(f"{path.relative_to(ROOT)}:{lineno}: .txt 规则不支持注释行（{value!r}）")
            continue
        entries.append(value)
    if not entries:
        err(f"{path.relative_to(ROOT)}: 文件没有有效条目")
    return entries


def check_duplicates(entries: list[str], where: str, label: str) -> None:
    dup = [v for v, c in Counter(entries).items() if c > 1]
    for value in sorted(dup):
        warn(f"{where}: 重复条目 {value!r}（{label}）")


def validate_mihomo() -> dict[str, set[str]]:
    """返回 {behavior: {产物名}}，用于后续命名冲突检查。"""
    products: dict[str, set[str]] = {"domain": set(), "ipcidr": set()}
    if not MIHOMO_DIR.is_dir():
        err("mihomo/ 目录不存在")
        return products

    for behavior in ("domain", "ipcidr"):
        beh_dir = MIHOMO_DIR / behavior
        if not beh_dir.is_dir():
            err(f"mihomo/{behavior}/ 目录不存在")
            continue
        files = sorted(p for p in beh_dir.iterdir() if p.suffix in (".yaml", ".txt"))
        if not files:
            warn(f"mihomo/{behavior}/ 下没有任何规则文件")
        for path in files:
            where = str(path.relative_to(ROOT))
            if path.suffix == ".yaml":
                entries = collect_yaml_entries(path, behavior)
            else:
                entries = collect_txt_entries(path)
            for entry in entries:
                if behavior == "domain":
                    check_domain(entry, where)
                else:
                    check_cidr(entry, where)
            check_duplicates(entries, where, behavior)
            stats[f"mihomo/{behavior}"] += len(entries)
            stats["mihomo_files"] += 1
            products[behavior].add(path.stem)
    return products


def validate_singbox() -> set[str]:
    products: set[str] = set()
    if not SINGBOX_DIR.is_dir():
        err("singbox/rules/ 目录不存在")
        return products

    fields = {"version", "rules"}
    for path in sorted(SINGBOX_DIR.glob("*.json")):
        where = str(path.relative_to(ROOT))
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            err(f"{where}: JSON 解析失败 {exc}")
            continue
        if not isinstance(data, dict):
            err(f"{where}: 顶层必须是对象")
            continue

        unknown = set(data) - fields
        if unknown:
            err(f"{where}: 未知顶层字段 {sorted(unknown)}")
        # sing-box rule-set 格式版本，当前内核（1.14.x）要求 5
        if data.get("version") != 5:
            err(f"{where}: version 必须为 5，实际 {data.get('version')!r}")

        rules = data.get("rules")
        if not isinstance(rules, list) or not rules:
            err(f"{where}: rules 必须是非空列表")
            continue

        total = 0
        for idx, rule in enumerate(rules):
            if not isinstance(rule, dict):
                err(f"{where}: rules[{idx}] 不是对象")
                continue
            bad = set(rule) - SINGBOX_LIST_KEYS - SINGBOX_SCALAR_KEYS
            if bad:
                err(f"{where}: rules[{idx}] 含未知字段 {sorted(bad)}")
            for key, value in rule.items():
                loc = f"{where}: rules[{idx}].{key}"
                if key in SINGBOX_SCALAR_KEYS:
                    continue
                if key not in SINGBOX_LIST_KEYS:
                    continue
                if not isinstance(value, list) or not value:
                    err(f"{loc} 必须是非空列表")
                    continue
                total += len(value)
                seen: list[str] = []
                for item in value:
                    if not isinstance(item, str) or not item.strip():
                        err(f"{loc} 含非法条目 {item!r}")
                        continue
                    item = item.strip()
                    if key in ("domain", "domain_suffix"):
                        check_domain(item, loc)
                    elif key == "ip_cidr" or key == "src_ip_cidr":
                        check_cidr(item, loc)
                    elif key == "domain_regex":
                        try:
                            re.compile(item)
                        except re.error as exc:
                            err(f"{loc}: 正则非法 {item!r}（{exc}）")
                    seen.append(item)
                check_duplicates(seen, loc, key)
        stats["singbox"] += total
        stats["singbox_files"] += 1
        products.add(path.stem)
    return products


def validate_naming(mihomo_products: dict[str, set[str]], singbox_products: set[str]) -> None:
    overlap = mihomo_products["domain"] & mihomo_products["ipcidr"]
    for name in sorted(overlap):
        err(
            f"mihomo: {name}.mrs 会被 domain 与 ipcidr 同时产出，"
            f"必须改掉其中一个（产物文件名不含 behavior，会互相覆盖）"
        )
    if not singbox_products and SINGBOX_DIR.is_dir():
        warn("singbox/rules/ 下没有任何 .json 文件")


def validate_keep() -> None:
    """keep 清单的键应当是"没有对应源文件"的产物名；有源文件还写 keep 属于无效条目。"""
    if not KEEP_FILE.is_file():
        return
    names = []
    for line in KEEP_FILE.read_text(encoding="utf-8").splitlines():
        value = line.split("#", 1)[0].strip()
        if value:
            names.append(value)
    sources = {p.stem for p in ROOT.glob("mihomo/*/*.yaml")}
    sources |= {p.stem for p in ROOT.glob("mihomo/*/*.txt")}
    sources |= {p.stem for p in SINGBOX_DIR.glob("*.json")}
    for name in names:
        if name in sources:
            warn(f"{KEEP_FILE.name}: {name!r} 已有源文件，keep 条目不生效（可以删掉）")
    stats["keep"] = len(names)


def main() -> int:
    verbose = "-v" in sys.argv
    mihomo_products = validate_mihomo()
    singbox_products = validate_singbox()
    validate_naming(mihomo_products, singbox_products)
    validate_keep()

    for w in warnings:
        print(f"::warning::{w}")
    for e in errors:
        print(f"::error::{e}")

    print(
        f"\n汇总：mihomo {stats['mihomo_files']} 文件 / {stats['mihomo/domain'] + stats['mihomo/ipcidr']} 条目，"
        f"sing-box {stats['singbox_files']} 文件 / {stats['singbox']} 条目，"
        f"keep {stats['keep']} 条"
    )
    print(f"结果：error {len(errors)}，warning {len(warnings)}")

    if verbose:
        print(f"产物名：mihomo={sorted(mihomo_products['domain'] | mihomo_products['ipcidr'])}")
        print(f"        singbox={sorted(singbox_products)}")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
