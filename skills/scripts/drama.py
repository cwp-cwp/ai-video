#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 视频创作平台 · 命令行客户端

只依赖 Python 标准库。用来替代手写 curl，统一处理：
  - X-Token 认证与会话保存
  - {code,msg,data} 响应校验（code != 0 直接报错退出）
  - 异步任务的轮询
  - 分镜保存前的字段自检（防整包覆盖丢数据）

用法示例：
  python drama.py login --base http://localhost:18080/video-service/api --email a@b.c --password xxx
  python drama.py get /project/list
  python drama.py get /storyboard/content/12 --out shots.json
  python drama.py post /project/create --json '{"name":"雨夜","type":"连续剧","imageSize":"9:16"}'
  python drama.py post /asset/character/batch-generate-image --json '[1,2,3]'
  python drama.py wait storyboard <taskId>
  python drama.py audit --project 12                    # 体检服务器上的分镜（P0/P1/P2 + 台词时长表）
  python drama.py audit --project 12 --file shots.json  # 体检本地改好的文件
  python drama.py audit --project 12 --file shots.json --out report.json
  python drama.py check-storyboard --project 12 --file shots.json   # 旧名字，等价于 audit
  python drama.py save-storyboard --project 12 --file shots.json    # 无 P0 才写库
"""
import argparse
import difflib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SESSION = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".session.json")

TASK_PATHS = {
    "script": "/script/task/{}",
    "storyboard": "/storyboard/task/{}",
    "asset": "/asset/image-task/{}",
    "voice": "/asset/voice-task/{}",
    "dialogue": "/storyboard/voice-task/{}",
}


def die(msg, code=1):
    print("ERROR: " + str(msg), file=sys.stderr)
    sys.exit(code)


def load_session():
    if os.path.exists(SESSION):
        with open(SESSION, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_session(data):
    with open(SESSION, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def normalize_path(path):
    """规范化接口路径

    Git Bash / MSYS 会把以 "/" 开头的参数当成文件路径转换（/auth/me → D:/.../auth/me），
    所以这里既接受 "auth/me" 也接受 "/auth/me"，并对已经被转换的盘符路径给出明确提示。
    """
    if path.startswith("http://") or path.startswith("https://"):
        return path
    if len(path) > 2 and path[1] == ":" and path[2] == "/":
        die("路径被 Git Bash 转成了 Windows 路径：%s\n"
            "请去掉开头的斜杠（写成 auth/me），或在命令前加 MSYS_NO_PATHCONV=1" % path)
    return path if path.startswith("/") else "/" + path


def request(method, path, base=None, token=None, body=None, timeout=300):
    sess = load_session()
    base = (base or sess.get("base") or "").rstrip("/")
    token = token or sess.get("token")
    if not base:
        die("没有服务地址，先执行 login，或用 --base 指定")
    url = normalize_path(path)
    if not url.startswith("http"):
        url = base + url
    data = None
    headers = {"Accept": "application/json"}
    if token:
        headers["X-Token"] = token
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            new_token = resp.headers.get("X-New-Token")
            if new_token and token:
                sess["token"] = new_token
                save_session(sess)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        die("HTTP %s %s\n%s" % (e.code, url, raw[:600]))
    except urllib.error.URLError as e:
        die("连不上 %s：%s\n（便携版请先运行 apache-tomcat-10.1.59/start.bat）" % (url, e.reason))
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if isinstance(payload, dict) and "code" in payload and payload.get("code") not in (0, 200, "0", "200"):
        # 注意：平台成功码实测为 200（文档写的是 0），两种都放行
        die("业务失败 code=%s msg=%s" % (payload.get("code"), payload.get("msg")))
    return payload.get("data") if isinstance(payload, dict) and "data" in payload else payload


def cmd_login(args):
    data = request("POST", "/auth/login", base=args.base,
                   body={"email": args.email, "password": args.password}, token="")
    token = (data or {}).get("token")
    if not token:
        die("登录返回里没有 token：%s" % data)
    save_session({"base": args.base.rstrip("/"), "token": token,
                  "userId": (data or {}).get("id"), "email": args.email})
    print("登录成功 userId=%s，会话已保存" % (data or {}).get("id"))


def cmd_call(args):
    body = json.loads(args.json) if args.json else None
    data = request(args.method, args.path, base=args.base, body=body)
    text = json.dumps(data, ensure_ascii=False, indent=2) if not isinstance(data, str) else data
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print("已写入 %s（%d 字符）" % (args.out, len(text)))
    else:
        print(text)


def cmd_wait(args):
    tmpl = TASK_PATHS.get(args.kind)
    if not tmpl:
        die("未知任务类型 %s，可选：%s" % (args.kind, ", ".join(TASK_PATHS)))
    deadline = time.time() + args.timeout
    last = None
    while time.time() < deadline:
        data = request("GET", tmpl.format(args.task_id)) or {}
        status = (data.get("status") or "").lower()
        if status != last:
            print("[%s] status=%s progress=%s %s" % (
                time.strftime("%H:%M:%S"), status, data.get("progress"),
                (data.get("message") or "")[:120]))
            last = status
        if status in ("completed", "success", "finished"):
            print("任务完成")
            if args.show_result:
                print(json.dumps(data.get("result"), ensure_ascii=False, indent=2)[:4000])
            return
        if status in ("failed", "error", "cancelled"):
            die("任务失败：%s" % (data.get("message") or data.get("errorMessage") or data))
        time.sleep(args.interval)
    die("等待超时（%ds），任务可能仍在跑，可稍后再查" % args.timeout)


def load_assets(base, project_id):
    """拉项目三类资产的 name 集合，用于分镜引用校验

    任一接口取不到就返回 None —— 宁可跳过校验，也不要把所有资产名误报成 WARN。
    """
    names = {"characters": set(), "scenes": set(), "props": set()}
    for key, path in (("characters", "/asset/character/list/"),
                      ("scenes", "/asset/scene/list/"),
                      ("props", "/asset/prop/list/")):
        try:
            data = request("GET", path + str(project_id), base=base)
        except SystemExit:
            print("WARN  取资产列表失败，跳过资产名一致性校验（先在平台建好资产再重跑）")
            return None
        for item in data if isinstance(data, list) else []:
            if item.get("name"):
                names[key].add(item["name"])
    return names


# ==================== 质量体检引擎 ====================
# 单一引擎：audit / check-storyboard / save-storyboard 全走这里，避免两套阈值打架。

CPS = 4.0                  # 中文口播舒适语速：字/秒
MAX_SPEAK = 5.2            # 口播上限：超过就会「截断 / 急促」
MAX_DUR, MIN_DUR = 15, 2   # H3 单镜上限 / 过短阈值
ACTION_PER_SEC = 1.2       # 每秒最多承载几个「观众能看清」的动作
CLOSE_TYPES = {"近景", "特写", "大特写", "中近景"}

ABSTRACT_WORDS = ["很美", "震撼", "氛围", "电影感", "高级", "精致", "唯美",
                  "引人入胜", "充满张力", "张力十足", "视觉冲击"]
MENTAL_WORDS = ["心里", "想到", "回忆起", "觉得", "意识到", "感到", "明白",
                "内心", "心情", "思绪", "感慨"]


def _cjk(s):
    """统计中文字数（台词语速按中文字算）"""
    return sum(1 for c in (s or "") if "\u4e00" <= c <= "\u9fff")


def _strip_meta(desc):
    """去掉历史上手工注入的元信息（【视角·重要】说明），它们不是画面动作"""
    s = desc or ""
    for mark in ("【视角·重要】", "【视角】"):
        i = s.find(mark)
        if i >= 0:
            s = s[:i]
    return s.strip()


def _action_units(desc):
    """粗估可读动作数：按标点切分，长度≥3 的片段算一个动作单元"""
    segs = [x.strip() for x in re.split(r"[，,。；;！!？?]", _strip_meta(desc)) if x.strip()]
    return max(1, len([x for x in segs if len(x) >= 3]))


def _disp_width(s):
    import unicodedata
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in str(s))


def _pad(s, width):
    """按终端显示宽度补空格（中文算 2 列），保证表格对齐"""
    s = str(s)
    return s + " " * max(0, width - _disp_width(s))


def audit_storyboard(base, project_id, data, target=None):
    """分镜质量体检，返回分级问题列表

    P0 阻塞（写坏数据 / 出不了片）、P1 质量问题（影响成片）、P2 建议
    每条：{level, shot, field, msg, fix}
    """
    issues = []

    def add(level, no, field, msg, fix=""):
        issues.append({"level": level, "shot": no, "field": field, "msg": msg, "fix": fix})

    shots = data.get("shots")
    if not isinstance(shots, list) or not shots:
        add("P0", None, "shots", "shots 为空，平台会拒绝或把分镜清空", "先 GET 基线再改")
        return issues

    nums = [s.get("shotNumber") for s in shots]
    if nums != list(range(1, len(shots) + 1)):
        add("P0", None, "shotNumber", "shotNumber 不是 1..%d 连续" % len(shots), "重编号后再保存")

    assets = load_assets(base, project_id)
    total = 0.0
    types, moves = [], []
    fixed = 0

    for idx, s in enumerate(shots):
        no = s.get("shotNumber") or idx + 1
        desc = (s.get("description") or "").strip()
        dur = float(s.get("duration") or 0)
        stype = (s.get("shotType") or "").strip()
        move = (s.get("cameraMovement") or "").strip()
        total += dur
        types.append(stype)
        moves.append(move)
        if "固定" in move:
            fixed += 1

        # ---------- P0：结构 ----------
        if not desc:
            add("P0", no, "description", "描述为空", "写「起点 → 唯一动作 → 终点」")
        elif len(desc) < 8:
            add("P1", no, "description", "描述只有 %d 字，太短没法拍" % len(desc), "补到「起点→动作→终点」")
        if dur <= 0:
            add("P0", no, "duration", "时长缺失", "给 3–15 秒")
        if assets:
            for n in s.get("characters") or []:
                if n not in assets["characters"]:
                    add("P0", no, "characters", "角色「%s」不在资产列表" % n, "改成资产里的名字，或先建资产")
            loc = s.get("location")
            if loc and loc not in assets["scenes"]:
                add("P0", no, "location", "场景「%s」不在资产列表" % loc, "同上")
            for n in s.get("propNames") or []:
                if n not in assets["props"]:
                    add("P0", no, "propNames", "道具「%s」不在资产列表" % n, "同上")
        if not s.get("sceneAssetId"):
            add("P0", no, "sceneAssetId", "缺场景 id —— 生成时没有场景参考图", "回填资产 id")
        if s.get("characters") and not s.get("characterAssetIds"):
            add("P0", no, "characterAssetIds", "有角色但缺 characterAssetIds —— 人物一致性没参考", "回填资产 id")

        # ---------- P1：时长 ----------
        if dur > MAX_DUR:
            add("P1", no, "duration", "%.0f 秒超过 H3 上限 15 秒" % dur, "拆镜，或压缩动作")
        elif 0 < dur < MIN_DUR:
            add("P1", no, "duration", "%.1f 秒过短，观众读不完" % dur, "≥2 秒（冲击点除外）")

        # ---------- P1：台词 vs 时长（关键：别截断、别急促） ----------
        # 一镜要能把台词说完：舒适 4 字/秒，快顶 5.2 字/秒。
        # 时间不够 → 要么说到一半被截断，要么语速被拉得急促，两种都难看。
        text = "".join((d.get("text") or "") for d in (s.get("dialogue") or []))
        chars = _cjk(text)
        if chars and dur > 0:
            need = chars / CPS          # 按舒适语速说完这句需要几秒
            rate = chars / dur
            if need > MAX_DUR:
                # 单镜最长 15 秒，这段台词按舒适语速都说不完 → 加时长没用，只能拆
                add("P1", no, "duration",
                    "台词 %d 字按 4 字/秒需 %.0f 秒，超过单镜 %d 秒上限 → 一镜说不完，必须拆"
                    % (chars, need, MAX_DUR),
                    "按句号/呼吸点拆成 %d 镜，或删到 %d 字以内"
                    % (int(need // MAX_DUR) + 1, int(MAX_DUR * CPS)))
            elif rate > MAX_SPEAK:
                add("P1", no, "duration",
                    "台词 %d 字挤进 %.0f 秒（%.2f 字/秒，超 %.1f 上限）→ 会截断或急促"
                    % (chars, dur, rate, MAX_SPEAK),
                    "时长提到 ≥%.1f 秒，或把这句拆到下一镜" % need)
            elif dur < need:
                add("P1", no, "duration",
                    "台词 %d 字按 4 字/秒约需 %.1f 秒，只给了 %.0f 秒 → 会说得急促"
                    % (chars, need, dur),
                    "时长提到 ≥%.1f 秒，或删 %d 字" % (need, max(1, chars - int(dur * CPS))))
            elif rate < 2.0 and chars >= 8:
                add("P2", no, "duration",
                    "台词 %d 字占 %.0f 秒（%.1f 字/秒），节奏偏拖" % (chars, dur, rate),
                    "缩到 %.1f 秒，或补动作/反应" % need)

        # ---------- P1：动作量 ----------
        if desc and dur > 0:
            units = _action_units(desc)
            if units / dur > ACTION_PER_SEC:
                add("P1", no, "description",
                    "%d 个动作塞进 %.0f 秒（%.1f 个/秒），生成时会被压扁" % (units, dur, units / dur),
                    "删无功能动作 / 合并 / 拆镜，别靠加时长硬塞")

        # ---------- P1：可拍性 ----------
        hit = [w for w in ABSTRACT_WORDS if w in desc]
        if hit:
            add("P1", no, "description", "抽象词：%s —— 拍不出来" % "、".join(hit),
                "翻译成可见的光线/材质/动作")
        hit = [w for w in MENTAL_WORDS if w in desc]
        if hit:
            add("P1", no, "description", "心理描写：%s —— 镜头拍不到" % "、".join(hit),
                "外化成动作或表情")

        # ---------- P2：建议 ----------
        if stype in CLOSE_TYPES and not s.get("characters"):
            add("P2", no, "characters", "「%s」是近景类却没有角色，确认是空镜还是漏填" % stype, "空镜删角色，漏填补角色")
        if not (s.get("soundEffect") or "").strip():
            add("P2", no, "soundEffect", "声音为空，短剧一半质感来自声音", "填具体声源（雨打铁皮棚、远处车声）")
        if not (s.get("h3VideoPrompt") or s.get("msrVideoPrompt") or "").strip():
            add("P2", no, "prompt", "还没有视频提示词", "生成提示词后再进视频生成")

    # ---------- 全局节奏 ----------
    # 注意：连续同景别本身不是错——长对话、正反打、长镜头都会在一个景别里待很久。
    # 只有「景别 + 运镜 + 场景」三件完全一样，才是真的没切；仅作提醒（P2），不阻塞。
    for i in range(1, len(types)):
        if types[i] and types[i] == types[i - 1]:
            same_move = bool(moves[i]) and moves[i] == moves[i - 1]
            same_loc = (bool(shots[i].get("location"))
                        and shots[i].get("location") == shots[i - 1].get("location"))
            if same_move and same_loc:
                add("P2", shots[i].get("shotNumber") or i + 1, "shotType",
                    "与上一镜同为「%s」且同运镜同场景，观众看不出这次切镜" % types[i],
                    "想强调就变一档景别或换机位角度；长对话/正反打本来就同景别，可忽略")

    if len(shots) >= 6 and fixed >= len(shots) * 0.9:
        add("P2", None, "cameraMovement", "%d/%d 镜都是固定机位" % (fixed, len(shots)),
            "给几镜有动机的推/移/跟")

    from collections import Counter
    valid = [t for t in types if t]
    if valid:
        top, cnt = Counter(valid).most_common(1)[0]
        if cnt > len(shots) * 0.5:
            add("P2", None, "shotType", "「%s」占 %d/%d，景别过于单一" % (top, cnt, len(shots)),
                "按「信息在哪个尺度」重新分配景别")

    if target and total and abs(total - target) > target * 0.15:
        add("P1", None, "duration",
            "总时长 %.0f 秒，目标 %.0f 秒（差 %+.0f）" % (total, target, total - target),
            "按场次增减镜头，不要单独拉长某镜")

    # ---------- 续接 ----------
    # 字段缺省 = 系统默认 true，只有显式 False 才算关掉。
    off = [s for s in shots if s.get("usePrevVideoRef") is False]
    if len(shots) > 1 and len(off) == len(shots):
        add("P1", None, "usePrevVideoRef", "全部镜头都显式关了续接（系统默认是开的）",
            "删掉这个字段让默认值生效")
    prev_loc = None
    for s in shots:
        loc = s.get("location")
        if prev_loc and loc and loc != prev_loc and s.get("usePrevVideoRef"):
            add("P2", s.get("shotNumber"), "usePrevVideoRef",
                "换了场景（%s → %s）还开着续接" % (prev_loc, loc), "跨场关掉，避免把上一场画面带进来")
        prev_loc = loc or prev_loc

    return issues


def dialogue_rows(shots):
    """每镜「台词字数 vs 时长」对照表 —— 一眼看出哪镜说不完 / 太急促"""
    rows = []
    for idx, s in enumerate(shots):
        text = "".join((d.get("text") or "") for d in (s.get("dialogue") or []))
        chars = _cjk(text)
        if not chars:
            continue
        dur = float(s.get("duration") or 0)
        need = chars / CPS               # 按 4 字/秒说完需要几秒
        rate = (chars / dur) if dur else 0
        if dur <= 0:
            verdict = "缺时长"
        elif need > MAX_DUR:
            verdict = "必须拆镜"
        elif rate > MAX_SPEAK:
            verdict = "截断/急促"
        elif dur < need:
            verdict = "偏急"
        elif rate < 2.0 and chars >= 8:
            verdict = "偏拖"
        else:
            verdict = "OK"
        rows.append({"shot": s.get("shotNumber") or idx + 1, "chars": chars,
                     "duration": dur, "rate": round(rate, 1),
                     "need": round(need, 1), "verdict": verdict})
    return rows


LEVEL_TITLE = {
    "P0": "阻塞 —— 必须改，否则写坏数据或出不了片",
    "P1": "质量问题 —— 影响成片，建议全部修掉",
    "P2": "建议 —— 有余力再改",
}


def report(issues, shots, out_json=None):
    total = sum(float(s.get("duration") or 0) for s in shots)
    print("=== 分镜体检 ===")
    print("镜头 %d 个 | 总时长 %.0f 秒 | 平均 %.1f 秒"
          % (len(shots), total, total / len(shots) if shots else 0))

    rows = dialogue_rows(shots)
    if rows:
        print("\n=== 台词 vs 时长（舒适 4 字/秒，>%.1f 字/秒会截断/急促）===" % MAX_SPEAK)
        print("  " + _pad("镜号", 6) + _pad("字数", 6) + _pad("时长", 7)
              + _pad("字/秒", 8) + _pad("需秒", 7) + "判定")
        for r in rows:
            print("  " + _pad(r["shot"], 6) + _pad(r["chars"], 6)
                  + _pad("%.0fs" % r["duration"], 7) + _pad("%.1f" % r["rate"], 8)
                  + _pad("%.1f" % r["need"], 7) + r["verdict"])

    for level in ("P0", "P1", "P2"):
        group = [i for i in issues if i["level"] == level]
        if not group:
            continue
        print("\n[%s] %s —— %d 条" % (level, LEVEL_TITLE[level], len(group)))
        for i in group:
            tag = ("镜%s · " % i["shot"]) if i.get("shot") else ""
            print("  - %s%s：%s" % (tag, i["field"], i["msg"]))
            if i.get("fix"):
                print("      → %s" % i["fix"])
    n = {k: sum(1 for i in issues if i["level"] == k) for k in ("P0", "P1", "P2")}
    print("\n合计：P0 %d / P1 %d / P2 %d" % (n["P0"], n["P1"], n["P2"]))
    if out_json:
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump({"summary": {"shots": len(shots), "totalDuration": total, **n},
                       "dialogue": rows, "issues": issues}, f, ensure_ascii=False, indent=1)
        print("JSON 报告已写入 %s" % out_json)
    return n


def cmd_audit(args):
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        # 不给 --file 就直接体检服务器上已经存的分镜
        data = request("GET", "/storyboard/content/" + str(args.project), base=args.base) or {}
    issues = audit_storyboard(args.base, args.project, data, args.target)
    n = report(issues, data.get("shots") or [], args.out)
    sys.exit(1 if n["P0"] else 0)


def cmd_save(args):
    with open(args.file, "r", encoding="utf-8") as f:
        data = json.load(f)
    issues = audit_storyboard(args.base, args.project, data)
    n = report(issues, data.get("shots") or [])
    if n["P0"]:
        die("有 P0 阻塞问题，已阻止保存（避免把分镜写坏）")
    if n["P1"]:
        print("\n注意：还有 %d 条 P1 质量问题，建议改完再保存（当前不阻塞）。" % n["P1"])
    request("PUT", "/storyboard/save/" + str(args.project), base=args.base, body=data)
    print("已保存 %d 个镜头" % len(data.get("shots") or []))


# ==================== 剧情覆盖体检 ====================
# 目的：把「剧情被删减」变成可测量的问题。
# 压缩会在两级发生：小说→剧本、剧本→分镜。这里查的是剧本→分镜这一级（能程序化查的那级）。

_PUNCT = re.compile(r"[\s，。、；：！？…—\-“”‘’《》〈〉()（）\[\]【】,.;:!?\"'~·]")


def _norm(s):
    return _PUNCT.sub("", s or "")


def coverage_check(script, storyboard):
    """逐场、逐句核对：剧本里的台词，分镜里还在不在"""
    plots = (script or {}).get("plots") or []
    shots = (storyboard or {}).get("shots") or []

    spoken = []
    for s in shots:
        for d in (s.get("dialogue") or []):
            t = _norm(d.get("text"))
            if t:
                spoken.append((s.get("shotNumber"), t))
    all_text = "".join(t for _, t in spoken)

    rows, lost = [], []
    for i, p in enumerate(plots):
        no = i + 1
        loc = (p.get("location") or "").strip()
        dlg = p.get("dialogues") or []
        cover = [n for n in range(1, len(shots) + 1)
                 if (shots[n - 1].get("location") or "").strip() == loc] if loc else []
        got = 0
        for d in dlg:
            t = _norm(d.get("text"))
            if not t:
                continue
            hit = (t in all_text) or any(t in x or x in t for _, x in spoken)
            if hit:
                got += 1
            else:
                lost.append({"scene": no, "location": loc,
                             "character": d.get("character"), "text": d.get("text")})
        rows.append({"scene": no, "location": loc, "time": p.get("time"),
                     "dialogues": len(dlg), "kept": got, "shots": len(cover)})
    return rows, lost


# ==================== 出片前资源检查 ====================
# 分镜挂的资产如果还没出图，生成提示词和视频都会缺参考，人物/场景一致性直接崩。
# 所以在「生成提示词」「生成视频」之前必须过一遍这道闸。

SCENE_IMG_FIELDS = ("wideAngleImageUrl", "panoramaImageUrl", "frontImageUrl",
                    "rightImageUrl", "backImageUrl", "leftImageUrl", "referenceImageUrl")


def load_asset_objs(base, project_id):
    """取三类资产的完整对象（含图片字段），按 id 索引"""
    out = {"characters": {}, "scenes": {}, "props": {}}
    for key, path in (("characters", "/asset/character/list/"),
                      ("scenes", "/asset/scene/list/"),
                      ("props", "/asset/prop/list/")):
        data = request("GET", path + str(project_id), base=base) or []
        for item in data if isinstance(data, list) else []:
            out[key][item.get("id")] = item
    return out


def preflight_check(base, project_id, data):
    """逐镜核对：挂的资产在不在、图有没有出"""
    shots = data.get("shots") or []
    objs = load_asset_objs(base, project_id)
    problems = []

    def add(no, kind, msg, fix):
        problems.append({"shot": no, "kind": kind, "msg": msg, "fix": fix})

    for s in shots:
        no = s.get("shotNumber")
        # 顺序铁律：分镜 → 场面调度 → 提示词 → 视频。没有调度就不许出提示词。
        segs = (s.get("staging") or {}).get("segments") or []
        if not segs:
            add(no, "调度", "没有场面调度（staging 为空）", "先跑 generate-staging，再生成提示词")
        sid = s.get("sceneAssetId")
        if not sid:
            add(no, "场景", "没有绑定 sceneAssetId", "回填场景 id")
        else:
            sc = objs["scenes"].get(sid)
            if not sc:
                add(no, "场景", "sceneAssetId=%s 在资产库里不存在" % sid, "检查场景是否被删")
            elif not any(sc.get(f) for f in SCENE_IMG_FIELDS):
                add(no, "场景", "场景「%s」一张图都没生成" % sc.get("name"), "先出场景图")

        for cid in (s.get("characterAssetIds") or []):
            c = objs["characters"].get(cid)
            if not c:
                add(no, "角色", "characterAssetId=%s 不存在" % cid, "检查角色是否被删")
            elif not c.get("imageUrl"):
                add(no, "角色", "角色「%s」没有形象图" % c.get("name"), "先出角色图")
        for pid in (s.get("propAssetIds") or []):
            p = objs["props"].get(pid)
            if not p:
                add(no, "道具", "propAssetId=%s 不存在" % pid, "检查道具是否被删")
            elif not p.get("imageUrl"):
                add(no, "道具", "道具「%s」没有图片" % p.get("name"), "先出道具图")
    return problems, objs


# ==================== H3 提示词台词核对 ====================
# H3 的台词只认中文：提示词里必须把台词原句用 <d>...</d> 包住写进去。
# 光检查"有没有中文"不够——生成提示词时 LLM 经常漏一句、只写半句、把台词改写，
# 或者凭空多编一句；这些都不报错，直接变成成片里的错词、漏词。
# 句数只能做参考（一句台词允许拆成多个 <d> 跨子镜头停顿），所以判据是逐字比对文本。

CJK_RE = re.compile(r"[\u4e00-\u9fff]")
D_TAG_RE = re.compile(r"<d>(.*?)</d>", re.S)
LANG_TAG_RE = re.compile(r"^\s*\[[^\]]{1,12}\]\s*")
PAREN_RE = re.compile(r"[（(\[【][^）)\]】]{0,30}[）)\]】]")
NORM_RE = re.compile(r"[^\u4e00-\u9fffA-Za-z0-9]")


def _prompt_of(shot):
    for k in ("h3VideoPrompt", "msrVideoPrompt"):
        if shot.get(k):
            return shot[k]
    return ""


def _norm_text(s):
    """比对用规范化：去掉括号里的表演提示、标点空白，只留中文/字母/数字"""
    return NORM_RE.sub("", PAREN_RE.sub("", s or ""))


def _d_lines(prompt):
    """提取 <d> 里的台词（剥掉 [Chinese] 之类语言标记）"""
    out = []
    for raw in D_TAG_RE.findall(prompt or ""):
        t = LANG_TAG_RE.sub("", raw.strip()).strip()
        if t:
            out.append(t)
    return out


def _dialogue_gap(prompt_text, storyboard_text):
    """逐字比对，返回 (漏写片段, 多写片段, 漏写字数, 多写字数)；入参均已规范化。"""
    sm = difflib.SequenceMatcher(None, prompt_text, storyboard_text, autojunk=False)
    missing, extra = [], []
    m_chars = e_chars = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        if i2 > i1:                                  # 提示词有、分镜没有
            extra.append(prompt_text[i1:i2])
            e_chars += i2 - i1
        if j2 > j1:                                  # 分镜有、提示词没有
            missing.append(storyboard_text[j1:j2])
            m_chars += j2 - j1
    return missing, extra, m_chars, e_chars


def cmd_promptcheck(args):
    if not args.file and args.project is None:
        die("要么给 --project（从服务器拉分镜），要么给 --file（本地分镜 JSON）")
    if args.file:
        data = json.load(open(args.file, "r", encoding="utf-8"))
    else:
        data = request("GET", "/storyboard/content/" + str(args.project), base=args.base) or {}
    shots = data.get("shots") or []
    if not shots:
        die("分镜为空")

    p0, p1, p2 = [], [], []
    ok = 0
    total_shots = 0
    total_lines = 0
    for s in shots:
        dlg = [d for d in (s.get("dialogue") or []) if (d.get("text") or "").strip()]
        if not dlg:
            continue
        sb_norm = _norm_text("".join(d.get("text") or "" for d in dlg))
        if not sb_norm:
            continue
        total_shots += 1
        total_lines += len(dlg)
        no = s.get("shotNumber")
        p = _prompt_of(s)

        sb_text = "".join(d.get("text") or "" for d in dlg).strip()
        d_text = ""      # 提取到 <d> 之后再填

        def bad(bucket, why, missing=None, extra=None, d_cnt=0, dup=None):
            bucket.append({"shot": no, "why": why, "lines": len(dlg), "d_tags": d_cnt,
                           "storyboard": sb_text, "prompt": d_text,
                           "missing": missing or [], "extra": extra or [],
                           "dup": dup or []})

        if not p:
            bad(p0, "提示词为空")
            continue
        if not CJK_RE.search(p):
            bad(p0, "整条提示词里没有一个中文字")
            continue
        ds = _d_lines(p)
        d_text = "".join(ds).strip()
        if not ds:
            bad(p0, "有中文但没写在 <d></d> 里")
            continue

        missing, extra, m_chars, e_chars = _dialogue_gap(_norm_text(d_text), sb_norm)
        changed = m_chars + e_chars
        ratio = changed / max(len(sb_norm), 1)     # 差异占分镜台词的比例
        # 短句（<8 字）单字差异多是"了/啦"这类语气词，归 P2；长句里漏字且占比高才算改写
        rewritten = m_chars >= 2 or (m_chars >= 1 and len(sb_norm) >= 8 and ratio >= 0.2)
        # 重复：多出来的那段本身就是分镜台词（同一句写了两遍/多遍，成片会重复说）
        dup = [x for x in extra if len(x) >= 2 and (x in sb_norm or sb_norm in x)]
        if rewritten:
            bad(p0, "漏写/改写了 %d 字" % m_chars, missing, extra, len(ds))
        elif dup:
            bad(p1, "同一句台词重复写 %d 字" % sum(len(x) for x in dup),
                missing, extra, len(ds), dup)
        elif e_chars >= 3:
            bad(p1, "多写了 %d 字（分镜里没有这句）" % e_chars, missing, extra, len(ds))
        elif changed:
            bad(p2, "个别字有出入", missing, extra, len(ds))
        else:
            ok += 1

    print("=== H3 提示词台词核对 ===")
    print("分镜 %d 镜 | 有台词 %d 镜 / %d 句 | 逐字一致 %d 镜"
          % (len(shots), total_shots, total_lines, ok))

    if not (p0 or p1 or p2):
        print("\n全部通过：分镜台词与提示词 <d> 台词逐字一致。")
        return

    def dump(title, rows, indent="  "):
        print("\n" + title)
        for r in rows:
            print("%s- 镜%-3s %s（分镜 %d 句 / <d> %d 处）"
                  % (indent, r["shot"], r["why"], r["lines"], r["d_tags"]))
            if r.get("storyboard"):
                print("%s    分镜：%s" % (indent, r["storyboard"][:80]))
            if r.get("prompt"):
                print("%s    提示：%s" % (indent, r["prompt"][:80]))
            if r["missing"]:
                print("%s    漏写「%s」" % (indent, "」「".join(r["missing"])))
            if r["extra"]:
                label = "重复" if r.get("dup") else "多写"
                print("%s    %s「%s」" % (indent, label, "」「".join(r["extra"])))

    if p0:
        dump("[P0] 提示词台词和分镜对不上 —— 出片会漏词/错词，必须重生成", p0)
    if p1:
        dump("[P1] 台词遍数/内容不对 —— 同一句重复说，或多了分镜里没有的话", p1)
    if p2:
        dump("[P2] 个别字有出入 —— 不影响理解，介意就改", p2)

    if args.out:
        json.dump({"p0": p0, "p1": p1, "p2": p2},
                  open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("\nJSON 已写入 %s" % args.out)

    print("\n修法：单独重生成这几镜提示词（`batch-generate-msr-prompt` 只传这几个序号），"
          "再跑一遍本检查。P2 可忽略。")
    sys.exit(1 if (p0 or p1) else 0)


def cmd_preflight(args):
    if args.file:
        data = json.load(open(args.file, "r", encoding="utf-8"))
    else:
        data = request("GET", "/storyboard/content/" + str(args.project), base=args.base) or {}
    shots = data.get("shots") or []
    if not shots:
        die("分镜为空，先拿到分镜基线")

    problems, objs = preflight_check(args.base, args.project, data)
    nch, nsc, npr = len(objs["characters"]), len(objs["scenes"]), len(objs["props"])

    print("=== 出片前资源检查 ===")
    print("分镜 %d 镜 | 资产库：角色 %d / 场景 %d / 道具 %d" % (len(shots), nch, nsc, npr))

    if not problems:
        print("\n全部通过：每镜挂的场景/角色/道具都在，且都有图。")
        print("可以生成提示词和视频。")
        return

    # 按资产汇总（比逐镜列更好读）
    from collections import OrderedDict
    grouped = OrderedDict()
    for p in problems:
        key = (p["kind"], p["msg"])
        grouped.setdefault(key, []).append(p["shot"])

    print("\n[P0] 缺调度 / 缺图 / 缺资产 —— 必须先补齐，否则出片没有参考、一致性会崩")
    for (kind, msg), shots_ in grouped.items():
        heads = ", ".join(str(x) for x in shots_[:12]) + ("..." if len(shots_) > 12 else "")
        print("  - [%s] %s（%d 镜：%s）" % (kind, msg, len(shots_), heads))

    if args.out:
        json.dump({"summary": {"shots": len(shots), "problems": len(problems)},
                   "problems": problems},
                  open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("\nJSON 已写入 %s" % args.out)

    print("\n【不要继续】先把上面缺的补上（调度 → 生成；资产 → 出图），再重新跑本检查。")
    sys.exit(1)


def cmd_coverage(args):
    if args.script:
        script = json.load(open(args.script, "r", encoding="utf-8"))
    else:
        script = request("GET", "/script/content/" + str(args.project), base=args.base) or {}
    if args.storyboard:
        sb = json.load(open(args.storyboard, "r", encoding="utf-8"))
    else:
        sb = request("GET", "/storyboard/content/" + str(args.project), base=args.base) or {}

    rows, lost = coverage_check(script, sb)
    shots = sb.get("shots") or []
    total_dlg = sum(r["dialogues"] for r in rows)
    total_kept = sum(r["kept"] for r in rows)

    print("=== 剧情覆盖体检（剧本 → 分镜）===")
    print("剧本 %d 场 / 台词 %d 句 | 分镜 %d 镜（%.0f 秒）"
          % (len(rows), total_dlg, len(shots),
             sum(float(s.get("duration") or 0) for s in shots)))
    print("\n%-4s %-14s %-6s %-8s %s" % ("场", "地点", "台词", "镜头数", "保留"))
    for r in rows:
        flag = "  ← 整场没有镜头" if r["shots"] == 0 else ""
        print("%-4d %-14s %-6d %-8d %d/%d%s"
              % (r["scene"], r["location"][:12], r["dialogues"], r["shots"],
                 r["kept"], r["dialogues"], flag))

    rate = (total_kept / total_dlg * 100) if total_dlg else 100
    print("\n台词覆盖率 %.0f%%（%d/%d）" % (rate, total_kept, total_dlg))
    if lost:
        print("\n丢失的台词（分镜里找不到）：")
        for x in lost:
            print("  场%d %s · %s：%s" % (x["scene"], x["location"], x["character"], x["text"]))
    empty = [r for r in rows if r["shots"] == 0]
    if empty:
        print("\n整场没拍（最严重）：")
        for r in empty:
            print("  场%d %s" % (r["scene"], r["location"]))

    if args.out:
        json.dump({"summary": {"scenes": len(rows), "dialogues": total_dlg,
                               "kept": total_kept, "rate": round(rate, 1),
                               "shots": len(shots)},
                   "scenes": rows, "lost": lost},
                  open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("\nJSON 已写入 %s" % args.out)
    # 有整场丢失 / 覆盖率低于 95% 就算不通过，便于流水线卡口
    sys.exit(1 if (empty or rate < 95) else 0)


def main():
    # --base 既可写在子命令前，也可写在子命令后：
    # 子命令用 SUPPRESS 作为默认值，没传时不会覆盖顶层已解析到的值。
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--base", default=argparse.SUPPRESS,
                        help="服务地址，如 http://localhost:18080/video-service/api")

    p = argparse.ArgumentParser(description="AI 视频创作平台 CLI")
    p.add_argument("--base", default=None, help="服务地址，如 http://localhost:18080/video-service/api")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("login", parents=[common], help="邮箱密码登录并保存会话")
    sp.add_argument("--email", required=True)
    sp.add_argument("--password", required=True)
    sp.set_defaults(func=cmd_login)

    for name, method in (("get", "GET"), ("post", "POST"), ("put", "PUT"), ("delete", "DELETE")):
        sp = sub.add_parser(name, parents=[common], help="发 %s 请求" % method)
        sp.add_argument("path", help="接口路径，如 project/list（不要前导斜杠）")
        sp.add_argument("--json", default=None, help="请求体（JSON 字符串）")
        sp.add_argument("--out", default=None, help="把结果写到文件")
        sp.set_defaults(func=cmd_call, method=method)

    sp = sub.add_parser("wait", parents=[common], help="轮询异步任务直到完成")
    sp.add_argument("kind", choices=list(TASK_PATHS.keys()))
    sp.add_argument("task_id")
    sp.add_argument("--interval", type=int, default=6)
    sp.add_argument("--timeout", type=int, default=3600)
    sp.add_argument("--show-result", action="store_true")
    sp.set_defaults(func=cmd_wait)

    sp = sub.add_parser("audit", parents=[common],
                        help="分镜质量体检（P0/P1/P2 + 台词 vs 时长表），不写库")
    sp.add_argument("--project", type=int, required=True,
                    help="项目/分集 id（不给 --file 时从服务器拉分镜）")
    sp.add_argument("--file", default=None, help="体检本地分镜文件；不给则拉服务器上的")
    sp.add_argument("--target", type=float, default=None, help="目标总时长（秒），用于总长校验")
    sp.add_argument("--out", default=None, help="把完整报告写成 JSON（含台词表）")
    sp.set_defaults(func=cmd_audit)

    sp = sub.add_parser("coverage", parents=[common],
                        help="剧情覆盖体检：剧本的台词/场次在分镜里有没有被删掉")
    sp.add_argument("--project", type=int, required=True)
    sp.add_argument("--script", default=None, help="本地剧本 JSON（不给则拉服务器）")
    sp.add_argument("--storyboard", default=None, help="本地分镜 JSON（不给则拉服务器）")
    sp.add_argument("--out", default=None, help="把报告写成 JSON")
    sp.set_defaults(func=cmd_coverage)

    sp = sub.add_parser("preflight", parents=[common],
                        help="出片前资源检查：分镜挂的资产图有没有全部生成（缺图则退出码 1）")
    sp.add_argument("--project", type=int, required=True)
    sp.add_argument("--file", default=None, help="本地分镜 JSON（不给则拉服务器）")
    sp.add_argument("--out", default=None, help="把缺失清单写成 JSON")
    sp.set_defaults(func=cmd_preflight)

    sp = sub.add_parser("promptcheck", parents=[common],
                        help="H3 提示词台词核对：分镜台词与 <d> 台词逐字比对（漏句/重复/多句/改写都会报）")
    sp.add_argument("--project", type=int, default=None, help="项目/分集 id（不给 --file 时必填）")
    sp.add_argument("--file", default=None, help="本地分镜 JSON（不给则拉服务器）")
    sp.add_argument("--out", default=None, help="把问题清单写成 JSON")
    sp.set_defaults(func=cmd_promptcheck)

    # 旧名字保留，行为与 audit 完全一致（同一个引擎，避免两套阈值）
    sp = sub.add_parser("check-storyboard", parents=[common], help="[同 audit] 分镜体检，不写库")
    sp.add_argument("--project", type=int, required=True)
    sp.add_argument("--file", default=None)
    sp.add_argument("--target", type=float, default=None)
    sp.add_argument("--out", default=None)
    sp.set_defaults(func=cmd_audit)

    sp = sub.add_parser("save-storyboard", parents=[common], help="体检通过（无 P0）后保存分镜")
    sp.add_argument("--project", type=int, required=True)
    sp.add_argument("--file", required=True)
    sp.set_defaults(func=cmd_save)

    args = p.parse_args()
    if not hasattr(args, "base"):
        args.base = None
    args.func(args)


if __name__ == "__main__":
    main()
