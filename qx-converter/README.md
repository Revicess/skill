# QX 脚本多平台转换工具

将 Quantumult X 平台脚本（`$prefs`、`$task.fetch`、`$notify`、`$done`）转换为兼容 Surge、Loon、Shadowrocket、Stash、Egern、Node.js 的版本。

## 两种方案

| | Env.js 方案 | 兼容层方案 |
|---|---|---|
| **原理** | 改写 API + 追加 Env.min.js | 注入 ~2KB 适配层 |
| **体积增加** | ~12KB | ~2KB |
| **代码风格** | 统一为 Env.js 风格 | 保留 QX 原风格 |
| **适用场景** | 长期维护 | 快速适配、保留原貌 |

## Env.js 方案

```bash
python3 scripts/convert_to_envjs.py -i <输入> -o <输出>
```

| 参数 | 短写 | 说明 |
|------|------|------|
| `--input` | `-i` | 输入文件（必需） |
| `--output` | `-o` | 输出文件（必需） |
| `--env` | `-e` | Env.min.js 路径（默认 `/var/minis/shared/Chavy/Env.min.js`） |
| `--name` | `-n` | 脚本名称（默认自动提取） |
| `--force` | `-f` | 强制转换 |

**转换规则：**

| 原 API | 转换后 |
|--------|--------|
| `$prefs.valueForKey(key)` | `$.getdata(key)` |
| `$prefs.setValueForKey(val, key)` | `$.setdata(val, key)` |
| `$notify(title, sub, body)` | `$.msg(title, sub, body)` |
| `$task.fetch({method:'GET',...})` | `$.http.get({url, headers})` |
| `$task.fetch({method:'POST',...})` | `$.http.post({url, headers, body})` |
| `$done()` / `$done({})` | `$.done()` |

## 兼容层方案

```bash
python3 scripts/convert_compat_layer.py -i <输入> -o <输出>
```

| 参数 | 短写 | 说明 |
|------|------|------|
| `--input` | `-i` | 输入文件（必需） |
| `--output` | `-o` | 输出文件（必需） |
| `--force` | `-f` | 强制注入 |

兼容层在脚本头部注入 IIFE，QX 环境自动跳过，其他平台为 `$prefs`/`$task.fetch`/`$notify`/`$done` 提供等价实现，用户代码零修改。

## 目录结构

```
qx-converter/
├── SKILL.md
├── README.md
└── scripts/
    ├── convert_to_envjs.py      # Env.js 方案
    └── convert_compat_layer.py  # 兼容层方案
```

## 依赖

- Python 3（标准库 re、os、argparse）
- Env.js 方案需 **Env.min.js**（默认 `/var/minis/shared/Chavy/Env.min.js`）
  - 来源仓库：[chavyleung/scripts](https://github.com/chavyleung/scripts)（GPL 协议）
  - 文件位于仓库根目录，正式版可直接引用 `Env.min.js` 或 `Env.js`（可读版本）
  - 本工具的默认 Env.min.js 已内置于 `/var/minis/shared/Chavy/` 下
