#!/usr/bin/env python3
"""将 Quantumult X 脚本转换为多平台兼容版本 — 兼容层方案

与 convert_to_envjs.py（引入 Env.min.js）不同，本脚本采用兼容层方法：
在脚本头部注入一段精简的平台适配代码，让 QX 原生 API（$prefs、$task.fetch、
$notify、$done）在其他平台（Surge/Loon/Shadowrocket/Stash/Egern/Node.js）上
也能正常工作。

转换后的脚本保留 QX 风格的 API 调用（$prefs.valueForKey、$task.fetch 等），
无需改写用户代码，仅靠注入的兼容层实现跨平台运行。

QX 环境下原生支持这些 API，兼容层会在检测到 QX 时直接 return 跳过，
不执行任何 polyfill 定义。

用法:
    python3 convert_compat_layer.py -i input.js -o output.js
    python3 convert_compat_layer.py -i input.js -o output.js --force
"""

import re
import os
import argparse

# ──────────────────────────────────────────────────────────────────
# 兼容层代码（注入到脚本头部）
# ──────────────────────────────────────────────────────────────────
COMPAT_LAYER = r"""
// ─── QX 多平台兼容层 ───
// 让 $prefs / $task.fetch / $notify / $done 等 QX API 在 Surge/Loon/Shadowrocket/Stash/Egern/Node.js 上正常工作
// QX 环境下原生支持这些 API，直接跳过整个兼容层
(function() {
  if (typeof $task !== 'undefined') return; // QX 环境，无需兼容

  // ── 环境检测 ──
  function _detectEnv() {
    if (typeof Egern !== 'undefined') return 'Egern';
    if (typeof $environment !== 'undefined' && $environment['surge-version']) return 'Surge';
    if (typeof $environment !== 'undefined' && $environment['stash-version']) return 'Stash';
    if (typeof $loon !== 'undefined') return 'Loon';
    if (typeof $rocket !== 'undefined') return 'Shadowrocket';
    if (typeof module !== 'undefined' && module.exports) return 'Node.js';
    return 'Unknown';
  }
  const _env = _detectEnv();

  // ── $prefs 兼容 ──
  // QX: $prefs.valueForKey(key) / $prefs.setValueForKey(val, key)
  // Surge/Loon/Stash/Shadowrocket/Egern: $persistentStore.read(key) / $persistentStore.write(val, key)
  if (typeof $prefs === 'undefined') {
    const _store = {};
    $prefs = {
      valueForKey(key) {
        switch (_env) {
          case 'Surge':
          case 'Loon':
          case 'Stash':
          case 'Shadowrocket':
          case 'Egern':
            return $persistentStore.read(key);
          case 'Node.js':
            return _store[key] || null;
          default:
            return null;
        }
      },
      setValueForKey(val, key) {
        switch (_env) {
          case 'Surge':
          case 'Loon':
          case 'Stash':
          case 'Shadowrocket':
          case 'Egern':
            return $persistentStore.write(val, key);
          case 'Node.js':
            _store[key] = val;
            return true;
          default:
            return false;
        }
      }
    };
  }

  // ── $task.fetch 兼容 ──
  // QX: $task.fetch(opts).then(resp => {...}, err => {...})
  // Surge/Loon/Stash/Shadowrocket/Egern: $httpClient.get/post(opts, callback)
  if (typeof $task === 'undefined') {
    $task = {
      fetch(opts) {
        return new Promise((resolve, reject) => {
          const method = (opts.method || 'GET').toUpperCase();
          const reqOpts = Object.assign({}, opts);
          delete reqOpts.method;

          const callback = (err, resp, body) => {
            if (err) {
              reject({ error: err });
            } else {
              const result = {
                statusCode: resp ? (resp.status || resp.statusCode) : 0,
                status: resp ? (resp.status || resp.statusCode) : 0,
                headers: resp ? resp.headers : {},
                body: body || (resp ? resp.body : '')
              };
              resolve(result);
            }
          };

          switch (_env) {
            case 'Surge':
            case 'Loon':
            case 'Stash':
            case 'Shadowrocket':
            case 'Egern':
              if (method === 'POST') {
                if (reqOpts.body && reqOpts.headers && !reqOpts.headers['Content-Type'] && !reqOpts.headers['content-type']) {
                  reqOpts.headers['content-type'] = 'application/x-www-form-urlencoded';
                }
                if (reqOpts.headers) {
                  delete reqOpts.headers['Content-Length'];
                  delete reqOpts.headers['content-length'];
                }
                $httpClient.post(reqOpts, callback);
              } else {
                $httpClient.get(reqOpts, callback);
              }
              break;
            case 'Node.js':
              try {
                const http = require('http');
                const https = require('https');
                const urlObj = new URL(reqOpts.url);
                const isHttps = urlObj.protocol === 'https:';
                const lib = isHttps ? https : http;
                const reqData = reqOpts.body || '';
                const nodeOpts = {
                  hostname: urlObj.hostname,
                  port: urlObj.port || (isHttps ? 443 : 80),
                  path: urlObj.pathname + urlObj.search,
                  method: method,
                  headers: Object.assign({}, reqOpts.headers || {})
                };
                if (reqData) {
                  nodeOpts.headers['Content-Length'] = Buffer.byteLength(reqData);
                }
                const req = lib.request(nodeOpts, (res) => {
                  let data = '';
                  res.on('data', chunk => data += chunk);
                  res.on('end', () => {
                    resolve({
                      statusCode: res.statusCode,
                      status: res.statusCode,
                      headers: res.headers,
                      body: data
                    });
                  });
                });
                req.on('error', err => reject({ error: err.message || String(err) }));
                if (reqData) req.write(reqData);
                req.end();
              } catch (e) {
                reject({ error: 'Node.js http error: ' + e.message });
              }
              break;
            default:
              reject({ error: 'Unsupported environment: ' + _env });
          }
        });
      }
    };
  }

  // ── $notify 兼容 ──
  // Surge/Loon/Stash/Shadowrocket/Egern: $notification.post(title, subt, desc, opts)
  if (typeof $notify === 'undefined') {
    $notify = function(title, subt, desc, opts) {
      switch (_env) {
        case 'Surge':
        case 'Loon':
        case 'Stash':
        case 'Shadowrocket':
        case 'Egern':
          $notification.post(title, subt, desc, opts);
          break;
        case 'Node.js':
          console.log(`[Notify] ${title} | ${subt || ''} | ${desc || ''}`);
          break;
      }
    };
  }

  // ── $done 兼容 ──
  if (typeof $done === 'undefined') {
    $done = function(val) {
      if (_env === 'Node.js') process.exit(0);
    };
  }
})();
// ─── 兼容层结束 ───
"""


def detect_script_name(content, filename):
    """从脚本内容或文件名中提取脚本名称"""
    m = re.search(r'@Name[：:]\s*(.+)', content)
    if m:
        name = m.group(1).strip()
        name = re.split(r'\s*@\w+', name)[0].strip()
        return name
    m = re.search(r'@title\s+(.+)', content)
    if m:
        name = m.group(1).strip()
        name = re.split(r'\s*@\w+', name)[0].strip()
        return name
    basename = os.path.basename(filename)
    name = os.path.splitext(basename)[0]
    for suffix in ('_orig', '_original', '_source', '_qx', '_quantumult'):
        if name.endswith(suffix):
            name = name[:-len(suffix)]
            break
    return name


def has_compat_layer(content):
    """检测脚本是否已包含兼容层"""
    markers = [
        'QX 多平台兼容层',
        '_detectEnv',
        'QX_COMPAT_LAYER',
    ]
    found = sum(1 for m in markers if m in content)
    return found >= 2


def convert_with_compat_layer(input_file, output_file, force=False):
    """使用兼容层方法转换脚本"""
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 检测是否已有兼容层
    if not force and has_compat_layer(content):
        print("⚠️ 检测到脚本已包含兼容层。使用 --force 参数强制重新注入。")
        return False

    name = detect_script_name(content, input_file)
    print(f"📋 脚本名称: {name}")
    print(f"🔧 转换方案: 兼容层注入（不修改用户代码）")

    # 注入兼容层
    if '*/' in content:
        content = content.replace('*/', '*/' + COMPAT_LAYER, 1)
    else:
        content = COMPAT_LAYER + '\n' + content

    # 保存
    os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(content)

    # 统计原始 QX API 调用数（兼容层不修改它们，只是让它们能跨平台运行）
    user_code = content.split('QX 多平台兼容层')[1] if 'QX 多平台兼容层' in content else content
    api_counts = {
        '$prefs.valueForKey': len(re.findall(r'\$prefs\.valueForKey', user_code)),
        '$prefs.setValueForKey': len(re.findall(r'\$prefs\.setValueForKey', user_code)),
        '$task.fetch': len(re.findall(r'\$task\.fetch', user_code)),
        '$notify': len(re.findall(r'(?<!\$notification\.)\$notify\s*\(', user_code)),
        '$done': len(re.findall(r'(?<!\$\.)\$done\s*\(', user_code)),
    }

    print(f"\n✅ 转换完成！")
    print(f"  输入: {input_file}")
    print(f"  输出: {output_file}")
    print(f"\n=== 兼容层适配 ===")
    total = 0
    for api, count in api_counts.items():
        if count:
            print(f"  {api}: {count} 处（兼容层自动适配）")
            total += count
    print(f"  ──────────────")
    print(f"  总计: {total} 处 QX API 由兼容层适配")
    print(f"  兼容层注入: 1 次（约 2KB）")
    print(f"  用户代码修改: 0 处")
    print(f"\n=== 两种方案对比 ===")
    print(f"  兼容层方案: 注入 ~2KB 适配代码，用户代码零修改")
    print(f"  Env.js 方案: 追加 ~12KB Env.min.js，需改写 API 调用")
    return True


def main():
    parser = argparse.ArgumentParser(
        description='将 QX 脚本转换为多平台兼容版本（兼容层方案）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基本用法
  python3 convert_compat_layer.py -i script.js -o script_compat.js

  # 强制重新注入
  python3 convert_compat_layer.py -i script.js -o script_compat.js --force
"""
    )
    parser.add_argument('--input', '-i', required=True, help='输入文件路径')
    parser.add_argument('--output', '-o', required=True, help='输出文件路径')
    parser.add_argument('--force', '-f', action='store_true', help='强制注入，即使已包含兼容层')
    args = parser.parse_args()
    convert_with_compat_layer(args.input, args.output, args.force)


if __name__ == '__main__':
    main()
