# L22 将来时学习组设计

## 目标

把 L22 中分散的简单将来时、条件式、先将来时与老师纠错卡编排成一个连续学习组，并增加少量机判产出卡，让学习者不仅能读懂规则，还能实际写出正确形式。

## 范围

- 只整理 L22 的“将来时系统”组；其他课程和 L22 其他知识点不重新分类。
- 保留现有 103 张 species 卡及其稳定 ID，避免丢失 SRS 掌握记录。
- 增加 6 张机判练习卡；它们是练习变体，不进入 103 个 species 覆盖分母。
- 不开发新的 drill 页面，复用现有 checkpoint、知识点表、行点击和 SRS。

## 数据合同

新增 `L22/L22.checkpoint_groups.json`。每个组定义：

- `id`：稳定英文标识；
- `label`：知识点表显示的中文组名；
- `order`：组在课程卡组中的位置；
- `species`：已有 species label 与组内顺序；
- `practice_cards`：稳定 ID、组内顺序、问题、答案解释与唯一机判答案。

构建器新增可选参数 `--checkpoint-groups`。未提供时保持当前输出不变；提供时只给指定 species 添加组元数据、生成练习卡并稳定排序。未知 species、重复成员、重复练习 ID 或缺少机判字段时构建失败。

## 学习顺序

1. 简单将来时的意义与 `词根 + 词尾`。
2. futur proche 与 futur simple 的边界。
3. 老师指出的核心错误：将来词根误接 imparfait 词尾会形成 conditionnel。
4. `voudrai/voudrais`、`finirons/finirions` 最小对照产出。
5. futur antérieur 的事件顺序、构成及触发词。
6. `aura fini/auront trouvé` 产出。
7. 区分“未来助动词”和“完成性过去分词”，避免称作过去时。
8. 老师要求的词根、过去分词与基础词汇复习。

## UI 与掌握度

知识点表继续使用现有 `st.dataframe`。卡片带 `study_group_label` 时，“类别”列显示“将来时系统”；列表顺序直接使用 manifest 顺序。新增卡继续用 checkpoint ID 写入现有 SRS，不增加平行状态。

## 验收

- L22 manifest 含 103 张 species 卡和 6 张练习卡，共 109 张。
- species 覆盖仍为 103/103。
- “将来时系统”25 张卡连续出现在列表前部。
- 6 张练习卡全部机判，答案唯一。
- 原 103 张卡 ID 集合完全不变；未分组卡保持原相对顺序。
- 全量测试通过，AppTest 能看到“将来时系统”类别并进入新增机判卡。
