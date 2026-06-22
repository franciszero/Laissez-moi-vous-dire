# 法语听写复习器

本地 Streamlit 小工具：用 macOS `say` 朗读法语词，你听写；答完显示词义（词表中文 + Anki 卡 + macOS 词典兜底）。支持「学习模式（按课）」和「考试模式（错题/到期，本地 SRS）」。

L22 另有「🤖 AI 精练」：用 Hermes 当前配置的本地 rapid-mlx 模型批改自由造句/整句翻译。模型只在进入该页时加载；退出、切换视图或闲置 5 分钟会自动卸载。AI 只给建议，SRS 对错由你最终确认。

## 运行

```bash
cd 听写
./run.sh            # 等价于 streamlit run app.py
```

浏览器打开 http://localhost:8501 。改了代码要点页面右上角 **Rerun**，或重启。

---

## 加新课程（两种方法，自己就能做）

词表按「课」组织：每课一个文件夹 `本地录屏课/<课名>/vocab.json`。
启动时会**自动扫描所有 `*/vocab.json`**——所以**任何含 `vocab.json` 的文件夹都会出现在左侧「选课」里**，文件夹叫什么名字都行（L19、考前冲刺、随便）。

### 方法 1：网页上传（推荐，不用碰 JSON）

1. 左侧栏 →「➕ 添加 / 自定义词表」
2. 上传一个 **TSV / CSV** 文件，每行是下面任一种：
   - `法语<Tab>中文`
   - `类别<Tab>法语<Tab>中文`（类别 = `NOMS` / `VERBES` / `ADJECTIFS` / `AUTRES`）
   - 分隔符 **Tab / 逗号 / Markdown 竖线表格** 都认；**表头行、`---` 分隔行会自动跳过**
3. 填课程名（如 `L19`）→ 点「导入这个词表」
4. 自动生成 `本地录屏课/L19/vocab.json`，**立刻出现在「选课」**

> 上传时词条会自动清洗成听写目标：去掉 `n. f. / v. t. / adv.` 等语法缩写、`[音标]`、`（中文注释）`；名词保留冠词（`la confiture`）；`X, 阴性形`（如 `client, e`）取基本形（`client`）。
> 同名课程会被拦下不覆盖——换个名字，或先删掉那个文件夹。

### 方法 2：手动放文件

在 `本地录屏课/<课名>/` 建一个 `vocab.json`，内容是数组，每个词**最少要 `lemma` 和 `zh`**：

```json
[
  {"lemma": "la pomme", "pos": "noun", "zh": "苹果", "lesson": "L19"},
  {"lemma": "courir",   "pos": "verb", "zh": "跑",   "lesson": "L19"}
]
```

刷新页面即出现在「选课」。完整字段可参考 `../L18/vocab.json`。

### 批量查重追加词条

准备一个 JSON 数组，每条至少包含 `lemma`、`pos`、`zh`，然后运行：

```bash
python3 scripts/merge_vocab.py --vocab ../L20/vocab.json --input batch.json
```

工具按规范化后的 lemma 去重：目标课已有词条保持原样，只追加缺词；同一批次的冲突释义会直接报错。重复运行结果不变。`--input -` 可从标准输入读取。

---

## 答完显示的词义来自哪（三档，自动降级）

1. **释义** = 你词表里的中文（最快、永远有）
2. **📇 完整 Anki 卡片** = 若该词在 Anki `Français` 牌组已制卡 → 原样显示整张卡背面（只读，不改你的卡；需要 Anki 开着 + 装了 AnkiConnect 插件）
3. **词典（macOS）** = 没 Anki 卡时，查 macOS 系统词典，**只显示法语释义**（英文结果会被过滤掉）
   - 想让词典覆盖率高：打开「词典」App → 设置 → 启用一本法语词典并**拖到列表最上面**
   - 需要 `pip install pyobjc-framework-CoreServices`（已在 requirements.txt）

---

## 数据与备份

- `dictation.db` = 你的听写进度（错词次数、连对、到期、历史）。每次结构性改动前会自动备份成 `dictation.db.*.bak`。
- `words.txt` = 最早的 L17（Leçon 25）词表，留作后备导入源。

## 制卡（可选，给 Anki 生成精美卡片）

`../L18/anki_batch_lecon23_24_25.txt` 是 anki-wordsmith 批处理格式：`词 (词性; 课文例句)`。
提交给 anki-wordsmith 服务即可生成 `Français` 牌组的卡片。**注意：名词必须带冠词**（`un Parisien` 不是 `Parisien`），这是 anki-wordsmith 的硬性校验。

## 开发

```bash
python3 -m pytest -q          # 跑单元测试
python3 scripts/build_vocab.py  # 从 L18/source/*.tsv 重新生成 L17/L18 的 vocab.json
```

模块划分：`vocab.py`（清洗/解析/加载词表）、`anki.py`（只读 AnkiConnect）、`llm.py`（按需 rapid-mlx 批改）、`macdict.py`（macOS 词典兜底）、`store.py`（sqlite 导入/查询）、`app.py`（Streamlit 编排）。
