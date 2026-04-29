#!/usr/bin/env python3
"""将 Quantumult X 等平台脚本转换为兼容 Env.js 的多平台脚本 - 通用工具

支持的转换：
  $prefs.valueForKey(key)       → $.getdata(key)
  $prefs.setValueForKey(val,key) → $.setdata(val, key)
  $notify(title, sub, body)      → $.msg(title, sub, body)
  $task.fetch({...})             → $.http.get/post({...})  (移除 method，保留其余属性)
  $done()                        → $.done()

附加操作：
  - 在脚本头部添加 const $ = new Env("脚本名")
  - 将 Env.min.js 内容追加到脚本末尾
"""

import re
import os
import argparse

# 默认 Env.min.js 路径
DEFAULT_ENV_MIN_JS = "/var/minis/shared/Chavy/Env.min.js"


def find_balanced(s, start, open_ch, close_ch):
    """从 start 位置（必须是 open_ch）开始，找到平衡的 close_ch 位置"""
    if start >= len(s) or s[start] != open_ch:
        return -1
    depth = 0
    for i in range(start, len(s)):
        if s[i] == open_ch:
            depth += 1
        elif s[i] == close_ch:
            depth -= 1
            if depth == 0:
                return i
    return -1


def extract_value(obj_str, key):
    """从 JS 对象字面量字符串中提取指定 key 的值（支持嵌套括号）"""
    pattern = re.compile(r'\b' + re.escape(key) + r'\s*:\s*')
    m = pattern.search(obj_str)
    if not m:
        return None
    pos = m.end()
    return _read_value(obj_str, pos)


def _read_value(obj_str, pos):
    """从 obj_str 的 pos 位置读取一个 JS 值"""
    while pos < len(obj_str) and obj_str[pos] in ' \t\n\r':
        pos += 1
    if pos >= len(obj_str):
        return None
    start = pos
    if obj_str[pos] == '{':
        end = find_balanced(obj_str, pos, '{', '}')
        if end == -1:
            return None
        return obj_str[pos:end + 1]
    elif obj_str[pos] == '[':
        end = find_balanced(obj_str, pos, '[', ']')
        if end == -1:
            return None
        return obj_str[pos:end + 1]
    elif obj_str[pos] in ('"', "'"):
        quote = obj_str[pos]
        i = pos + 1
        while i < len(obj_str):
            if obj_str[i] == '\\':
                i += 2
                continue
            if obj_str[i] == quote:
                return obj_str[pos:i + 1]
            i += 1
        return None
    elif obj_str[pos] == '`':
        i = pos + 1
        while i < len(obj_str):
            if obj_str[i] == '\\':
                i += 2
                continue
            if obj_str[i] == '`':
                return obj_str[pos:i + 1]
            i += 1
        return None
    else:
        depth = 0
        i = pos
        while i < len(obj_str):
            c = obj_str[i]
            if c in '([{':
                depth += 1
            elif c in ')]}':
                if depth > 0:
                    depth -= 1
                else:
                    break
            elif c == ',' and depth == 0:
                break
            i += 1
        return obj_str[pos:i].strip()


def _remove_method_key(obj_str):
    """从 JS 对象字面量字符串中移除 'method: <value>'，保留其余所有属性原样不变。
    
    支持简写属性（如 { headers }）和各种值类型（字符串、对象、变量等）。
    会正确跳过字符串内容中的 'method' 匹配。
    """
    result = []
    i = 0
    length = len(obj_str)
    
    while i < length:
        # Skip string literals
        if obj_str[i] in ('"', "'", '`'):
            q = obj_str[i]
            result.append(obj_str[i])
            i += 1
            while i < length:
                if obj_str[i] == '\\' and i + 1 < length:
                    result.append(obj_str[i:i+2])
                    i += 2
                    continue
                result.append(obj_str[i])
                if obj_str[i] == q:
                    i += 1
                    break
                i += 1
            continue
        
        # Try to match 'method' key
        if obj_str[i:i+6] == 'method':
            after_key = i + 6
            # Skip whitespace
            while after_key < length and obj_str[after_key] in ' \t\n\r':
                after_key += 1
            # Check colon
            if after_key < length and obj_str[after_key] == ':':
                # This is 'method: <value>', skip it entirely
                after_colon = after_key + 1
                while after_colon < length and obj_str[after_colon] in ' \t\n\r':
                    after_colon += 1
                # Read the value
                val_end = after_colon
                depth = 0
                while val_end < length:
                    c = obj_str[val_end]
                    # Skip strings inside the value
                    if c in ('"', "'", '`'):
                        q2 = c
                        val_end += 1
                        while val_end < length:
                            if obj_str[val_end] == '\\' and val_end + 1 < length:
                                val_end += 2
                                continue
                            if obj_str[val_end] == q2:
                                val_end += 1
                                break
                            val_end += 1
                        continue
                    if c in '([{':
                        depth += 1
                    elif c in ')]}':
                        if depth > 0:
                            depth -= 1
                        else:
                            break
                    elif c == ',' and depth == 0:
                        break
                    val_end += 1
                
                # Skip trailing comma + whitespace
                skip_end = val_end
                while skip_end < length and obj_str[skip_end] in ' \t\n\r':
                    skip_end += 1
                if skip_end < length and obj_str[skip_end] == ',':
                    skip_end += 1
                else:
                    # No comma after method; try to remove leading comma before method
                    pre_idx = len(result) - 1
                    while pre_idx >= 0 and result[pre_idx] in ' \t\n\r':
                        pre_idx -= 1
                    if pre_idx >= 0 and result[pre_idx] == ',':
                        # Remove trailing comma+ws before method
                        del result[pre_idx:]
                        i = skip_end
                        continue
                
                i = skip_end
                continue
        
        result.append(obj_str[i])
        i += 1
    
    return ''.join(result)


def convert_fetch(content):
    """转换 $task.fetch({...}) 调用为 $.http.get/post({...})，保留完整对象属性（仅移除 method）"""
    result = []
    i = 0
    fetch_sig = '$task.fetch'
    fetch_count = 0

    while i < len(content):
        idx = content.find(fetch_sig, i)
        if idx == -1:
            result.append(content[i:])
            break

        result.append(content[i:idx])
        pos = idx + len(fetch_sig)

        while pos < len(content) and content[pos] in ' \t\n\r':
            pos += 1

        if pos >= len(content) or content[pos] != '(':
            result.append(content[idx:pos])
            i = pos
            continue

        paren_end = find_balanced(content, pos, '(', ')')
        if paren_end == -1:
            result.append(content[idx:])
            break

        brace_abs_start = pos + 1
        while brace_abs_start < paren_end and content[brace_abs_start] in ' \t\n\r':
            brace_abs_start += 1

        if brace_abs_start >= paren_end or content[brace_abs_start] != '{':
            # 参数不是对象字面量（可能是变量），保留原样
            result.append(content[idx:paren_end + 1])
            i = paren_end + 1
            continue

        brace_abs_end = find_balanced(content, brace_abs_start, '{', '}')
        if brace_abs_end == -1:
            result.append(content[idx:])
            break

        obj_str = content[brace_abs_start:brace_abs_end + 1]

        # 检测 method
        method_val = extract_value(obj_str, 'method')
        method = 'GET'
        if method_val:
            m = re.match(r"""['"](\w+)['"]""", method_val)
            if m:
                method = m.group(1).upper()

        # 从对象中移除 method 键，保留其余所有属性原样
        new_obj = _remove_method_key(obj_str)

        if method == 'POST':
            new_call = f'$.http.post({new_obj})'
        else:
            new_call = f'$.http.get({new_obj})'

        result.append(new_call)
        fetch_count += 1
        i = paren_end + 1

    return ''.join(result), fetch_count


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


def is_already_converted(content):
    """检测脚本是否已经转换过（避免重复转换）"""
    indicators = [
        'new Env(',
        '$.http.get({',
        '$.http.post({',
        '$.getdata(',
        '$.setdata(',
    ]
    found = sum(1 for ind in indicators if ind in content)
    return found >= 2


def convert_notify(content):
    """转换 $notify(...) 为 $.msg(...)，支持多行参数"""
    result = []
    i = 0
    sig = '$notify'
    count = 0

    while i < len(content):
        idx = content.find(sig, i)
        if idx == -1:
            result.append(content[i:])
            break

        after = idx + len(sig)
        if after < len(content) and (content[after].isalnum() or content[after] == '_'):
            result.append(content[i:after])
            i = after
            continue

        result.append(content[i:idx])
        pos = after

        while pos < len(content) and content[pos] in ' \t\n\r':
            pos += 1

        if pos >= len(content) or content[pos] != '(':
            result.append(content[idx:pos])
            i = pos
            continue

        paren_end = find_balanced(content, pos, '(', ')')
        if paren_end == -1:
            result.append(content[idx:])
            break

        inner = content[pos + 1:paren_end].strip()
        result.append(f'$.msg({inner})')
        count += 1
        i = paren_end + 1

    return ''.join(result), count


def convert_to_envjs(input_file, env_min_js_path, output_file, script_name=None, force=False):
    """将原始脚本转换为兼容 Env.js 的版本"""
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()

    with open(env_min_js_path, 'r', encoding='utf-8') as f:
        env_min_js = f.read()

    if not force and is_already_converted(content):
        print("⚠️ 检测到脚本可能已经转换过（包含 new Env / $.get 等标记）。")
        print("   使用 --force 参数强制重新转换。")
        return False

    if not script_name:
        script_name = detect_script_name(content, input_file)
    print(f"📋 脚本名称: {script_name}")

    stats = {
        'getdata': 0,
        'setdata': 0,
        'msg': 0,
        'get': 0,
        'post': 0,
        'done': 0,
    }

    # 1. Env.js 初始化
    env_init = f'\n// Env.js 初始化\nconst $ = new Env("{script_name}");\n'
    if '*/' in content:
        content = content.replace('*/', '*/' + env_init, 1)
    else:
        content = env_init + content

    # 2. 替换持久化存储方法
    before = content.count('$.getdata(')
    content = re.sub(
        r'\$prefs\.valueForKey\(\s*([^)]+)\s*\)',
        r'$.getdata(\1)', content
    )
    stats['getdata'] = content.count('$.getdata(') - before

    before = content.count('$.setdata(')
    content = re.sub(
        r'\$prefs\.setValueForKey\(\s*([^,]+)\s*,\s*([^)]+)\s*\)',
        r'$.setdata(\1, \2)', content
    )
    stats['setdata'] = content.count('$.setdata(') - before

    # 3. 替换通知方法
    before = content.count('$.msg(')
    content, notify_count = convert_notify(content)
    stats['msg'] = content.count('$.msg(') - before

    # 4. 转换 $task.fetch
    before_get = content.count('$.http.get(')
    before_post = content.count('$.http.post(')
    content, fetch_count = convert_fetch(content)
    stats['get'] = content.count('$.http.get(') - before_get
    stats['post'] = content.count('$.http.post(') - before_post

    # 5. 处理 $done()
    before = content.count('$.done()')
    content = re.sub(r'\$done\(\s*\{\s*\}\s*\)', '$.done()', content)
    content = re.sub(r'\$done\(\s*\)', '$.done()', content)
    content = re.sub(r'\$done\(\s*(\{[^}]+\})\s*\)', r'$.done(\1)', content)
    stats['done'] = content.count('$.done()') - before

    # 6. 追加 Env.min.js
    content = content + '\n\n' + env_min_js

    os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"\n✅ 转换完成！")
    print(f"   输入: {input_file}")
    print(f"   Env: {env_min_js_path}")
    print(f"   输出: {output_file}")
    print(f"\n=== 修改统计 ===")
    if stats['getdata']:
        print(f"  $.getdata 替换: {stats['getdata']} 次")
    if stats['setdata']:
        print(f"  $.setdata 替换: {stats['setdata']} 次")
    if stats['msg']:
        print(f"  $.msg 替换: {stats['msg']} 次")
    if stats['get']:
        print(f"  $.http.get 替换: {stats['get']} 次")
    if stats['post']:
        print(f"  $.http.post 替换: {stats['post']} 次")
    if stats['done']:
        print(f"  $.done 替换: {stats['done']} 次")
    total = sum(stats.values())
    print(f"  ──────────────")
    print(f"  总计: {total} 处修改")
    print(f"  new Env 插入: 1 次")
    print(f"  Env.min.js 追加: 1 次")
    return True


def main():
    parser = argparse.ArgumentParser(
        description='将脚本转换为兼容 Env.js 的版本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基本用法
  python3 convert_to_envjs.py -i script.js -o script_env.js

  # 指定脚本名称
  python3 convert_to_envjs.py -i script.js -o script_env.js -n "MyScript"

  # 使用自定义 Env.min.js 路径
  python3 convert_to_envjs.py -i script.js -e /path/to/Env.min.js -o script_env.js

  # 强制重新转换
  python3 convert_to_envjs.py -i script.js -o script_env.js --force
"""
    )
    parser.add_argument('--input', '-i', required=True, help='输入文件路径（要转换的JS文件）')
    parser.add_argument('--env', '-e', default=DEFAULT_ENV_MIN_JS,
                        help=f'Env.min.js 文件路径（默认: {DEFAULT_ENV_MIN_JS}）')
    parser.add_argument('--output', '-o', required=True, help='输出文件路径')
    parser.add_argument('--name', '-n', default=None,
                        help='脚本名称（用于 new Env("名称")，默认自动检测）')
    parser.add_argument('--force', '-f', action='store_true',
                        help='强制转换，即使检测到脚本已经转换过')

    args = parser.parse_args()
    convert_to_envjs(args.input, args.env, args.output, args.name, args.force)


if __name__ == '__main__':
    main()
