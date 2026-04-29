---
name: qx-converter
description: "将 Quantumult X 脚本转换为多平台兼容版本。提供两种方案：Env.js 方案（改写 API + 追加 Env.min.js）和兼容层方案（注入适配层，用户代码零修改）。当用户提到脚本转换、QX 转多平台、Env.js 适配、兼容层注入、将 xxx.js 转换等场景时使用此技能。使用时须向用户说明两种方案差异，由用户选择方案后再执行转换。"
---

# QX 脚本多平台转换工具

将使用 `$prefs`、`$task.fetch`、`$notify`、`$done` 等 Quantumult X 平台特定 API 的脚本，转换为可在 Surge、Loon、Shadowrocket、Stash、Egern、Node.js 等平台运行的版本。

## 两种转换方案

**使用本 Skill 时，必须先向用户说明以下两种方案的区别，由用户决定使用哪种方案。**

| | Env.js 方案 | 兼容层方案 |
|---|---|---|
| **原理** | 改写 API 调用 + 追加 Env.min.js | 注入 ~2KB 适配层，用户代码零修改 |
| **输出大小** | 增加 ~12KB（Env.min.js） | 增加 ~2KB（兼容层） |
| **代码风格** | 改为 `$.http.get`、`$.getdata` 等 | 保留 `$task.fetch`、`$prefs` 等 QX 风格 |
| **可读性** | 统一为 Env.js 风格 | 原样保留，熟悉 QX 更易读 |
| **依赖** | 需 Env.min.js | 无额外文件依赖 |
| **适用场景** | 长期维护、多人协作 | 快速适配、保留原貌 |

### Env.js 方案

```bash
python3 /var/minis/skills/qx-converter/scripts/convert_to_envjs.py \
  -i <输入文件> -o <输出文件>
```

**参数：**

| 参数 | 短写 | 必需 | 说明 |
|------|------|------|------|
| `--input` | `-i` | ✅ | 输入文件路径 |
| `--output` | `-o` | ✅ | 输出文件路径 |
| `--env` | `-e` | ❌ | Env.min.js 路径（默认 `/var/minis/shared/Chavy/Env.min.js`） |
| `--name` | `-n` | ❌ | 脚本名称（默认从 `@Name` 标签或文件名提取） |
| `--force` | `-f` | ❌ | 强制转换，即使检测到已转换过 |

**转换规则：**

| 原 API | 转换后 | 说明 |
|--------|--------|------|
| `$prefs.valueForKey(key)` | `$.getdata(key)` | 读取持久化数据 |
| `$prefs.setValueForKey(val, key)` | `$.setdata(val, key)` | 写入持久化数据 |
| `$notify(title, sub, body)` | `$.msg(title, sub, body)` | 发送通知（支持多行） |
| `$task.fetch({ method:'GET',... })` | `$.http.get({ url, headers })` | GET 请求 |
| `$task.fetch({ method:'POST',... })` | `$.http.post({ url, headers, body })` | POST 请求 |
| `$done()` / `$done({})` | `$.done()` | 完成任务 |

**附加操作：**
1. 脚本头部插入 `const $ = new Env("脚本名")`
2. 末尾追加 Env.min.js
3. 自动从 `@Name` 标签或文件名提取名称
4. 重复转换防护（`--force` 跳过）

### 兼容层方案

```bash
python3 /var/minis/skills/qx-converter/scripts/convert_compat_layer.py \
  -i <输入文件> -o <输出文件>
```

**参数：**

| 参数 | 短写 | 必需 | 说明 |
|------|------|------|------|
| `--input` | `-i` | ✅ | 输入文件路径 |
| `--output` | `-o` | ✅ | 输出文件路径 |
| `--force` | `-f` | ❌ | 强制注入，即使已包含兼容层 |

**原理：** 在脚本头部（`*/` 注释后）注入 IIFE 兼容层：
- 检测到 QX 环境时直接 return 跳过（零开销）
- 在其他平台上为 `$prefs`、`$task.fetch`、`$notify`、`$done` 提供等价实现
- 用户代码完全不变，QX API 调用原样保留

## 支持的目标平台

Surge、Loon、Shadowrocket、Stash、Egern、Quantumult X、Node.js

## 目录结构

```
qx-converter/
├── SKILL.md
├── README.md
└── scripts/
    ├── convert_to_envjs.py      # Env.js 方案转换脚本
    └── convert_compat_layer.py  # 兼容层方案转换脚本
```

## 示例

```bash
# Env.js 方案
python3 /var/minis/skills/qx-converter/scripts/convert_to_envjs.py \
  -i script.js -o script_env.js

# 兼容层方案
python3 /var/minis/skills/qx-converter/scripts/convert_compat_layer.py \
  -i script.js -o script_compat.js
```
