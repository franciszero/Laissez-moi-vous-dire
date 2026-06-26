import html
import json
import random
import re
import sqlite3
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import vocab as vocab_mod
import anki as anki_mod
import macdict as macdict_mod
import roundlogic
import matcher
import mastery as mastery_mod
import srs
import asr
import llm
import llm_lifecycle
import aigrade
import conjugate
from store import (
    import_vocab_into_db,
    get_ids_for_lemmas,
    save_round,
    load_round,
    get_attempts_for_words,
    save_setting,
    load_setting,
    ensure_checkpoint,
    update_checkpoint,
    get_checkpoint_state,
    get_due_checkpoints,
    save_checkpoint_attempt,
    get_checkpoint_attempts,
    save_ai_attempt,
    get_ai_attempts,
)

ZH_VOICE = "Tingting"  # macOS 中文嗓音（听/看中文模式用）
MODES = {
    "听法语 → 敲法语": ("fr_audio", ("fr",), "transcribe"),   # 听写：音→拼写
    "听法语 → 敲中文": ("fr_audio", ("zh",), "meaning"),       # 理解：法→意
    "听法语 → 敲法语+中文": ("fr_audio", ("fr", "zh"), "both"), # 听写+理解
    "听中文 → 敲法语": ("zh_audio", ("fr",), "produce"),       # 产出：意→拼写
    "看中文 → 敲法语": ("zh_text", ("fr",), "produce"),        # 产出：意→拼写
    "听中文 → 念法语": ("zh_audio", ("speak_fr",), "pron"),
    "看中文 → 念法语": ("zh_text", ("speak_fr",), "pron"),
    "看法语 → 念法语": ("fr_text", ("speak_fr",), "pron"),
    "看阳性 → 写阴性": ("fr_morph", ("fem",), "morph"),
}
# AI 精练「标准规范」：1-4（候选词/变位/句式/参考句）是出题时固化的人工标准，
# 运行时不让本地模型重新发明（见 HANDOFF §5）。status=draft 待人工核验后改 reviewed。
LLM_EXERCISES = [
    {
        "id": "L22:ai:sentence-core-after-work", "label": "造句流程 1/2 · 先写正确主干",
        "cue": "他们找到工作后，会在巴黎定居。",
        "instruction": "第一轮先降复杂度：只写“他们会在巴黎定居”这个最小正确主干。",
        "target": "他们会在巴黎定居。",
        "candidates": [
            {"zh": "他们", "fr": ["ils", "elles"]},
            {"zh": "定居", "fr": ["s'installer", "s'établir"]},
            {"zh": "在巴黎", "fr": ["à Paris"]},
        ],
        "conjugations": [{"verb": "s'installer", "form": "futur simple", "value": "ils s'installeront"}],
        "structures": ["S + s'installer + à + 城市"],
        "references": ["Ils s'installeront à Paris."],
        "required": ["futur simple", "城市名前用 à", "完整的主谓主干"],
        "ignore": "本轮不要求表达“找到工作后”",
        "status": "draft", "source": "L22", "author": "claude-opus-4-8",
    },
    {
        "id": "L22:ai:sentence-complex-after-work", "label": "造句流程 2/2 · 再升级完整句",
        "cue": "他们找到工作后，会在巴黎定居。",
        "instruction": "第二轮保留刚才的主干，再补“找到工作后”的先后关系。",
        "target": "他们找到工作后，会在巴黎定居。",
        "candidates": [
            {"zh": "找到", "fr": ["trouver"]},
            {"zh": "工作", "fr": ["un travail", "un emploi"]},
            {"zh": "定居", "fr": ["s'installer"]},
        ],
        "conjugations": [
            {"verb": "trouver", "form": "futur antérieur", "value": "ils auront trouvé"},
            {"verb": "s'installer", "form": "futur simple", "value": "ils s'installeront"},
        ],
        "structures": [
            "Quand + futur antérieur 从句, 主句 futur simple",
            "Après avoir + 过去分词, 主句 futur simple",
        ],
        "references": [
            "Quand ils auront trouvé un travail, ils s'installeront à Paris.",
            "Après avoir trouvé un travail, ils s'installeront à Paris.",
        ],
        "required": ["两个未来动作的先后", "先发生的用 futur antérieur 或 après avoir+过去分词", "后发生的用 futur simple"],
        "ignore": "",
        "status": "draft", "source": "L22", "author": "claude-opus-4-8",
    },
    {
        "id": "L22:ai:translate-opposer", "label": "长句整句翻译 1/3",
        "cue": "人们常常把外省生活和首都生活对立起来。",
        "instruction": "先找 on + opposer A à B，再处理副词和 celle 指代。",
        "target": "人们常常把外省生活和首都生活对立起来。",
        "candidates": [
            {"zh": "人们", "fr": ["on"]},
            {"zh": "对立/对比", "fr": ["opposer"]},
            {"zh": "外省", "fr": ["la province"]},
            {"zh": "首都", "fr": ["la capitale"]},
            {"zh": "乐于/常常", "fr": ["volontiers", "souvent"]},
        ],
        "conjugations": [{"verb": "opposer", "form": "imparfait", "value": "on opposait"}],
        "structures": ["On + opposer A à B（imparfait）", "celle 指代前面的 la vie"],
        "references": ["On opposait volontiers la vie de province à celle de la capitale."],
        "required": ["opposer A à B", "imparfait", "celle 指代 la vie"],
        "ignore": "",
        "status": "draft", "source": "L22", "author": "claude-opus-4-8",
    },
    {
        "id": "L22:ai:translate-media", "label": "长句整句翻译 2/3",
        "cue": "媒体的发展使外省摆脱了孤立。",
        "instruction": "先写主语中心，再用 tirer A de B 接骨架。",
        "target": "媒体的发展使外省摆脱了孤立。",
        "candidates": [
            {"zh": "媒体", "fr": ["les médias"]},
            {"zh": "发展", "fr": ["le développement"]},
            {"zh": "使…摆脱", "fr": ["tirer ... de", "sortir ... de"]},
            {"zh": "孤立", "fr": ["l'isolement"]},
        ],
        "conjugations": [{"verb": "tirer", "form": "passé composé", "value": "a tiré"}],
        "structures": ["主语（le développement des médias）+ tirer A de B（passé composé）"],
        "references": ["Le développement des médias a tiré la province de son isolement."],
        "required": ["主语 le développement des médias", "passé composé", "tirer A de B"],
        "ignore": "",
        "status": "draft", "source": "L22", "author": "claude-opus-4-8",
    },
    {
        "id": "L22:ai:translate-decentralisation", "label": "长句整句翻译 3/3",
        "cue": "地方分权被提上日程。",
        "instruction": "把“被提上日程”作为固定补语整体表达。",
        "target": "地方分权被提上日程。",
        "candidates": [
            {"zh": "地方分权", "fr": ["la décentralisation"]},
            {"zh": "被提上日程", "fr": ["être à l'ordre du jour"]},
        ],
        "conjugations": [{"verb": "être", "form": "présent", "value": "est"}],
        "structures": ["S + être à l'ordre du jour"],
        "references": ["La décentralisation est à l'ordre du jour."],
        "required": ["固定表达 être à l'ordre du jour"],
        "ignore": "",
        "status": "draft", "source": "L22", "author": "claude-opus-4-8",
    },
]


DB_PATH = "dictation.db"
WORDS_FILE = "words.txt"

BASE_DIR = Path(__file__).resolve().parent.parent  # 本地录屏课/


def _file_signature(pattern: str) -> tuple[tuple[str, int, int], ...]:
    """Return a cache key for lesson data files matched under BASE_DIR."""
    rows: list[tuple[str, int, int]] = []
    for path in sorted(BASE_DIR.glob(pattern)):
        try:
            stat = path.stat()
        except OSError:
            continue
        rows.append((str(path.relative_to(BASE_DIR)), stat.st_mtime_ns, stat.st_size))
    return tuple(rows)


@st.cache_data(show_spinner=False)
def load_vocab(_signature: tuple[tuple[str, int, int], ...]):
    return vocab_mod.load_all_vocab(BASE_DIR)


@st.cache_data(show_spinner=False)
def load_checkpoints(_signature: tuple[tuple[str, int, int], ...]):
    """扫 ../L*/manifest.json，取 bucket==checkpoint 的卡 → {lesson: [card,...]}。"""
    import manifest as mf
    out: dict = {}
    for vj in sorted(BASE_DIR.glob("L*/manifest.json")):
        try:
            d = mf.load(str(vj))
        except (OSError, ValueError):
            continue
        cards = mf.checkpoints(d)
        if cards:
            out[d.get("lesson", vj.parent.name)] = cards
    return out


@st.cache_data(show_spinner=False)
def load_conjugations(_signature: tuple[tuple[str, int, int], ...]):
    """扫 ../L*/conjugation.json → {lesson: [{verb,type,zh}, ...]}（只规则动词）。"""
    out: dict = {}
    for cj in sorted(BASE_DIR.glob("L*/conjugation.json")):
        try:
            d = json.loads(cj.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        verbs = d.get("verbs") or []
        if verbs:
            out[d.get("lesson", cj.parent.name)] = verbs
    return out


_CONJ_TENSE_ORDER = ["présent", "imparfait", "futur_proche", "futur_simple", "conditionnel", "participe_passé"]
# 展示 8 格（elle≈il、elles≈ils），映射到 6 个存储形 [je,tu,il,nous,vous,ils]
_CONJ_DISPLAY = [("je", 0), ("tu", 1), ("il", 2), ("elle", 2), ("nous", 3), ("vous", 4), ("ils", 5), ("elles", 5)]


def _conj_card(spec: dict, lesson: str) -> dict:
    """由 conjugate.py 确定性生成一张动词变位卡（规则动词）。"""
    c = conjugate.conjugate(spec["verb"], spec["type"])
    tenses = []
    for k in _CONJ_TENSE_ORDER:
        if k == "participe_passé":
            tenses.append({"key": k, "label": conjugate.TENSE_LABELS[k], "kind": "single", "answer": c[k]})
        else:
            tenses.append({"key": k, "label": conjugate.TENSE_LABELS[k], "kind": "six", "forms": list(c[k])})
    return {"id": f"{lesson}:conj:{spec['verb']}", "kind": "conj",
            "verb": spec["verb"], "zh": spec.get("zh", ""), "tenses": tenses}


def _lesson_cards(lesson: str) -> list[dict]:
    """一课的全部知识卡：checkpoint 卡 + 动词变位卡（卡即数据，统一一个 deck）。"""
    cards = list(load_checkpoints(_file_signature("L*/manifest.json")).get(lesson, []))
    for _s in load_conjugations(_file_signature("L*/conjugation.json")).get(lesson, []):
        try:
            cards.append(_conj_card(_s, lesson))
        except KeyError:
            pass
    for _ex in LLM_EXERCISES:                          # AI 产出题并入同一 deck（kind=production）
        if _ex["id"].startswith(lesson + ":"):
            cards.append({**_ex, "kind": "production"})
    return cards


def _start_cards(cards: list[dict], label: str, lesson: str) -> None:
    """进入「知识点」卡复习的统一入口（消除三处复制的 cp_* 开轮设置）。"""
    for _c in cards:
        ensure_checkpoint(_c["id"], lesson)
    st.session_state.cp_active = True
    st.session_state.cp_cards = cards
    st.session_state.cp_index = 0
    st.session_state.cp_show_back = False
    st.session_state.cp_label = label
    st.session_state.pop("cp_feedback", None)


@st.cache_data(show_spinner=False)
def card_state_cached(lemma: str):
    return anki_mod.card_state(lemma)


@st.cache_data(show_spinner=False)
def macdict_cached(lemma: str):
    return macdict_mod.define(lemma)


def word_zh(lemma: str) -> str:
    """词的中文释义：优先「当前练习这一课」的释义（同词跨课释义可能不同），否则用合并值。"""
    entry = VOCAB.get(lemma) or {}
    lesson = st.session_state.get("round_lesson")
    return (entry.get("zh_by_lesson") or {}).get(lesson) or entry.get("zh", "")


def render_learn_panel(lemma: str) -> None:
    """答完/显示答案后，展示中文词义 + 可选的 Anki 富内容。"""
    zh = word_zh(lemma)
    if zh:
        st.markdown(f"**释义**：{zh}")
    state = card_state_cached(lemma)
    if state["status"] == "ok":
        with st.expander("📇 完整 Anki 卡片", expanded=True):
            components.html(
                state["html"] + "<style>.qa-summary{display:none !important}</style>",
                height=820,
                scrolling=True,
            )
        return
    # 残卡（生成失败/字段全 N/A）：别显示空卡，但留个提示让我知道这词要重新生成
    if state["status"] == "stub":
        st.caption(f"⚠️ Anki 卡{state['reason']}，待重新生成（{lemma}）")
    definition = macdict_cached(lemma)
    if definition:
        st.markdown(f"**词典（macOS）**：{definition}")


# =========================
# 基础工具
# =========================

def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def parse_time(value: str | None) -> datetime:
    if not value:
        return datetime.min
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.min


def _due_checkpoint_cards(cards: list[dict]) -> list[dict]:
    """到期该复习的知识点卡（遗忘曲线驱动，最早到期优先）。"""
    by_id = {c["id"]: c for c in cards}
    return [by_id[i] for i in get_due_checkpoints(list(by_id)) if i in by_id]


def normalize(text: str) -> str:
    """
    答案比较（重音敏感——法语听写重音算数）：
    - 忽略大小写
    - 忽略前后空格、合并多个空格
    - 保留重音：épicier ≠ epicier
    """
    return " ".join(text.strip().lower().split())


def speak(text: str, voice: str, rate: int) -> None:
    """
    调用 macOS 自带 say 命令播放。
    用 Popen 异步播放，避免朗读时整页渲染被阻塞。
    """
    subprocess.Popen(["say", "-v", voice, "-r", str(rate), text])


@st.cache_data(show_spinner=False)
def list_fr_voices() -> list[str]:
    """
    列出系统里所有法语 say 语音（fr_FR 在前，fr_CA 在后）。
    用于下拉选择，避免手输错名字时 say 静默回退到英文默认嗓音。
    """
    try:
        out = subprocess.run(
            ["say", "-v", "?"], capture_output=True, text=True, check=False
        ).stdout
    except OSError:
        return []

    fr_fr: list[str] = []
    fr_ca: list[str] = []
    for line in out.splitlines():
        m = re.match(r"^(.*?)\s+(fr_(?:FR|CA))\b", line)
        if not m:
            continue
        if m.group(2) == "fr_FR":
            fr_fr.append(m.group(1).strip())
        else:
            fr_ca.append(m.group(1).strip())

    return fr_fr + fr_ca


def focus_answer_input() -> None:
    """切题后把焦点放到答案输入框（Streamlit 无原生 focus API）。"""
    components.html(
        """
        <script>
        (function () {
          const doc = window.parent.document;
          function focusInput() {
            const inputs = doc.querySelectorAll(
              '[data-testid="stTextInput"] input[type="text"]'
            );
            const input = inputs[inputs.length - 1];
            if (input) {
              input.focus();
              input.select();
            }
          }
          focusInput();
          setTimeout(focusInput, 50);
          setTimeout(focusInput, 150);
        })();
        </script>
        """,
        height=0,
        width=0,
    )


def wire_form_enter_submit() -> None:
    """答案框按 Enter：不是最后一个框就跳到下一个框（法语→中文），是最后一个才提交。"""
    components.html(
        """
        <script>
        (function () {
          const doc = window.parent.document;
          if (doc.__dictationEnterBound) return;
          doc.__dictationEnterBound = true;
          doc.addEventListener(
            "keydown",
            function (e) {
              if (
                e.key !== "Enter" ||
                e.shiftKey ||
                e.ctrlKey ||
                e.metaKey ||
                e.altKey ||
                e.isComposing
              ) {
                return;
              }
              const el = doc.activeElement;
              if (!el || el.tagName !== "INPUT" || el.type !== "text") return;
              const form = el.closest("form");
              if (!form) return;
              const inputs = Array.from(
                form.querySelectorAll('input[type="text"]')
              );
              const idx = inputs.indexOf(el);
              if (idx !== -1 && idx < inputs.length - 1) {
                // 不是最后一个框 → 跳到下一个（如 法语→中文），不提交
                e.preventDefault();
                const nxt = inputs[idx + 1];
                nxt.focus();
                nxt.select();
                return;
              }
              const submit = form.querySelector(
                '[data-testid="stFormSubmitButton"] button, [data-testid="stFormSubmitButton"]'
              );
              if (!submit) return;
              e.preventDefault();
              submit.click();
            },
            true
          );
        })();
        </script>
        """,
        height=0,
        width=0,
    )


def mark_word_navigation() -> None:
    st.session_state.play_on_load = True
    st.session_state.focus_input = True


# =========================
# 数据库
# =========================

def get_conn():
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS words (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT NOT NULL UNIQUE,
        wrong_count INTEGER NOT NULL DEFAULT 0,
        correct_streak INTEGER NOT NULL DEFAULT 0,
        interval_days INTEGER NOT NULL DEFAULT 0,
        due_at TEXT,
        last_seen_at TEXT,
        created_at TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        word_id INTEGER NOT NULL,
        answer TEXT NOT NULL,
        is_correct INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(word_id) REFERENCES words(id)
    )
    """)

    # 迁移：给 attempts 加 skill 列
    try:
        cur.execute("ALTER TABLE attempts ADD COLUMN skill TEXT")
    except sqlite3.OperationalError:
        pass

    # 迁移：旧的 "form" 与 NULL（当年听写/产出混记，且默认模式是 听法语→敲法语）→ 归为「听写」transcribe
    cur.execute("UPDATE attempts SET skill = 'transcribe' WHERE skill = 'form' OR skill IS NULL")

    # 迁移：给 words 加 hidden 列（软删除：不用背的词隐藏出流程，数据保留）
    try:
        cur.execute("ALTER TABLE words ADD COLUMN hidden INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    # 知识点 checkpoint 卡的 SRS 状态（内容在 manifest，状态按 card_id 存这）
    cur.execute("""
    CREATE TABLE IF NOT EXISTS checkpoints (
        card_id TEXT PRIMARY KEY,
        lesson TEXT NOT NULL,
        correct_streak INTEGER NOT NULL DEFAULT 0,
        interval_days INTEGER NOT NULL DEFAULT 0,
        due_at TEXT,
        last_seen_at TEXT,
        created_at TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()


def import_words_from_txt(file_path: str = WORDS_FILE) -> int:
    path = Path(file_path)
    if not path.exists():
        return 0

    lines = path.read_text(encoding="utf-8").splitlines()
    words = []

    for line in lines:
        word = line.strip()
        if not word:
            continue
        if word.startswith("#"):
            continue
        words.append(word)

    conn = get_conn()
    cur = conn.cursor()

    inserted = 0
    for word in words:
        try:
            cur.execute(
                """
                INSERT INTO words (text, created_at)
                VALUES (?, ?)
                """,
                (word, now_iso()),
            )
            inserted += 1
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    conn.close()

    return inserted


def get_all_words() -> list[dict]:
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
    SELECT *
    FROM words
    WHERE hidden = 0
    ORDER BY text
    """)

    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def set_word_hidden(word_id: int, hidden: bool) -> None:
    """软删除/恢复一个词：hidden=1 不再进任何练习流程，数据保留。"""
    conn = get_conn()
    conn.execute("UPDATE words SET hidden = ? WHERE id = ?", (1 if hidden else 0, word_id))
    conn.commit()
    conn.close()


def _hidden_id_set() -> set:
    conn = get_conn()
    s = {r[0] for r in conn.execute("SELECT id FROM words WHERE hidden = 1")}
    conn.close()
    return s


def get_hidden_words() -> list[dict]:
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT * FROM words WHERE hidden = 1 ORDER BY text")]
    conn.close()
    return rows


def get_words_by_ids(ids: list[int]) -> list[dict]:
    if not ids:
        return []

    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    placeholders = ",".join(["?"] * len(ids))
    cur.execute(
        f"""
        SELECT *
        FROM words
        WHERE id IN ({placeholders})
        """,
        ids,
    )

    rows = [dict(row) for row in cur.fetchall()]
    conn.close()

    by_id = {row["id"]: row for row in rows}
    return [by_id[word_id] for word_id in ids if word_id in by_id]


def get_due_wrong_words(due_only: bool = False, only_ids=None) -> list[dict]:
    """
    错题复习排序：
    1. 到期的排前面
    2. 错得多的排前面
    3. 连续答对少的排前面
    4. 最久没见的排前面

    due_only=True 时只返回已到期（due_at <= 现在）的词，更贴近间隔复习本意。
    """
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
    SELECT *
    FROM words
    WHERE wrong_count > 0 AND hidden = 0
    """)

    rows = [dict(row) for row in cur.fetchall()]
    conn.close()

    if only_ids is not None:          # 限定在某一课的词内
        keep = set(only_ids)
        rows = [row for row in rows if row["id"] in keep]

    current = datetime.now()

    if due_only:
        rows = [row for row in rows if parse_time(row["due_at"]) <= current]

    def priority(row: dict):
        due = parse_time(row["due_at"])
        last_seen = parse_time(row["last_seen_at"])

        is_due = 0 if due <= current else 1

        return (
            is_due,
            due,
            -row["wrong_count"],
            row["correct_streak"],
            last_seen,
        )

    rows.sort(key=priority)
    return rows


def record_attempt(word_id: int, answer: str, is_correct: bool, skill: str = "form") -> None:
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO attempts (word_id, answer, is_correct, created_at, skill)
        VALUES (?, ?, ?, ?, ?)
        """,
        (word_id, answer, 1 if is_correct else 0, now_iso(), skill),
    )

    cur.execute(
        """
        SELECT wrong_count, correct_streak
        FROM words
        WHERE id = ?
        """,
        (word_id,),
    )

    row = cur.fetchone()
    if not row:
        conn.close()
        return

    wrong_count, correct_streak = row

    if is_correct:
        correct_streak += 1

        intervals = [1, 2, 4, 7, 15, 30]
        interval_days = intervals[min(correct_streak - 1, len(intervals) - 1)]
        due_at = datetime.now() + timedelta(days=interval_days)

        cur.execute(
            """
            UPDATE words
            SET correct_streak = ?,
                interval_days = ?,
                due_at = ?,
                last_seen_at = ?
            WHERE id = ?
            """,
            (
                correct_streak,
                interval_days,
                due_at.isoformat(timespec="seconds"),
                now_iso(),
                word_id,
            ),
        )

    else:
        wrong_count += 1

        cur.execute(
            """
            UPDATE words
            SET wrong_count = ?,
                correct_streak = 0,
                interval_days = 0,
                due_at = ?,
                last_seen_at = ?
            WHERE id = ?
            """,
            (
                wrong_count,
                now_iso(),
                now_iso(),
                word_id,
            ),
        )

    conn.commit()
    conn.close()


def get_last_wrong_answer(word_id: int) -> str | None:
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT answer
        FROM attempts
        WHERE word_id = ?
          AND is_correct = 0
        ORDER BY id DESC
        LIMIT 1
        """,
        (word_id,),
    )

    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    return row[0]


def get_attempt_history(word_id: int, limit: int = 10) -> list[dict]:
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute(
        """
        SELECT answer, is_correct, created_at
        FROM attempts
        WHERE word_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (word_id, limit),
    )

    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def get_stats() -> dict:
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM words WHERE hidden = 0")
    total = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM words WHERE wrong_count > 0 AND hidden = 0")
    wrong_words = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM attempts")
    attempts = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM attempts WHERE is_correct = 1")
    correct_attempts = cur.fetchone()[0]

    conn.close()

    accuracy = 0
    if attempts:
        accuracy = correct_attempts / attempts * 100

    return {
        "total": total,
        "wrong_words": wrong_words,
        "attempts": attempts,
        "accuracy": accuracy,
    }


# =========================
# Streamlit 状态
# =========================

def goto(pos: int) -> None:
    """跳到整轮里第 pos 个词（1-based），并朗读+聚焦。"""
    pool = st.session_state.pool
    if not pool:
        return
    pos = max(1, min(pos, len(pool)))
    st.session_state.index = pos
    st.session_state.current_word = get_words_by_ids([pool[pos - 1]])[0]
    st.session_state.feedback = None
    st.session_state.show_answer = False
    st.session_state.at_rest = False
    st.session_state.pending = None
    st.session_state.speak = {"state": "idle"}
    st.session_state.graded = False
    mark_word_navigation()


def reset_round(word_ids: list[int], batch_size: int) -> None:
    """开始一整轮：整批词作为一个池子，每 batch_size 个弹一次休息。"""
    st.session_state.pool = list(word_ids)
    st.session_state.round_total = len(word_ids)
    st.session_state.batch_size_round = max(1, batch_size)
    st.session_state.index = 0
    st.session_state.current_word = None
    st.session_state.feedback = None
    st.session_state.show_answer = False
    st.session_state.round_results = {}
    st.session_state.at_rest = False
    if word_ids:
        goto(1)


_ROUND_KEYS = ("pool", "index", "round_total", "round_label", "round_lesson", "batch_size_round", "at_rest")


def persist_round() -> None:
    """把当前一轮存到 DB。"""
    data = {k: st.session_state.get(k) for k in _ROUND_KEYS}
    data["round_results"] = {
        str(k): v for k, v in st.session_state.get("round_results", {}).items()
    }
    save_round(data)


def restore_round(data: dict) -> None:
    """从 DB 恢复一轮（刷新后续上）。"""
    for k in _ROUND_KEYS:
        if data.get(k) is not None:
            st.session_state[k] = data[k]
    st.session_state.round_results = {
        int(k): v for k, v in data.get("round_results", {}).items()
    }
    pool = st.session_state.pool
    idx = st.session_state.index
    st.session_state.current_word = (
        get_words_by_ids([pool[idx - 1]])[0] if pool and 1 <= idx <= len(pool) else None
    )


def prev_word() -> bool:
    if st.session_state.index <= 1:
        return False
    goto(st.session_state.index - 1)
    return True


def next_word() -> None:
    action, pos = roundlogic.next_action(
        st.session_state.index,
        len(st.session_state.pool),
        st.session_state.get("batch_size_round", 10),
    )
    if action == "done":
        st.session_state.current_word = None   # 整轮做完
        st.session_state.at_rest = False
    elif action == "rest":
        st.session_state.at_rest = True         # 到休息点，先停一下
    else:
        goto(pos)


def _lesson_ids(lesson: str, lessons_map: dict) -> list[int]:
    """某一课（或「全部」）的词 id 列表，已排除隐藏（不用背）的词。"""
    if lesson == "全部":
        return [row["id"] for row in get_all_words()]   # get_all_words 已过滤 hidden
    ids = get_ids_for_lemmas(lessons_map.get(lesson, []))
    hidden = _hidden_id_set()
    return [i for i in ids if i not in hidden]


def _fem_ids(lesson: str, lessons_map: dict) -> list[int]:
    """某一课里「有阴性形式」的词 id（变形练习的词池）。"""
    rows = get_words_by_ids(_lesson_ids(lesson, lessons_map))
    return [r["id"] for r in rows if VOCAB.get(r["text"], {}).get("fem")]


def start_full_round(batch_size: int) -> int:
    """完整词库随机不放回，分批进行；返回总词数。"""
    ids = [row["id"] for row in get_all_words()]
    random.shuffle(ids)
    reset_round(ids, batch_size)
    st.session_state.round_lesson = "全部"
    st.session_state.round_label = "全部词库"
    return len(ids)


def start_lesson_round(lesson: str, lessons_map: dict, batch_size: int) -> int:
    """学习模式：练某一课（或「全部」）。返回总词数。"""
    ids = _lesson_ids(lesson, lessons_map)
    random.shuffle(ids)
    reset_round(ids, batch_size)
    st.session_state.round_lesson = lesson
    st.session_state.round_label = "全部词库" if lesson == "全部" else f"学习 · {lesson}"
    return len(ids)


def start_lesson_review(lesson: str, lessons_map: dict, due_only: bool, batch_size: int) -> int:
    """复习某一课的错词（按遗忘曲线优先级；due_only 只练到期）。返回总词数。"""
    scope = None if lesson == "全部" else _lesson_ids(lesson, lessons_map)
    ids = [row["id"] for row in get_due_wrong_words(due_only=due_only, only_ids=scope)]
    reset_round(ids, batch_size)
    st.session_state.round_lesson = lesson
    kind = "到期复习" if due_only else "错词复习"
    where = "全部" if lesson == "全部" else lesson
    st.session_state.round_label = f"{kind} · {where}"
    return len(ids)


def start_lesson_morph(lesson: str, lessons_map: dict, batch_size: int) -> int:
    """变形练习：只练这一课里有阴性的词，并自动切到「看阳性→写阴性」模式。"""
    ids = _fem_ids(lesson, lessons_map)
    reset_round(ids, batch_size)
    st.session_state.round_lesson = lesson
    st.session_state.round_label = "变形 · 全部" if lesson == "全部" else f"变形 · {lesson}"
    st.session_state["pending_mode"] = "看阳性 → 写阴性"   # 下次渲染在 selectbox 实例化前应用
    return len(ids)


def start_review_round(due_only: bool, batch_size: int) -> int:
    """全部课程的到期/错词复习（顶部「今天到期」提醒用）。返回总词数。"""
    ids = [row["id"] for row in get_due_wrong_words(due_only=due_only)]
    reset_round(ids, batch_size)
    st.session_state.round_lesson = "全部"
    st.session_state.round_label = "到期复习 · 全部" if due_only else "错词复习 · 全部"
    return len(ids)


# =========================
# 页面
# =========================

st.set_page_config(
    page_title="法语听写复习器",
    layout="centered",
)


init_db()

VOCAB_SIGNATURE = _file_signature("*/vocab.json")
VOCAB, LESSONS = load_vocab(VOCAB_SIGNATURE)
if st.session_state.get("vocab_import_signature") != VOCAB_SIGNATURE:
    import_vocab_into_db(VOCAB)
    st.session_state.vocab_import_signature = VOCAB_SIGNATURE

if "pool" not in st.session_state:
    st.session_state.pool = []

if "index" not in st.session_state:
    st.session_state.index = 0

if "current_word" not in st.session_state:
    st.session_state.current_word = None

if "feedback" not in st.session_state:
    st.session_state.feedback = None

if "show_answer" not in st.session_state:
    st.session_state.show_answer = False

if "play_on_load" not in st.session_state:
    st.session_state.play_on_load = False

if "focus_input" not in st.session_state:
    st.session_state.focus_input = False

if "round_results" not in st.session_state:
    st.session_state.round_results = {}   # {word_id: 首次是否答对}

if "at_rest" not in st.session_state:
    st.session_state.at_rest = False

if "batch_size_round" not in st.session_state:
    st.session_state.batch_size_round = 10

if "round_total" not in st.session_state:
    st.session_state.round_total = 0

if "round_label" not in st.session_state:
    st.session_state.round_label = ""

if "round_lesson" not in st.session_state:
    st.session_state.round_lesson = "全部"   # 当前这一轮属于哪一课（复习/重开按它分组）

if "cp_active" not in st.session_state:   # 「📝 知识点」是独立流程，绝不碰 pool/current_word
    st.session_state.cp_active = False
    st.session_state.cp_cards = []
    st.session_state.cp_index = 0
    st.session_state.cp_show_back = False

if "llm_loaded" not in st.session_state:  # 本地模型生命周期（AI 产出卡按需加载、闲置卸载）
    st.session_state.llm_loaded = False
    st.session_state.llm_last_active = 0.0

if "pending" not in st.session_state:
    st.session_state.pending = None   # 中文拿不准时的人工自判暂存

if "speak" not in st.session_state:
    st.session_state.speak = {"state": "idle"}   # 念法语模式的状态机

if "graded" not in st.session_state:
    st.session_state.graded = False   # 当前这道题是否已评过分（防刷分）

# 刷新/重开后续上上次那一轮（每个会话只恢复一次；忽略旧版批次存档）
if not st.session_state.get("restored"):
    st.session_state.restored = True
    if not st.session_state.pool:
        _saved = load_round()
        if _saved and "queue" not in _saved:   # 旧版（队列）存档不兼容，跳过
            restore_round(_saved)


def _leave_overlays() -> None:
    """离开所有覆盖式复习视图（AI 精练 / 知识点 / 动词变位），回到词练习。"""
    if st.session_state.get("llm_loaded"):
        llm.unload()
    st.session_state.llm_loaded = False
    st.session_state.pop("llm_error", None)
    st.session_state.cp_active = False


st.title("法语听写复习器")

stats = get_stats()

col1, col2, col3, col4 = st.columns(4)
col1.metric("词库", stats["total"], help="所有课去重后的总词数（不是当前这一课）")
col2.metric("错词", stats["wrong_words"])
col3.metric("提交次数", stats["attempts"])
col4.metric("正确率", f"{stats['accuracy']:.1f}%")


with st.sidebar:
    st.header("设置")

    fr_voices = list_fr_voices()
    if fr_voices:
        default_index = fr_voices.index("Thomas") if "Thomas" in fr_voices else 0
        voice = st.selectbox("语音", fr_voices, index=default_index)
    else:
        voice = st.text_input("语音", value="Thomas")

    rate = st.slider("语速", min_value=80, max_value=220, value=135, step=5)

    auto_next = st.checkbox("答对后自动下一题", value=False)
    if "pending_mode" in st.session_state:   # 「变形」入口要求切到的模式（widget 实例化前才能设）
        st.session_state["mode"] = st.session_state.pop("pending_mode")
    mode_name = st.selectbox("模式", list(MODES), key="mode")
    PROMPT_TYPE, ANSWER_FIELDS, SKILL = MODES[mode_name]

    st.divider()

    batch_size = st.number_input(
        "每批词数（做完一批会停下来喘口气）",
        min_value=1,
        max_value=100,
        value=10,
        step=1,
    )

    st.subheader("学习")
    lesson_options = ["全部"] + sorted(LESSONS)
    if "sel_lesson" not in st.session_state:   # 刷新/重开默认停在上次那一课
        _last = load_setting("last_lesson", "全部")
        st.session_state.sel_lesson = _last if _last in lesson_options else "全部"
    chosen_lesson = st.selectbox("选课", lesson_options, key="sel_lesson")

    _scope = None if chosen_lesson == "全部" else _lesson_ids(chosen_lesson, LESSONS)
    _n_all = len(get_all_words()) if chosen_lesson == "全部" else len(_scope)
    _n_wrong = len(get_due_wrong_words(only_ids=_scope))

    if st.button(f"开始这一课（{_n_all} 词）", type="primary"):
        _leave_overlays()
        save_setting("last_lesson", chosen_lesson)
        if start_lesson_round(chosen_lesson, LESSONS, batch_size):
            st.rerun()
        else:
            st.warning("这一课还没有词。")

    if st.button(f"错词（{_n_wrong}）", disabled=_n_wrong == 0):   # 到期复习改由顶部 banner 统一入口
        _leave_overlays()
        save_setting("last_lesson", chosen_lesson)
        start_lesson_review(chosen_lesson, LESSONS, False, batch_size)
        st.rerun()

    _n_fem = len(_fem_ids(chosen_lesson, LESSONS))
    if st.button(f"变形（{_n_fem}）", disabled=_n_fem == 0):
        _leave_overlays()
        save_setting("last_lesson", chosen_lesson)
        start_lesson_morph(chosen_lesson, LESSONS, batch_size)
        st.rerun()

    _cards = _lesson_cards(chosen_lesson)            # checkpoint 卡 + 动词变位卡，统一一个 deck
    if st.button(f"📝 知识点（{len(_cards)}）", disabled=not _cards):
        _leave_overlays()
        save_setting("last_lesson", chosen_lesson)
        _start_cards(_cards, f"知识点 · {chosen_lesson}", chosen_lesson)
        st.rerun()
    st.caption("错词=做错过的；到期=顶部按遗忘曲线提醒；变形=有阴阳性的词；知识点=老师讲的非单词要点（含动词变位 + AI 造句批改；AI 卡提交时才加载本地模型）。")

    if st.button("🔄 重新扫描词表（加了课/改了文件后点）"):
        load_vocab.clear()
        load_checkpoints.clear()
        load_conjugations.clear()
        st.rerun()

    hidden_rows = get_hidden_words()
    with st.expander(f"🙈 已隐藏的词（{len(hidden_rows)}）"):
        if not hidden_rows:
            st.caption("背到不用背的词（地名等），点「🙈 这个词不用背」即可隐藏；数据保留，可在此恢复。")
        for r in hidden_rows:
            hc1, hc2 = st.columns([3, 1])
            hc1.write(f"{r['text']} — {VOCAB.get(r['text'], {}).get('zh', '')}")
            if hc2.button("恢复", key=f"unhide_{r['id']}"):
                set_word_hidden(r["id"], False)
                st.rerun()

    st.divider()
    with st.expander("➕ 添加 / 自定义词表"):
        st.caption("每行：法语<Tab>中文　或　类别<Tab>法语<Tab>中文；Tab/逗号/Markdown 表格都认，表头自动跳过")
        up = st.file_uploader("上传词表文件", type=["tsv", "csv", "txt"])
        new_name = st.text_input("课程名（会建 ../<名>/vocab.json，如 L19）")
        if st.button("导入这个词表"):
            name = new_name.strip()
            if not up or not name:
                st.warning("请同时选择文件并填课程名。")
            else:
                out = BASE_DIR / name / "vocab.json"
                if out.exists():
                    st.error(f"已有同名课程「{name}」，换个名字（或先删掉 {out.parent}）。")
                else:
                    text = up.getvalue().decode("utf-8", errors="replace")
                    entries, skipped = vocab_mod.parse_uploaded(text, lesson=name)
                    if not entries:
                        st.error("没解析出有效词条，请检查格式。")
                    else:
                        out.parent.mkdir(parents=True, exist_ok=True)
                        out.write_text(json.dumps(entries, ensure_ascii=False, indent=2), "utf-8")
                        import_vocab_into_db({e["lemma"]: e for e in entries})
                        load_vocab.clear()
                        st.success(f"已导入 {len(entries)} 词到「{name}」（跳过 {skipped} 行）。已出现在选课里。")
                        st.rerun()


def speak_prompt(word) -> None:
    """播放提示：听/看法语 → 念法语；听/看中文 → 念中文。"""
    if PROMPT_TYPE in ("fr_audio", "fr_text"):
        speak(word["text"], voice=voice, rate=rate)
    else:
        speak(word_zh(word["text"]), voice=ZH_VOICE, rate=rate)


def _finalize_speak(word, heard, ok) -> None:
    zh = word_zh(word["text"])
    record_attempt(word["id"], heard or "（口述）", ok, "pron")
    st.session_state.round_results[word["id"]] = ok
    st.session_state.graded = True
    speak("对" if ok else "错", voice=ZH_VOICE, rate=rate)
    st.session_state.feedback = {
        "type": "success" if ok else "error",
        "message": (
            f"✅ 对：{word['text']} — {zh}"
            if ok
            else f"❌ 听到「{heard}」，答案：{word['text']} — {zh}"
        ),
    }
    st.session_state.speak = {"state": "done"}


@st.fragment(run_every=0.6)
def _speak_autopoll() -> None:
    """自动模式：每 0.6s 轮询后台转写；收到一句就自动判，整页重跑。"""
    if not st.session_state.get("speak_auto"):
        return
    sp = st.session_state.speak
    if sp.get("state") != "armed":
        return
    d = asr.read_latest()
    if d and d.get("final") and d.get("ts", 0) > sp.get("armed_at", 0):
        word = st.session_state.current_word
        heard = d.get("text", "")
        if matcher.check_speech(heard, word["text"]) is True:
            _finalize_speak(word, heard, True)
        else:
            st.session_state.speak = {"state": "judge", "heard": heard}
        st.rerun(scope="app")
    else:
        st.caption("🎙 自动听写中…（说完稍等）")


def render_speak(word) -> None:
    """念法语：备妥变绿 → 念 → 读后台转写 → 比对 → 报对错。支持自动模式（轮询+倒计时）。"""
    target = word["text"]
    zh = word_zh(target)

    c1, c2, c3 = st.columns(3)
    if c1.button("上一题", disabled=st.session_state.index <= 1):
        if prev_word():
            st.rerun()
    if c2.button("播放 / 重听"):
        speak_prompt(word)
    if c3.button("下一题"):
        next_word()
        st.rerun()

    auto = st.checkbox("🔁 自动模式（说完自动判 + 倒计时下一题，适合快速过词）", key="speak_auto")

    sp = st.session_state.speak
    state = sp.get("state", "idle")

    # 自动模式：新词直接备妥（不用手点开始）
    if state == "idle" and auto:
        asr.clear()
        st.session_state.speak = {"state": "armed", "armed_at": time.time()}
        sp = st.session_state.speak
        state = "armed"

    if state == "idle":
        st.markdown("🟡 **未就绪** —— 点下面变绿再念")
        if st.button("🎤 开始作答", type="primary"):
            asr.clear()
            st.session_state.speak = {"state": "armed", "armed_at": time.time()}
            st.rerun()
    elif state == "armed":
        st.markdown("🟢 **请念出来…**")
        if auto:
            _speak_autopoll()
        a, b = st.columns(2)
        if a.button("🛑 念完了"):
            d = asr.read_latest()
            heard = d.get("text", "") if (d and d.get("ts", 0) > sp.get("armed_at", 0)) else ""
            if matcher.check_speech(heard, target) is True:
                _finalize_speak(word, heard, True)
            else:
                st.session_state.speak = {"state": "judge", "heard": heard}
            st.rerun()
        if b.button("✋ 取消"):
            st.session_state.speak = {"state": "idle"}
            st.rerun()
        st.caption(f"后台转写写到 {asr.ASR_FILE}（没接 worker 时用 scripts/asr_stub.py 写）")
    elif state == "judge":
        heard = sp.get("heard", "")
        if heard:
            st.markdown(f"🎧 听到：**{heard}**")
            st.warning(f"拿不准，你判一下 —— 标准：{target} — {zh}")
        else:
            st.warning(
                "🎧 没收到转写 —— 后台转写 worker 没在跑。念法语要先启动 "
                "`scripts/asr_worker.py`；不想用麦克风先测就跑 "
                f"`python3 scripts/asr_stub.py \"{target}\"`。现在只能手动自判 —— 标准：{target} — {zh}"
            )
        a, b = st.columns(2)
        if a.button("✅ 算我对"):
            _finalize_speak(word, heard, True)
            st.rerun()
        if b.button("❌ 算我错"):
            _finalize_speak(word, heard, False)
            st.rerun()
    else:  # done
        fb = st.session_state.feedback
        if fb:
            (st.success if fb["type"] == "success" else st.error)(fb["message"])
        render_learn_panel(target)
        if auto and fb and fb["type"] == "success":
            st.caption("✅ 自动下一题…")
            time.sleep(1.3)
            next_word()
            st.rerun()
        elif st.button("下一题 ▶", type="primary"):
            next_word()
            st.rerun()


def _finalize(word, fr_ans, zh_ans, fr_ok, zh_ok) -> None:
    """落定一次作答（按模式合并字段），写反馈与本轮对错。"""
    zh_gloss = word_zh(word["text"])
    parts, oks = [], []
    if "fr" in ANSWER_FIELDS:
        parts.append((fr_ans or "").strip() or "（空）")
        oks.append(bool(fr_ok))
    if "zh" in ANSWER_FIELDS:
        parts.append((zh_ans or "").strip() or "（空）")
        oks.append(bool(zh_ok))
    combined = " / ".join(parts)
    correct = bool(oks) and all(oks)
    if SKILL == "both":
        record_attempt(word["id"], (fr_ans or "").strip() or "（空）", bool(fr_ok), "transcribe")
        record_attempt(word["id"], (zh_ans or "").strip() or "（空）", bool(zh_ok), "meaning")
    else:
        record_attempt(word["id"], combined, correct, SKILL)
    st.session_state.round_results[word["id"]] = correct
    st.session_state.pending = None
    st.session_state.graded = True
    answer_text = f"{word['text']} — {zh_gloss}"
    rows = []
    if "fr" in ANSWER_FIELDS:
        rows.append(("法语", (fr_ans or "").strip() or "（空）", word["text"], bool(fr_ok)))
    if "zh" in ANSWER_FIELDS:
        rows.append(("中文", (zh_ans or "").strip() or "（空）", zh_gloss, bool(zh_ok)))
    st.session_state.feedback = {
        "type": "success" if correct else "error",
        "message": f"✅ 对：{answer_text}" if correct else f"❌ 你写：{combined}；答案：{answer_text}",
        "rows": rows,
    }


def _finalize_morph(word, fem_ans) -> None:
    """变形模式落定：对照 VOCAB[词].fem，记 skill=morph。"""
    fem = VOCAB.get(word["text"], {}).get("fem")
    ok = bool(fem) and bool(matcher.check_fr(fem_ans, fem))
    record_attempt(word["id"], (fem_ans or "").strip() or "（空）", ok, "morph")
    st.session_state.round_results[word["id"]] = ok
    st.session_state.graded = True
    st.session_state.feedback = {
        "type": "success" if ok else "error",
        "message": "✅ 对" if ok else "❌ 有错",
        "rows": [("阴性", (fem_ans or "").strip() or "（空）", fem or "（无阴性）", ok)],
    }


def render_answer_table(rows) -> None:
    """2×2 无边框对照表：行=法语/中文，列=你敲的/标准答案。ok ∈ {True, False, None}。"""
    mark = {True: "✅", False: "❌", None: "❔"}
    color = {True: "#1a7f37", False: "#c0362c", None: "#8a6d00"}
    head = (
        "<tr><td></td>"
        "<td style='padding:2px 28px 2px 0;color:#999;font-size:.82em'>你敲的</td>"
        "<td style='padding:2px 0;color:#999;font-size:.82em'>标准答案</td></tr>"
    )
    body = ""
    for label, typed, correct, ok in rows:
        body += (
            "<tr>"
            f"<td style='padding:3px 14px 3px 0;color:#666'>{mark[ok]} {label}</td>"
            f"<td style='padding:3px 28px 3px 0;color:{color[ok]}'>{html.escape(typed)}</td>"
            f"<td style='padding:3px 0;color:#1a1a1a'>{html.escape(correct)}</td>"
            "</tr>"
        )
    st.markdown(
        f"<table style='border-collapse:collapse;margin:2px 0 6px'>{head}{body}</table>",
        unsafe_allow_html=True,
    )


def render_practice() -> None:
    current_word = st.session_state.current_word

    if st.session_state.at_rest:
        done = st.session_state.index
        total = st.session_state.round_total
        res = st.session_state.round_results
        bs = st.session_state.batch_size_round
        st.success("✅ 歇一下～")
        st.write(
            f"{st.session_state.round_label} · 已做 {done}/{total} 词 · "
            f"对 {sum(1 for v in res.values() if v)} / 错 {sum(1 for v in res.values() if not v)}"
        )
        rc1, rc2 = st.columns(2)
        if rc1.button("继续 ▶", type="primary"):
            goto(st.session_state.index + 1)
            st.rerun()
        if rc2.button(f"↩︎ 回听刚才这 {min(bs, done)} 题"):
            goto(max(1, done - bs + 1))   # 跳回这一批开头，重新过一遍
            st.rerun()
    elif current_word is None:
        if st.session_state.pool:
            total = st.session_state.round_total
            res = st.session_state.round_results
            st.success("🎉 这一轮全部做完啦！")
            st.write(
                f"{st.session_state.round_label} · 共 {total} 词，"
                f"已作答 {len(res)}，答对 {sum(1 for v in res.values() if v)}。"
            )
            st.divider()
            lesson = st.session_state.get("round_lesson", "全部")
            where = "全部词库" if lesson == "全部" else lesson
            scope = None if lesson == "全部" else _lesson_ids(lesson, LESSONS)
            n_wrong = len(get_due_wrong_words(only_ids=scope))
            d1, d2 = st.columns(2)
            if d1.button(f"再练一遍（{where}）", type="primary"):
                if lesson == "全部":
                    start_full_round(batch_size)
                else:
                    start_lesson_round(lesson, LESSONS, batch_size)
                st.rerun()
            if d2.button(f"复习错词（{n_wrong}）", disabled=n_wrong == 0):
                start_lesson_review(lesson, LESSONS, False, batch_size)
                st.rerun()
        else:
            st.info("先从左侧选课、点「开始这一课」。")
    else:
        current_no = st.session_state.index
        total = st.session_state.round_total
        st.subheader(f"第 {current_no}/{total} 词")
        st.caption(
            f"{st.session_state.round_label} · {mode_name} · "
            f"每 {st.session_state.batch_size_round} 个歇一下 · 还剩 {total - current_no} 词"
        )

        zh_gloss = word_zh(current_word["text"])

        last_wrong = get_last_wrong_answer(current_word["id"])
        if last_wrong:
            st.warning(f"这个词你之前写错成：{last_wrong}")

        wire_form_enter_submit()

        if st.session_state.play_on_load:
            if PROMPT_TYPE in ("fr_audio", "zh_audio"):
                speak_prompt(current_word)
            st.session_state.play_on_load = False

        if PROMPT_TYPE == "zh_text":
            st.info(f"中文意思：{zh_gloss}")
        elif PROMPT_TYPE == "fr_text":
            st.info(f"读出来：{current_word['text']}")
        elif PROMPT_TYPE == "fr_morph":
            st.info(f"阳性：{current_word['text']} — {zh_gloss}，写出它的阴性形式")

        if ANSWER_FIELDS == ("speak_fr",):
            render_speak(current_word)
        elif ANSWER_FIELDS == ("fem",):
            if not VOCAB.get(current_word["text"], {}).get("fem"):
                st.caption("（这个词没有阴阳性变化）")
                if st.button("下一题 ▶", type="primary"):
                    next_word()
                    st.rerun()
            else:
                col_p, col_a, col_b = st.columns(3)
                if col_p.button("上一题", disabled=st.session_state.index <= 1):
                    if prev_word():
                        st.rerun()
                if col_a.button("显示答案"):
                    st.session_state.show_answer = True
                    if not st.session_state.graded:
                        record_attempt(current_word["id"], "（看了答案）", False, "morph")
                        st.session_state.round_results[current_word["id"]] = False
                        st.session_state.graded = True
                if col_b.button("下一题"):
                    next_word()
                    st.rerun()
                with st.form("morph_form", clear_on_submit=True):
                    fem_ans = st.text_input("阴性形式：", key="ans_fem")
                    submitted_m = st.form_submit_button("提交答案", type="primary")
                if st.session_state.focus_input:
                    focus_answer_input()
                    st.session_state.focus_input = False
                if submitted_m:
                    if st.session_state.graded:
                        ok = bool(matcher.check_fr(fem_ans, VOCAB[current_word["text"]]["fem"]))
                        st.session_state.feedback = {
                            "type": "success" if ok else "error",
                            "message": ("✅（练习，不计分）" if ok else "❌（练习，不计分）")
                            + VOCAB[current_word["text"]]["fem"],
                        }
                    else:
                        _finalize_morph(current_word, fem_ans)
                        if auto_next and st.session_state.feedback["type"] == "success":
                            time.sleep(0.6)
                            next_word()
                    st.rerun()
        elif st.session_state.pending:
            p = st.session_state.pending
            st.warning("中文拿不准，对照一下你判：")
            j_rows = []
            if "fr" in ANSWER_FIELDS:
                j_rows.append(
                    ("法语", (p["fr_ans"] or "").strip() or "（空）", current_word["text"], bool(p["fr_ok"]))
                )
            j_rows.append(("中文", (p["zh_ans"] or "").strip() or "（空）", zh_gloss, None))
            render_answer_table(j_rows)
            jc1, jc2 = st.columns(2)
            if jc1.button("✅ 算我对", type="primary"):
                _finalize(current_word, p["fr_ans"], p["zh_ans"], p["fr_ok"], True)
                if auto_next:
                    st.success(st.session_state.feedback["message"])
                    time.sleep(0.6)
                    next_word()
                st.rerun()
            if jc2.button("❌ 算我错"):
                _finalize(current_word, p["fr_ans"], p["zh_ans"], p["fr_ok"], False)
                st.rerun()
        else:
            col_prev, col_a, col_b, col_c = st.columns(4)

            with col_prev:
                if st.button("上一题", disabled=st.session_state.index <= 1):
                    if prev_word():
                        st.rerun()

            with col_a:
                if st.button("播放 / 重听"):
                    speak_prompt(current_word)

            with col_b:
                if st.button("显示答案"):
                    st.session_state.show_answer = True
                    if not st.session_state.graded:   # 看答案 = 算一次错（防抄答案刷分）
                        if SKILL == "both":
                            record_attempt(current_word["id"], "（看了答案）", False, "transcribe")
                            record_attempt(current_word["id"], "（看了答案）", False, "meaning")
                        else:
                            record_attempt(current_word["id"], "（看了答案）", False, SKILL)
                        st.session_state.round_results[current_word["id"]] = False
                        st.session_state.graded = True

            with col_c:
                if st.button("下一题"):
                    next_word()
                    st.rerun()

            with st.form("answer_form", clear_on_submit=True):
                fr_ans = st.text_input("法语：", key="ans_fr") if "fr" in ANSWER_FIELDS else ""
                zh_ans = st.text_input("中文：", key="ans_zh") if "zh" in ANSWER_FIELDS else ""
                submitted = st.form_submit_button("提交答案", type="primary")

            if st.session_state.focus_input:
                focus_answer_input()
                st.session_state.focus_input = False

            if submitted:
                fr_ok = matcher.check_fr(fr_ans, current_word["text"]) if "fr" in ANSWER_FIELDS else None
                zh_res = matcher.check_zh(zh_ans, zh_gloss) if "zh" in ANSWER_FIELDS else None
                if st.session_state.graded:
                    # 这道题已评过分：再输只算练习，显示对错但不计分、不入库
                    ok = (bool(fr_ok) if "fr" in ANSWER_FIELDS else True) and (
                        zh_res is True if "zh" in ANSWER_FIELDS else True
                    )
                    st.session_state.feedback = {
                        "type": "success" if ok else "error",
                        "message": (
                            f"✅（练习，不计分）{current_word['text']}"
                            if ok
                            else f"❌（练习，不计分）答案：{current_word['text']}"
                        ),
                    }
                elif "zh" in ANSWER_FIELDS and zh_res is None:
                    st.session_state.pending = {"fr_ans": fr_ans, "zh_ans": zh_ans, "fr_ok": fr_ok}
                    st.rerun()
                else:
                    zh_ok = bool(zh_res) if "zh" in ANSWER_FIELDS else True
                    _finalize(current_word, fr_ans, zh_ans, fr_ok, zh_ok)
                    if auto_next and st.session_state.feedback["type"] == "success":
                        st.success(st.session_state.feedback["message"])
                        time.sleep(0.6)
                        next_word()
                    st.rerun()   # 立刻重跑：左侧词表实时刷新 ✅/❌ 与掌握度

        if ANSWER_FIELDS != ("speak_fr",):
            if st.session_state.show_answer:
                if ANSWER_FIELDS == ("fem",):
                    st.info(f"阴性：{VOCAB.get(current_word['text'], {}).get('fem', '（无）')}")
                else:
                    st.info(f"答案：{current_word['text']} — {zh_gloss}")

            fb = st.session_state.feedback
            if fb:
                fb_rows = fb.get("rows") or []
                if len(fb_rows) >= 2:   # 法+中 多字段：2×2 对照表
                    (st.success if fb["type"] == "success" else st.error)(
                        "✅ 对" if fb["type"] == "success" else "❌ 有错"
                    )
                    render_answer_table(fb_rows)
                elif fb["type"] == "success":
                    st.success(fb["message"])
                else:
                    st.error(fb["message"])

            # 词义面板（中文+Anki卡/词典）在下方
            if st.session_state.show_answer or st.session_state.feedback:
                render_learn_panel(current_word["text"])

        if st.button("🙈 这个词不用背（隐藏，不再出现）"):
            set_word_hidden(current_word["id"], True)
            next_word()
            st.rerun()

        with st.expander("查看这个词的最近记录"):
            history = get_attempt_history(current_word["id"])

            if not history:
                st.write("还没有记录。")
            else:
                for item in history:
                    mark = "✅" if item["is_correct"] else "❌"
                    st.write(f"{mark} `{item['answer']}`    {item['created_at']}")


def render_word_panel():
    """右侧词表：行底色=历史掌握度（灰→黄→绿）；词前 ✅/❌=本轮结果。返回被点选的词或 None。"""
    if not st.session_state.get("pool"):
        st.caption("开始一课后，这里列出全部词。")
        return None
    st.markdown("**📋 词表**")
    st.caption(
        "听=听写(听法语写法语)、产=产出(看/听中文写法语)、义=理解(听法语写中文)、音=发音、变=阴阳性变形，"
        "各列按掌握度上色（灰→黄→绿）；「词」列底色=适用维度里最弱。词前 ▶=当前词、✅/❌=本轮结果；"
        "🙈+灰行=已隐藏（不进练习）。点任一词 → 主区可「隐藏 / 恢复」。"
    )
    show_trans = st.checkbox("显示翻译", value=False, key="show_trans")
    pool = st.session_state.pool
    res = st.session_state.round_results
    rows = get_words_by_ids(pool)
    # 把本课已隐藏的词也列出来（弱化显示，便于查看与恢复）
    lesson = st.session_state.get("round_lesson", "全部")
    lesson_lemmas = set(VOCAB) if lesson == "全部" else set(LESSONS.get(lesson, []))
    pool_ids = {r["id"] for r in rows}
    hidden_extra = [
        r for r in get_hidden_words()
        if r["text"] in lesson_lemmas and r["id"] not in pool_ids
    ]
    hidden_ids = {r["id"] for r in hidden_extra}
    rows = rows + hidden_extra
    attempts = get_attempts_for_words([r["id"] for r in rows])
    scores = {r["id"]: mastery_mod.skill_scores(attempts.get(r["id"], [])) for r in rows}

    cur = st.session_state.get("current_word")
    cur_id = cur["id"] if cur is not None else None

    def _disp(r):
        if r["id"] in hidden_ids:
            return f"🙈 {r['text']}"
        here = "▶ " if r["id"] == cur_id else ""
        icon = "✅ " if res.get(r["id"]) is True else "❌ " if res.get(r["id"]) is False else ""
        return f"{here}{icon}{r['text']}"

    df = pd.DataFrame(
        {
            "词": [_disp(r) for r in rows],
            "听": ["" for _ in rows],
            "产": ["" for _ in rows],
            "义": ["" for _ in rows],
            "音": ["" for _ in rows],
            "变": ["" for _ in rows],
            "翻译": [word_zh(r["text"]) for r in rows],
            "状态": ["已隐藏" if r["id"] in hidden_ids else "" for r in rows],
        }
    )

    def _style(row):
        r = rows[row.name]
        if r["id"] in hidden_ids:                       # 已隐藏：整行弱化
            return ["background-color:#fafafa; color:#bbb" for _ in row.index]
        sc = scores[r["id"]]
        has_fem = bool(VOCAB.get(r["text"], {}).get("fem"))
        skills = mastery_mod.BASE_SKILLS + (("morph",) if has_fem else ())
        cmap = {
            "词": mastery_mod.mastery_color(mastery_mod.overall(sc, skills=skills)),
            "听": mastery_mod.mastery_color(sc.get("transcribe", 0.0)),
            "产": mastery_mod.mastery_color(sc.get("produce", 0.0)),
            "义": mastery_mod.mastery_color(sc.get("meaning", 0.0)),
            "音": mastery_mod.mastery_color(sc.get("pron", 0.0)),
            "变": mastery_mod.mastery_color(sc.get("morph", 0.0)) if has_fem else "#f5f5f5",
        }
        return [
            f"background-color:{cmap[c]}; color:#1a1a1a" if c in cmap else ""
            for c in row.index
        ]

    cols = ["词", "听", "产", "义", "音", "变", "翻译", "状态"] if show_trans else ["词", "听", "产", "义", "音", "变", "状态"]
    event = st.dataframe(
        df.style.apply(_style, axis=1),
        column_order=cols,
        hide_index=True,
        use_container_width=True,
        height=740,
        on_select="rerun",
        selection_mode="single-row",
        key="word_table",
    )
    sel = event.selection.rows if getattr(event, "selection", None) else []
    return rows[sel[0]]["text"] if sel else None


def _checkpoint_title(card: dict) -> str:
    """短标题给侧栏列表用：优先 species 名，其次正面第一行。"""
    if card.get("kind") == "conj":
        return f"{card.get('verb', '')}（变位）"
    if card.get("kind") == "production":
        return f"AI产出 · {card.get('label', '')}"
    raw = card.get("source_species") or (card.get("front") or "")
    lines = str(raw).splitlines()
    title = " ".join((lines[0] if lines else "").split())
    return title[:86] + ("…" if len(title) > 86 else "")


def _format_answer_inline(text: str) -> str:
    """把知识点答案里的重点接口、代词、提示词做成富文本。"""
    out = html.escape(text)
    for phrase in ("先诊断", "判断顺序", "核心区别", "注意", "重要边界", "基础位置", "常用顺序"):
        out = out.replace(phrase, f"<strong class='answer-key'>{phrase}</strong>")
    out = re.sub(
        r"(à \+ [^，。；:：、。]+|de \+ [^，。；:：、。]+|直接宾语|间接宾语|动词接口|数量词)",
        r"<u>\1</u>",
        out,
    )
    out = re.sub(
        r"(?<![\wÀ-ÿ])(le|la|les|lui|leur|y|en|me|te|se|nous|vous|COD|COI|à|de)(?![\wÀ-ÿ])",
        r"<span class='answer-fr'>\1</span>",
        out,
        flags=re.IGNORECASE,
    )
    return out


CHECKPOINT_ANSWER_CSS = "\n".join(
    [
        "<style>",
        ".checkpoint-answer{font-size:.9rem;line-height:1.35;color:#1f2933;}",
        ".checkpoint-answer .answer-lead{font-weight:750;color:#123b72;margin:.05rem 0 .35rem;}",
        ".checkpoint-answer .answer-line{margin:.18rem 0;}",
        ".checkpoint-answer .answer-gap{height:.35rem;}",
        ".checkpoint-answer .answer-num,.checkpoint-answer .answer-dot{font-weight:750;color:#5b21b6;margin-right:.28rem;}",
        ".checkpoint-answer .answer-key{font-weight:800;color:#9d174d;}",
        ".checkpoint-answer .answer-fr{font-family:Georgia,'Times New Roman',serif;font-weight:700;color:#0f766e;}",
        ".checkpoint-answer u{text-decoration-thickness:2px;text-underline-offset:3px;color:#7c2d12;}",
        "</style>",
    ]
)


def _checkpoint_answer_html(card: dict, include_style: bool = False) -> str:
    """主窗口和侧栏共用的答案渲染：保留结构并增强重点样式。"""
    raw = str(card.get("back") or "")
    lines = raw.splitlines() or [raw]
    body = [CHECKPOINT_ANSWER_CSS] if include_style else []
    body.append("<div class='checkpoint-answer'>")
    seen_lead = False
    for line in lines:
        text = line.strip()
        if not text:
            body.append("<div class='answer-gap'></div>")
            continue
        numbered = re.match(r"^(\d+)\.\s+(.*)$", text)
        if numbered:
            body.append(
                f"<div class='answer-line'><span class='answer-num'>{numbered.group(1)}.</span>"
                f"{_format_answer_inline(numbered.group(2))}</div>"
            )
            continue
        if text.startswith("- "):
            body.append(
                f"<div class='answer-line'><span class='answer-dot'>•</span>"
                f"{_format_answer_inline(text[2:])}</div>"
            )
            continue
        cls = "answer-lead" if not seen_lead else "answer-line"
        body.append(f"<div class='{cls}'>{_format_answer_inline(text)}</div>")
        seen_lead = True
    body.append("</div>")
    return "\n".join(body)


def _checkpoint_kind(card: dict) -> str:
    if "mixed-pronoun-review" in card.get("tags", []):
        return "代词复习"
    return "机判" if card.get("answer") else "自评"


# 知识点「类别」：从 tags 里挑最有信息量的（具体→宽泛），给列表分组/查找用。
_CAT_RULES = [
    ("mixed-pronoun-review", "代词"),
    ("conjugation", "变位"),
    ("word_family_confusion", "动词词族"),
    ("pronominal_reflexive", "代词式动词"),
    ("past_participle_agreement", "过去分词配合"),
    ("agreement", "性数配合"),
    ("tense_system", "时态"),
    ("comparison", "比较"),
    ("article", "冠词"),
    ("gender_number", "性数"),
    ("spelling_pronunciation_gap", "拼写发音"),
    ("requires_de", "介词 de"),
    ("requires_a", "介词 à"),
    ("preposition_interface", "介词"),
    ("frequency_expressions", "频率"),
    ("listening_keyword", "听力词"),
    ("sentence_frame", "句型"),
]


def _checkpoint_category(card: dict) -> str:
    """知识点类别（中文）：用于在列表里按语法主题查找，而不是机判/自评这种判分方式。"""
    if card.get("kind") == "conj":
        return "变位"
    if card.get("kind") == "production":
        return "产出"
    if card.get("study_group_label"):
        return str(card["study_group_label"])
    tags = set(card.get("tags") or [])
    for tag, cat in _CAT_RULES:
        if tag in tags:
            return cat
    return "词汇"


def _checkpoint_mastery_score(state: dict | None) -> float:
    state = state or {}
    return srs.checkpoint_mastery_score(
        state.get("correct_streak", 0),
        state.get("interval_days", 0),
    )


def _checkpoint_mastery_mark(score: float) -> str:
    if score >= 0.75:
        return "🟩"
    if score >= 0.35:
        return "🟨"
    return "⬜"


def _render_checkpoint_lookback(card_id: str) -> None:
    """「上次怎么答的」：同一张卡历次作答，强化记忆（折叠，避免泄题）。"""
    past = get_checkpoint_attempts(card_id, limit=3)
    if not past:
        return
    with st.expander(f"📖 这张卡你以前怎么答的（{len(past)} 次）"):
        for p in past:
            mark = "✅" if p["correct"] else "❌"
            wrote = f"你写「{p['user_answer']}」" if p["user_answer"] else "自评"
            st.caption(f"{p['created_at']} · {mark} {wrote}")


def _render_checkpoint_question_cell(label: str, score: float, current: bool) -> None:
    color = mastery_mod.mastery_color(score)
    border = "#8aa7ff" if current else "#d8d8d8"
    weight = 750 if current else 600
    text = html.escape(label)
    st.markdown(
        f"<div style='min-height:2.55rem;border-radius:7px;border:1px solid {border};"
        f"background:{color};display:flex;align-items:center;padding:.38rem .55rem;"
        f"font-weight:{weight};color:#1a1a1a;line-height:1.25;'>{text}</div>",
        unsafe_allow_html=True,
    )


def _set_checkpoint_index(i: int, *, show_back: bool = False) -> None:
    cards = st.session_state.get("cp_cards") or []
    if not cards:
        st.session_state.cp_index = 0
        st.session_state.cp_show_back = False
        st.session_state.pop("cp_feedback", None)
        return
    st.session_state.cp_index = max(0, min(i, len(cards) - 1))
    st.session_state.cp_show_back = show_back
    st.session_state.pop("cp_feedback", None)


def render_checkpoint_panel() -> None:
    """知识点目录：真·表格(st.dataframe)，点某行跳到那张卡；「掌握」列按 SRS 间隔上色。"""
    cards = st.session_state.get("cp_cards") or []
    if not cards:
        st.caption("当前没有知识点卡。")
        return
    cur = max(0, min(st.session_state.get("cp_index", 0), len(cards) - 1))
    st.markdown("**📋 知识点表**")
    st.caption("「类别」可查找主题（代词/变位/时态/介词…）；「掌握」按 SRS 间隔上色；▶=当前；点行跳到那张卡。用表格右上角 🔍 搜「变位」「代词」「-dre」等关键字定位。")
    show_answers = st.checkbox("显示答案", value=False, key="cp_show_answer_list")
    states = get_checkpoint_state([c["id"] for c in cards])
    scores = [_checkpoint_mastery_score(states.get(c["id"])) for c in cards]

    data = {
        "#": [("▶ " if i == cur else "") + str(i + 1) for i in range(len(cards))],
        "类别": [_checkpoint_category(c) for c in cards],
        "知识点": [_checkpoint_title(c) for c in cards],
        "掌握": ["" for _ in cards],
    }
    if show_answers:
        data["答案"] = [" ".join(str(c.get("back") or "").split())[:120] for c in cards]
    df = pd.DataFrame(data)

    def _style(row):
        sc = scores[row.name]
        return [
            f"background-color:{mastery_mod.mastery_color(sc)}; color:#1a1a1a" if col == "掌握" else ""
            for col in row.index
        ]

    event = st.dataframe(
        df.style.apply(_style, axis=1),
        hide_index=True,
        use_container_width=True,
        height=740,
        on_select="rerun",
        selection_mode="single-row",
        key=f"cp_table_{cur}",
    )
    sel = event.selection.rows if getattr(event, "selection", None) else []
    if sel and sel[0] != cur:
        _set_checkpoint_index(sel[0])
        st.rerun()


def render_card_view(lemma: str) -> None:
    """主窗口里开卷看某个词的完整 Anki 卡。"""
    zh = word_zh(lemma)
    st.subheader(f"📖 {lemma}" + (f" — {zh}" if zh else ""))
    # 软删除：点词进来这里就能隐藏/恢复（不用进听写流程）
    _ids = get_ids_for_lemmas([lemma])
    if _ids:
        wid = _ids[0]
        if wid in _hidden_id_set():
            st.caption("🙈 这个词当前已隐藏，不进任何练习。")
            if st.button("↩︎ 恢复（重新纳入背诵）", key="cardview_restore"):
                set_word_hidden(wid, False)
                st.rerun()
        else:
            if st.button("🙈 这个词不用背（隐藏）", key="cardview_hide"):
                set_word_hidden(wid, True)
                st.rerun()
    state = card_state_cached(lemma)
    if state["status"] == "ok":
        components.html(
            state["html"] + "<style>.qa-summary{display:none !important}</style>",
            height=820,
            scrolling=True,
        )
    else:
        if state["status"] == "stub":
            st.warning(f"⚠️ Anki 卡{state['reason']}，待重新生成。")
        definition = macdict_cached(lemma)
        if definition:
            st.markdown(f"**词典（macOS）**：{definition}")
        elif state["status"] == "missing":
            st.info("这个词还没有 Anki 卡，也没查到法语词典释义。")


def render_checkpoint() -> None:
    """知识点卡片复习（独立流程）：正面→（有答案机判 / 无答案揭示自评）→ 排期。"""
    cards = st.session_state.get("cp_cards") or []
    i = st.session_state.cp_index
    if i >= len(cards):
        st.success(f"✅ 这组知识点过完了（{len(cards)} 张）！")
        if cards and st.button("← 回到最后一张"):
            _set_checkpoint_index(len(cards) - 1)
            st.rerun()
        if st.button("↩︎ 退出知识点", type="primary"):
            st.session_state.cp_active = False
            st.rerun()
        return
    card = cards[i]
    if card.get("kind") == "conj":                    # 动词变位卡：同一 deck，按卡型分派
        _render_conj_card(card, i, len(cards),
                          set_index=lambda n: _set_checkpoint_index(n),
                          on_exit=lambda: st.session_state.update(cp_active=False),
                          exit_label="↩︎ 退出知识点")
        return
    if card.get("kind") == "production":              # AI 自由产出题：同一 deck，提交时按需加载模型
        _render_production_card(card, i, len(cards),
                               set_index=lambda n: _set_checkpoint_index(n),
                               on_exit=lambda: st.session_state.update(cp_active=False))
        return
    st.subheader(f"📝 知识点 {i + 1}/{len(cards)}")
    if st.session_state.get("cp_label"):
        st.caption(st.session_state.cp_label)
    if st.button("↩︎ 退出知识点"):
        st.session_state.cp_active = False
        st.rerun()
    st.info(card["front"])
    answer = (card.get("answer") or "").strip()

    def _advance():
        st.session_state.cp_index = min(st.session_state.cp_index + 1, len(cards))
        st.session_state.cp_show_back = False
        st.session_state.pop("cp_feedback", None)

    def _previous(*, show_back: bool = False):
        _set_checkpoint_index(i - 1, show_back=show_back)

    def _next(*, show_back: bool = False):
        _set_checkpoint_index(i + 1, show_back=show_back)

    nav_prev, nav_pos, nav_next = st.columns([1, 2, 1])
    if nav_prev.button("← 上一个", disabled=i == 0, key="cp_prev_top"):
        _previous()
        st.rerun()
    nav_pos.caption(f"{i + 1} / {len(cards)}")
    if nav_next.button("下一个 →", disabled=i >= len(cards) - 1, key="cp_next_top"):
        _next()
        st.rerun()

    _render_checkpoint_lookback(card["id"])
    if not st.session_state.get("cp_show_back"):
        if answer:
            with st.form("cp_form", clear_on_submit=True):
                ans = st.text_input("你的答案：", key="cp_ans")
                if st.form_submit_button("提交", type="primary"):
                    ok = bool(matcher.check_fr(ans, answer))
                    update_checkpoint(card["id"], ok)
                    save_checkpoint_attempt(card["id"], ans, ok)
                    st.session_state.cp_feedback = (ok, ans)
                    st.session_state.cp_show_back = True
                    st.rerun()
        else:
            if st.button("👁 揭示答案", type="primary"):
                st.session_state.cp_show_back = True
                st.rerun()
    else:
        fb = st.session_state.get("cp_feedback")
        if fb is not None:                       # 机判卡：已判，给结果 + 下一张
            ok, ans = fb
            (st.success if ok else st.error)(
                (f"✅ 对：{answer}" if ok else f"❌ 你写「{ans}」，应为：{answer}")
            )
            st.markdown("**📖 答案**")
            st.markdown(_checkpoint_answer_html(card, include_style=True), unsafe_allow_html=True)
            c1, c2 = st.columns([1, 2])
            if c1.button("← 上一个", disabled=i == 0, key="cp_prev_answered"):
                _previous(show_back=True)
                st.rerun()
            if c2.button("下一张 ▶", type="primary"):
                _advance()
                st.rerun()
        else:                                    # 自评卡：揭示背面 → 我对/我错
            st.markdown("**📖 答案**")
            st.markdown(_checkpoint_answer_html(card, include_style=True), unsafe_allow_html=True)
            a, b, c = st.columns(3)
            if a.button("← 上一个", disabled=i == 0, key="cp_prev_self"):
                _previous(show_back=True)
                st.rerun()
            if b.button("✅ 我对", type="primary"):
                update_checkpoint(card["id"], True)
                save_checkpoint_attempt(card["id"], None, True)
                _advance()
                st.rerun()
            if c.button("❌ 我错"):
                update_checkpoint(card["id"], False)
                save_checkpoint_attempt(card["id"], None, False)
                _advance()
                st.rerun()


@st.fragment(run_every=15)
def _llm_idle_watch() -> None:
    # 引擎级兜底：只要模型加载着就盯（不论在哪个视图），闲置即卸载，最大泄漏=闲置阈值
    if not st.session_state.get("llm_loaded"):
        return
    now = time.time()
    last_active = st.session_state.get("llm_last_active", 0)
    if llm_lifecycle.should_idle_unload(True, last_active, now):
        llm.unload()
        st.session_state.llm_loaded = False
        st.session_state.llm_error = "闲置超过 5 分钟，模型已自动卸载并释放内存。"
        st.rerun(scope="app")
    st.caption(f"模型会在闲置 {llm_lifecycle.idle_minutes_left(last_active, now)} 分钟后自动卸载。")


def _render_hints(spec: dict) -> str:
    """作答前的可选提示（脚手架）。返回用了哪些提示，用于历史与 SRS 计分。"""
    if spec.get("ignore"):
        st.caption(f"本轮忽略：{spec['ignore']}")
    used = []
    c1, c2, c3 = st.columns(3)
    if c1.checkbox("💡 词表", key=f"hint_w_{spec['id']}") and spec.get("candidates"):
        st.caption("词表（开放，可用别的正确表达）：" +
                   "；".join(f"{c['zh']}→{'/'.join(c['fr'])}" for c in spec["candidates"]))
        used.append("词表")
    if c2.checkbox("💡 变位", key=f"hint_c_{spec['id']}") and spec.get("conjugations"):
        st.caption("变位：" + "；".join(f"{c['value']}（{c['verb']} {c['form']}）" for c in spec["conjugations"]))
        used.append("变位")
    if c3.checkbox("💡 句式", key=f"hint_s_{spec['id']}") and spec.get("structures"):
        st.caption("句式：" + "；".join(spec["structures"]))
        used.append("句式")
    return "+".join(used) if used else "无"


def _render_spec_review(spec: dict) -> None:
    """提交后揭示参考句与完整规范（不再计入提示等级）。"""
    with st.expander("📋 规范与参考（提交后揭示）", expanded=True):
        if spec.get("references"):
            st.markdown("**参考句**：" + " ／ ".join(f"`{r}`" for r in spec["references"]))
        if spec.get("required"):
            st.caption("必须表达：" + "；".join(spec["required"]))
        if spec.get("status") != "reviewed":
            st.caption("⚠️ 此规范为 AI 起草（draft），尚未人工核验。")


def _render_lookback(cue_id: str) -> None:
    """「上次→这次」：同题历次作答 + 当时的染色，激活记忆。"""
    past = get_ai_attempts(cue_id, limit=3)
    if not past:
        return
    with st.expander(f"📖 这道题你以前怎么写的（{len(past)} 次）"):
        for p in past:
            st.caption(f"{p['created_at']} · 终判：{p['verdict']} · 提示：{p['hint_level'] or '无'}")
            segs = aigrade.anchor_and_segment(p["answer"], p["feedback"])
            st.markdown(f'<div style="line-height:1.9">{aigrade.to_html(segs)}</div>',
                        unsafe_allow_html=True)
            if p["minimal"]:
                st.caption(f"最小修正：{p['minimal']}")


def _render_grade_result(result: dict, answer: str) -> None:
    if result.get("parse_error"):
        st.warning("模型没有按 JSON 返回，下面显示原文；请你据此终判。")
        st.code(result.get("raw", ""))
        return
    # 第 8 步：模型只给「片段+状态」，位置由代码逐字验证、染色（颜色=AI 判断，需核验）
    segs = aigrade.anchor_and_segment(answer, result.get("spans", []))
    st.markdown("**你的句子（AI 批改 · 需核验）**")
    st.markdown(
        f'<div style="line-height:2;font-size:1.05em">{aigrade.to_html(segs)}</div>',
        unsafe_allow_html=True,
    )
    st.caption("🟩 接受／可接受变体　🟨 可接受但不自然　🟥 错误　⬜ 应删除（删除线）。颜色是 AI 判断，请自己核验。")
    flagged = [s for s in segs if s.get("状态") in ("错误", "多余", "正确但不自然", "拿不准")]
    for s in flagged:
        repl = f" → `{s['替换']}`" if s.get("替换") else ""
        st.markdown(f"- {s.get('维度','')}·**{s['状态']}**：`{s['text']}` — {s.get('依据','')}{repl}")
    if result.get("最小修正"):
        st.write(f"**最小修正（只改错处）：** {result['最小修正']}")
    if result.get("更自然版"):
        st.write(f"**更自然的参考：** {result['更自然版']}")
    if result.get("总判定"):
        st.caption(f"AI 建议总判定：{result['总判定']}（仅供参考，终判由你点）")


def _render_production_card(card: dict, i: int, total: int, *, set_index, on_exit) -> None:
    """AI 自由产出题作为 deck 里的一种卡（kind=production）：提交时才按需加载本地模型。
    判分仍走 aigrade（人工规范 + 代码确定性 + 三态终判）；模型只给建议。"""
    if st.button("↩︎ 退出知识点", key="prod_exit"):
        on_exit()
        for _k in ("llm_result", "llm_graded_answer", "llm_grade_error", "llm_hint_level"):
            st.session_state.pop(_k, None)
        st.rerun()
    st.markdown(f"**🤖 {card['label']}**　{i + 1}/{total}")
    st.info(card.get("target") or card["cue"])           # 本轮真正要写的（1/2 轮=只写主干）
    st.caption(card["instruction"])
    if card.get("target") and card["target"] != card.get("cue"):
        st.caption(f"完整句（下一轮再加）：{card['cue']}")
    if st.session_state.get("llm_loaded"):
        st.caption("🟢 本地模型已加载（闲置约 5 分钟自动卸载）")
    has_result = bool(st.session_state.get("llm_result"))
    _render_lookback(card["id"])
    hint_level = _render_hints(card)
    if has_result:
        _render_spec_review(card)

    with st.form(f"prod_{card['id']}"):
        answer = st.text_area("你的法语整句：", key=f"prod_ans_{card['id']}")
        submitted = st.form_submit_button("交给本地 AI 批改（首次会加载模型 ~10 秒）", type="primary")
    if submitted:
        st.session_state.llm_last_active = time.time()
        st.session_state.llm_hint_level = hint_level
        st.session_state.pop("llm_grade_error", None)
        st.session_state.pop("llm_result", None)
        if not answer.strip():
            st.session_state.llm_grade_error = "请先写一句法语。"
        else:
            try:
                if not st.session_state.get("llm_loaded"):
                    with st.spinner("加载本地模型中…首次 ~10 秒"):
                        llm.load()
                        st.session_state.llm_loaded = True
                with st.spinner("批改中…"):
                    raw = llm.chat(aigrade.build_prompt(card, answer.strip()))
                    st.session_state.llm_result = aigrade.normalize_result(raw)
                    st.session_state.llm_graded_answer = answer.strip()
                    try:
                        st.session_state.llm_model = llm._session_model()
                    except llm.LLMError:
                        st.session_state.llm_model = ""
            except llm.LLMError as exc:
                st.session_state.llm_grade_error = str(exc)
        st.rerun()

    if st.session_state.get("llm_grade_error"):
        st.error(st.session_state.llm_grade_error)
    result = st.session_state.get("llm_result")
    if not result:
        return
    _render_grade_result(result, st.session_state.get("llm_graded_answer", ""))
    assisted = st.session_state.get("llm_hint_level", "无") != "无"
    st.caption("AI 只提供建议；SRS 结果以你的终判为准。" +
               ("（你用了提示，「我对」不计为独立通过）" if assisted else ""))
    c_ok, c_wrong, c_unsure = st.columns(3)
    final_ok = c_ok.button("✅ 我对", type="primary", key="prod_right")
    final_wrong = c_wrong.button("❌ 我错", key="prod_wrong")
    final_unsure = c_unsure.button("🤔 拿不准", key="prod_unsure")
    if final_ok or final_wrong or final_unsure:
        verdict = "我对" if final_ok else "我错" if final_wrong else "拿不准"
        if final_wrong:
            update_checkpoint(card["id"], False)
        elif final_ok and not assisted:
            update_checkpoint(card["id"], True)
        save_ai_attempt(
            card["id"], st.session_state.get("llm_graded_answer", ""), verdict=verdict,
            minimal=result.get("最小修正", ""), natural=result.get("更自然版", ""),
            feedback=result.get("spans", []), hint_level=st.session_state.get("llm_hint_level", "无"),
            model=st.session_state.get("llm_model", ""))
        for _k in ("llm_result", "llm_graded_answer", "llm_grade_error", "llm_hint_level"):
            st.session_state.pop(_k, None)
        set_index(i + 1)
        st.rerun()


def _render_conj_card(card: dict, i: int, total: int, *, set_index, on_exit, exit_label: str) -> None:
    """渲染一张动词变位卡（整张范式手敲填空、逐格核对）。nav/退出由调用方注入，
    使它能同时服务 cp deck（cp_index）和旧独立流程（conj_index）。答案键来自 conjugate.py。"""
    if st.button(exit_label, key="conj_exit"):
        on_exit()
        st.session_state.pop("conj_results", None)
        st.rerun()
    st.markdown(f"### {card['verb']}　<small>{card['zh']}</small>　{i + 1}/{total}", unsafe_allow_html=True)
    st.caption("主语已给出，填空敲出每个变位；提交后逐格核对，多敲几遍就记住了。")
    _render_checkpoint_lookback(card["id"])

    with st.form(f"conjf_{card['id']}"):
        typed: dict = {}
        for t in card["tenses"]:
            st.markdown(f"**{t['label']}**")
            if t["kind"] == "single":
                typed[(t["key"], "_")] = st.text_input("过去分词", key=f"cj_{card['id']}_{t['key']}",
                                                       label_visibility="collapsed", placeholder="过去分词")
            else:
                cols = st.columns(4)
                for n, (pron, _idx) in enumerate(_CONJ_DISPLAY):
                    typed[(t["key"], pron)] = cols[n % 4].text_input(
                        pron, key=f"cj_{card['id']}_{t['key']}_{pron}", placeholder=pron)
        submitted = st.form_submit_button("提交并核对", type="primary")
    if submitted:
        res, all_ok = {}, True
        for t in card["tenses"]:
            if t["kind"] == "single":
                exp, got = t["answer"], typed[(t["key"], "_")]
                ok = bool(matcher.check_fr(got, exp))
                res[f"{t['key']}|_"] = (ok, got, exp); all_ok &= ok
            else:
                for pron, idx in _CONJ_DISPLAY:
                    exp, got = t["forms"][idx], typed[(t["key"], pron)]
                    ok = bool(matcher.check_fr(got, exp))
                    res[f"{t['key']}|{pron}"] = (ok, got, exp); all_ok &= ok
        n_ok = sum(1 for v in res.values() if v[0])
        update_checkpoint(card["id"], all_ok)
        save_checkpoint_attempt(card["id"], f"{n_ok}/{len(res)} 对", all_ok)
        st.session_state.conj_results = {"id": card["id"], "res": res, "all": all_ok, "n_ok": n_ok, "n": len(res)}
        st.rerun()

    results = st.session_state.get("conj_results")
    if results and results.get("id") == card["id"]:
        res = results["res"]
        (st.success if results["all"] else st.warning)(
            "✅ 全对！" if results["all"] else f"对 {results['n_ok']}/{results['n']}，看下面标注，多敲几遍。")
        for t in card["tenses"]:
            st.markdown(f"**{t['label']}**")
            if t["kind"] == "single":
                ok, got, exp = res[f"{t['key']}|_"]
                st.markdown(("✅ " if ok else "❌ ") + f"`{exp}`" + ("" if ok or not got else f"（你写「{got}」）"))
            else:
                parts = []
                for pron, _idx in _CONJ_DISPLAY:
                    rok, _got, rexp = res[f"{t['key']}|{pron}"]
                    parts.append(("✅" if rok else "❌") + f"{pron} {rexp}")
                st.caption("　".join(parts))
        b1, b2, b3 = st.columns(3)
        if b1.button("← 上一个", disabled=i == 0, key="conj_prev"):
            set_index(i - 1); st.session_state.pop("conj_results", None); st.rerun()
        if b2.button("🔁 再敲一遍", key="conj_redo"):
            st.session_state.pop("conj_results", None); st.rerun()
        if b3.button("下一个 ▶", disabled=i >= total - 1, key="conj_next"):
            set_index(i + 1); st.session_state.pop("conj_results", None); st.rerun()


# 左侧原生边栏词表（像 GPT/Claude 主页：自带折叠按钮，折叠后主区满宽）
with st.sidebar:
    st.divider()
    if st.session_state.get("cp_active"):
        render_checkpoint_panel()
        _selected = None
    else:
        _selected = render_word_panel()

# 在词表里点某个词 → 主区开卷看它的卡；点「回到听写」收起
if _selected != st.session_state.get("last_selected"):
    st.session_state.last_selected = _selected
    st.session_state.hide_preview = False
_show_card = bool(_selected) and not st.session_state.get("hide_preview", False)

if st.session_state.get("cp_active"):
    render_checkpoint()
else:
    # 唯一「今天到期」入口（词 + 知识点卡）：侧栏不再有重复的到期按钮（按当前选课作用域）
    _due_words = len(get_due_wrong_words(due_only=True, only_ids=_scope))
    _due_cp_cards = _due_checkpoint_cards(_lesson_cards(chosen_lesson))
    if _due_words or _due_cp_cards:
        _where = "全部课程" if chosen_lesson == "全部" else chosen_lesson
        bc = st.columns([3, 1, 1])
        bc[0].info(f"📅 今天到期（{_where}）：**{_due_words}** 个词 · **{len(_due_cp_cards)}** 张知识点卡")
        if _due_words and bc[1].button("复习到期词", key="due_words"):
            _leave_overlays()
            start_lesson_review(chosen_lesson, LESSONS, True, batch_size)
            st.rerun()
        if _due_cp_cards and bc[2].button("复习到期卡", key="due_cards"):
            _leave_overlays()
            _start_cards(_due_cp_cards, f"今天到期 · {chosen_lesson}", chosen_lesson)
            st.rerun()

    if _show_card:
        if st.button("↩︎ 回到听写"):
            st.session_state.hide_preview = True
            st.rerun()
        render_card_view(_selected)
    else:
        render_practice()

# 每次渲染后把当前一轮存档，刷新/重开能续上
if st.session_state.get("pool"):
    persist_round()

# 引擎级闲置卸载兜底：只要本地模型加载着就盯（不论当前哪个视图），闲置即卸载
_llm_idle_watch()
