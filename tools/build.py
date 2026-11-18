# -*- coding: utf-8 -*-
"""漫画記事LPの組み立て道具（manga-flow-kit）。

使い方:
  python3 tools/build.py prompts  work/<作品>   台本(script.json)から画像生成の指示文と jobs.md を作る
  python3 tools/build.py status   work/<作品>   どの画像ができていて、どれが残っているかを出す
  python3 tools/build.py assemble work/<作品>   できたコマと黒帯を縦に並べて final.png / final.jpg にする

画像そのものは作らない（画像は Codex の image_gen で作る）。手順は AGENTS.md。
台本の書き方は templates/script.example.json と docs/決まり.md。
"""
import json
import os
import re
import sys

KIT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

ASPECT = {
    "3:2": "Landscape 3:2 image (1536x1024)",
    "2:3": "Portrait 2:3 image (1024x1536)",
    "1:1": "Square 1:1 image (1024x1024)",
}

DEFAULT_STYLE = (
    "STYLE: Clean digital Japanese advertorial web-manga (広告漫画) for a general adult audience. "
    "SEMI-REALISTIC adult faces and proportions: realistic head-to-body ratio, small realistic eyes with a single highlight, "
    "a real nose bridge. Thin, uniform, clean black ink lineart (NOT shaky, NOT sketchy). "
    "FLAT CEL SHADING with 1-2 hard-edged shadow steps, no airbrush gradients on skin. Muted natural palette. "
    "Emotional beats may use soft gradient backgrounds with sparkles; shock beats use blank white or black backgrounds "
    "with radial concentration lines; sweat drops and short diagonal blush lines on cheeks. "
    "Backgrounds are simple low-density line drawings drawn in paler, thinner lines than the characters. "
    "NOT moe, NOT big anime eyes, NOT chibi, NOT painterly, NOT 3D render, NOT western comic."
)

POS_WORDS = {
    "TR": "upper-RIGHT corner, cut off by the top and right panel edges",
    "TL": "upper-LEFT corner, cut off by the top and left panel edges",
    "R": "RIGHT side, middle height, cut off by the right panel edge",
    "L": "LEFT side, middle height, cut off by the left panel edge",
    "BR": "lower-RIGHT corner, cut off by the bottom and right edges",
    "BL": "lower-LEFT corner, cut off by the bottom and left edges",
    "TC": "top-center, cut off by the top edge",
    "BC": "bottom-center, cut off by the bottom edge",
}

SHAPES = {
    "ellipse": "plain WHITE speech balloon (smooth ellipse, thin black outline)",
    "burst": "WHITE jagged BURST balloon (shout, extra-bold text)",
    "thought": "WHITE thought balloon with a dotted outline",
    "black": "SOLID BLACK ellipse with WHITE text (inner voice)",
}

SIZE_REL = {
    "S": "about 1/17 of the panel height per character (never smaller than 1/19)",
    "M": "about 1/16 of the panel height per character (never smaller than 1/18)",
    "L": "about 1/14 of the panel height per character (never smaller than 1/16)",
}

TEXT_KINDS = ("speech", "box", "mono", "sfx", "label")


def load(work):
    p = os.path.join(work, "script.json")
    if not os.path.exists(p):
        sys.exit(f"script.json が見つかりません: {p}")
    s = json.load(open(p, encoding="utf-8"))
    for u in s["pages"]:
        if u["type"] == "panel":
            for c in u.get("cast", []):
                if c not in s["cast"]:
                    sys.exit(f"{u['id']}: cast に {c} がありません")
            for t in u.get("text", []):
                if t["kind"] not in TEXT_KINDS:
                    sys.exit(f"{u['id']}: text の kind が不明です: {t['kind']}")
                if t.get("pos") and t["pos"] not in POS_WORDS:
                    sys.exit(f"{u['id']}: pos が不明です: {t['pos']}")
            if u.get("aspect", "3:2") not in ASPECT:
                sys.exit(f"{u['id']}: aspect は {list(ASPECT)} のどれか")
    return s


def plain(text):
    return re.sub(r"[《》|]", "", text)


def rel(work, *parts):
    return os.path.relpath(os.path.join(work, *parts), KIT)


def refs(kind, limit=2):
    """お手本（refs/style = 画風、refs/lettering = 文字入れ）の画像。名前順で最大 limit 枚"""
    d = os.path.join(KIT, "refs", kind)
    if not os.path.isdir(d):
        return []
    fs = sorted(f for f in os.listdir(d) if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp")))
    return [os.path.relpath(os.path.join(d, f), KIT) for f in fs[:limit]]


STYLE_REF_NOTE = ("The image(s) attached AFTER the character sheet(s) are ART STYLE references ONLY: match their line weight, "
                  "cel shading, palette and level of detail. Do NOT copy their faces, identities, composition or any text.")
LETTER_REF_NOTE = ("The SECOND attached image is a TYPOGRAPHY STYLE reference ONLY (font feel, vessel style, line weight, "
                   "text size relative to the panel): do NOT copy its artwork, layout or wording.")


# ─────────────── 指示文 ───────────────
def cast_prompt(s, cid):
    c = s["cast"][cid]
    return "\n".join([
        f"TASK: character reference sheet for {c['name']}.",
        "CHARACTER:",
        f"- {c['desc']}",
        "LAYOUT: the same person shown twice side by side on a plain white background: LEFT = front-facing bust-up with a neutral "
        "expression, RIGHT = full body standing, front view. Same face, hairstyle, age, build and outfit in both.",
    ] + ([STYLE_REF_NOTE.replace("AFTER the character sheet(s) ", "")] if refs("style") else []) + [
        s.get("style") or DEFAULT_STYLE,
        "OUTPUT: Landscape 3:2 image (1536x1024).",
        "ABSOLUTELY NO text, letters, numbers, labels, name tags, logos or watermarks anywhere.",
    ])


def art_prompt(s, u):
    L = [f"TASK: manga panel {u['id']} (artwork only, no text)."]
    sheets = [c for c in u.get("cast", []) if s["cast"][c].get("sheet", True)]
    if sheets:
        L.append("Keep the SAME face, hairstyle, age, build and outfit as the attached character sheet(s). "
                 "Same person(s), recognizable in every panel.")
    if u.get("cast"):
        L.append("CHARACTERS:")
        L += [f"- {s['cast'][c]['desc']}" for c in u["cast"]]
    L.append("SCENE / COMPOSITION:")
    L.append(u["scene"])
    zones = sorted(set(POS_WORDS[t["pos"]].split(",")[0] for t in u.get("text", [])
                       if t["kind"] in ("speech", "box") and t.get("pos")))
    if zones:
        L.append("TEXT ZONES: keep these areas as plain, low-detail background with NO face, hand or important object there "
                 "(speech balloons will be added later): " + "; ".join(zones) + ".")
    L.append("Draw NO speech balloons, NO boxes and NO text of any kind.")
    if refs("style"):
        L.append(STYLE_REF_NOTE if sheets else STYLE_REF_NOTE.replace("AFTER the character sheet(s) ", ""))
    L.append(s.get("style") or DEFAULT_STYLE)
    L.append("OUTPUT:")
    L.append(f"{ASPECT[u.get('aspect', '3:2')]}, single panel, no border, filled edge to edge.")
    L.append("ABSOLUTELY NO text, letters, numbers, captions, labels, logos, watermarks, signatures or sound effects anywhere. "
             "Add NO extra characters beyond those described.")
    return "\n".join(L)


def letter_prompt(s, u):
    items = [t for t in u.get("text", [])]
    L = [
        "You are a professional Japanese manga letterer for a commercial advertorial manga (広告漫画). "
        "The FIRST attached image is a finished TEXT-FREE panel with NO balloons. Add the Japanese text elements below EXACTLY "
        "as specified: draw each vessel (balloon / box) AND its text, adapting placement to the actual composition. "
        "NEVER cover a face, hands or the key acting." + (" " + LETTER_REF_NOTE if refs("lettering") else ""),
        "READING ORDER (absolute): Japanese right-to-left, top-to-bottom. The FIRST element below is the RIGHTMOST / TOPMOST. "
        "The order below IS the reading order.",
        "TYPOGRAPHY: vertical writing (縦書き). Two-digit numbers and short Latin abbreviations are set TATE-CHU-YOKO "
        "(horizontal inside the vertical column, one character cell). Character pitch is uniform, columns evenly spaced with "
        "about 0.3 character of air between columns; small kana (っゃゅょ) sit slightly up-right. Dialogue = antique-style kana "
        "with gothic kanji (アンチック体), clean uniform medium-bold weight. NEVER mincho/serif, NEVER rounded gothic. "
        "Narration boxes = same family, slightly lighter. Shouts = extra-bold. All dialogue and narration in this panel use the "
        "SAME character size unless stated. Line breaks: use EXACTLY the column breaks given (each 「…」 segment = one vertical "
        "column). Never start a column with ー、。…っゃゅょ or !?.",
        "VESSELS: white balloons with a thin black outline, NO tail unless needed (attribute the speaker by placing the balloon "
        "right beside that character). Narration = WHITE VERTICAL rectangular box with a thin black outline, placed in a corner "
        "and CUT OFF by the panel edge. Each vessel is sized to its text plus about one character of margin on every side. "
        "The text block is CENTERED inside its vessel. Never let text cross the panel edge.",
        f"ADD EXACTLY these {len(items)} text elements and NOTHING else (no extra balloons, no extra words):",
    ]
    for n, t in enumerate(items, 1):
        k = t["kind"]
        where = POS_WORDS.get(t.get("pos", "TR"))
        if k == "label":
            L.append(f"{n}. [name tag] small WHITE horizontal rectangle with a thin black outline, near the {where}, "
                     f"horizontal black gothic text 「{t['text']}」, about 1/22 of the panel height per character. "
                     "Place it on the background next to the character, never over the face.")
            continue
        if k == "sfx":
            L.append(f"{n}. [sfx] Hand-drawn style sound effect 「{t['text']}」, LARGE (each character at least 1/12 of the "
                     f"panel height), dark grey with a thin white outline, near the {where}. No balloon.")
            continue
        if k == "mono":
            L.append(f"{n}. [bare text, no vessel] small mutter 「{plain(t['text'])}」 drawn directly on the art near the {where}.")
            continue
        cols = " ／ ".join("「" + c + "」" for c in re.sub(r"[《》]", "", t["text"]).split("|") if c)
        size = SIZE_REL[t.get("size", "M")]
        if k == "box":
            L.append(f"{n}. [narration box] WHITE vertical rectangular box in the {where}. Character size {size}. "
                     f"COLUMNS (right to left, exactly these): {cols}")
        else:
            who = t.get("who")
            name = s["cast"][who]["name"] if who in s["cast"] else "the speaking character"
            look = s["cast"][who].get("look", "") if who in s["cast"] else ""
            sp = f"{name} ({look})" if look else name
            tail = ""
            others = [s["cast"][c]["name"] for c in u.get("cast", []) if c != who]
            if who and others:
                tail = (f" Place it beside {name}'s head; if a tail is needed it MUST point toward {name}'s mouth "
                        f"(NEVER toward {', '.join(others)}).")
            shape = SHAPES[t.get("shape", "ellipse")]
            L.append(f"{n}. [speech] SPEAKER: {sp}. {shape} in the {where}.{tail} Character size {size}. "
                     f"COLUMNS (right to left, exactly these): {cols}")
        reds = re.findall(r"《(.+?)》", t["text"])
        if reds:
            L.append(f"   EMPHASIS (color only): render {', '.join('「' + r + '」' for r in reds)} in dark RED (#C41C1C), "
                     "same font, same size, no bracket marks drawn.")
        if t.get("hint"):
            L.append(f"   PLACEMENT NOTE: {t['hint']}")
    L.append("PRESERVE the artwork completely: do not redraw, recolor, crop, pad or add borders; keep the image size and aspect. "
             "Do not add any characters, marks or symbols not listed. Do not draw the bracket characters 《》.")
    L.append("Write ALL text EXACTLY character-for-character as given above. No additions, no rephrasing, no extra punctuation.")
    return "\n".join(L)


def do_prompts(work):
    s = load(work)
    pd = os.path.join(work, "prompts")
    os.makedirs(pd, exist_ok=True)
    os.makedirs(os.path.join(work, "expected"), exist_ok=True)
    jobs = ["# jobs — 上から順に1行ずつ image_gen を呼ぶ",
            "",
            "各行: 指示文ファイル → 保存先（添付する画像）。指示文は一字一句そのまま渡す（要約・翻訳・言い換えをしない）。",
            "保存したら開いて確かめる（AGENTS.md の手順4）。",
            ""]
    jobs.append("## A. キャラクターの設定画（1人1枚）")
    for cid, c in s["cast"].items():
        if not c.get("sheet", True):
            continue
        open(os.path.join(pd, f"cast_{cid}.txt"), "w", encoding="utf-8").write(cast_prompt(s, cid))
        att = refs("style")
        jobs.append(f"- [ ] {rel(work, 'prompts', f'cast_{cid}.txt')} → {rel(work, 'cast', f'{cid}.png')}"
                    + (f"（添付: {', '.join(att)}）" if att else ""))
    jobs += ["", "## B. コマの絵（文字も吹き出しも無し）"]
    for u in s["pages"]:
        if u["type"] != "panel":
            continue
        open(os.path.join(pd, f"{u['id']}_art.txt"), "w", encoding="utf-8").write(art_prompt(s, u))
        att = [rel(work, "cast", f"{c}.png") for c in u.get("cast", []) if s["cast"][c].get("sheet", True)] + refs("style")
        jobs.append(f"- [ ] {rel(work, 'prompts', u['id'] + '_art.txt')} → {rel(work, 'art', u['id'] + '.png')}"
                    + (f"（添付: {', '.join(att)}）" if att else ""))
    jobs += ["", "## C. 写植（B の絵を添付して、吹き出しと文字を描き足す）"]
    for u in s["pages"]:
        if u["type"] != "panel":
            continue
        exp = [plain(t["text"]) for t in u.get("text", [])]
        open(os.path.join(work, "expected", f"{u['id']}.txt"), "w", encoding="utf-8").write("\n".join(exp) + "\n")
        if not u.get("text"):
            jobs.append(f"- [ ] {u['id']}: 文字なし（写植しない。art をそのまま使う）")
            continue
        open(os.path.join(pd, f"{u['id']}_letter.txt"), "w", encoding="utf-8").write(letter_prompt(s, u))
        att = [rel(work, "art", u["id"] + ".png")] + refs("lettering", 1)
        jobs.append(f"- [ ] {rel(work, 'prompts', u['id'] + '_letter.txt')} → {rel(work, 'letters', u['id'] + '.png')}"
                    f"（添付: {', '.join(att)}）")
    jobs += ["", "## D. 組み立て", f"- [ ] python3 tools/build.py assemble {rel(work)}"]
    open(os.path.join(work, "jobs.md"), "w", encoding="utf-8").write("\n".join(jobs) + "\n")
    print(f"prompts: {pd}")
    print(f"jobs:    {os.path.join(work, 'jobs.md')}")


def do_status(work):
    s = load(work)
    need = [os.path.join(work, "cast", f"{c}.png") for c, v in s["cast"].items() if v.get("sheet", True)]
    for u in s["pages"]:
        if u["type"] == "panel":
            need.append(os.path.join(work, "art", f"{u['id']}.png"))
            if u.get("text"):
                need.append(os.path.join(work, "letters", f"{u['id']}.png"))
    done = [p for p in need if os.path.exists(p)]
    print(f"できた {len(done)} / 要る {len(need)}")
    for p in need:
        if p not in done:
            print("  まだ:", os.path.relpath(p, KIT))
    return len(done) == len(need)


# ─────────────── 組み立て ───────────────
FONT_CANDIDATES = [
    "fonts/ShipporiAntiqueB1-Regular.ttf",
    "fonts/ZenAntique-Regular.ttf",
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "C:/Windows/Fonts/YuGothB.ttc",
    "C:/Windows/Fonts/meiryob.ttc",
    "C:/Windows/Fonts/msgothic.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
]


def jp_font(size):
    from PIL import ImageFont
    for f in FONT_CANDIDATES:
        p = f if os.path.isabs(f) else os.path.join(KIT, f)
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    print("注意: 日本語フォントが見つかりません。bash tools/get_fonts.sh を走らせてください（黒帯の文字が化けます）")
    return ImageFont.load_default()


def render_band(lines, width):
    """黒帯（場面転換）: 黒地に白文字の横組み。《》は赤"""
    from PIL import Image, ImageDraw
    fs = 52
    f = jp_font(fs)
    lh = int(fs * 1.6)
    h = lh * len(lines) + fs * 2
    im = Image.new("RGB", (width, h), (16, 16, 18))
    d = ImageDraw.Draw(im)
    y = fs + lh // 2
    for ln in lines:
        parts = re.split(r"(《.+?》)", ln)
        total = sum(d.textlength(re.sub(r"[《》]", "", p), font=f) for p in parts)
        x = (width - total) / 2
        for p in parts:
            red = p.startswith("《")
            t = re.sub(r"[《》]", "", p)
            d.text((x, y), t, font=f, fill=(230, 60, 60) if red else (255, 255, 255), anchor="lm")
            x += d.textlength(t, font=f)
        y += lh
    return im


def do_assemble(work):
    from PIL import Image
    s = load(work)
    W = int(s.get("width", 1080))
    margin, gutter = 40, 28
    cw = W - 2 * margin
    pieces = []
    for u in s["pages"]:
        if u["type"] == "panel":
            src = None
            for d in (("letters",) if u.get("text") else ()) + ("art",):
                p = os.path.join(work, d, f"{u['id']}.png")
                if os.path.exists(p):
                    src = p
                    break
            if not src:
                print("まだ無いので飛ばした:", u["id"])
                continue
            if u.get("text") and "letters" not in src:
                print("注意: 写植前の絵を使った:", u["id"])
            im = Image.open(src).convert("RGB")
            pw = int(cw * float(u.get("scale", 1.0)))
            pieces.append(("panel", im.resize((pw, int(im.height * pw / im.width)), Image.LANCZOS)))
        elif u["type"] == "band":
            pieces.append(("band", render_band(u["lines"], W)))
    if not pieces:
        sys.exit("並べる物がありません")
    H = margin * 2 + sum(im.height for _, im in pieces) + gutter * (len(pieces) - 1)
    canvas = Image.new("RGB", (W, H), (255, 255, 255))
    y = margin
    for kind, im in pieces:
        x = 0 if kind == "band" else (W - im.width) // 2
        canvas.paste(im, (x, y))
        y += im.height + gutter
    out = os.path.join(work, "final.png")
    canvas.save(out)
    canvas.save(out.replace(".png", ".jpg"), quality=88)
    print("saved:", out, canvas.size)


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("prompts", "status", "assemble"):
        sys.exit(__doc__)
    work = os.path.abspath(sys.argv[2])
    {"prompts": do_prompts, "status": do_status, "assemble": do_assemble}[sys.argv[1]](work)
