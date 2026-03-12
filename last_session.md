今回の変更
#### add implementation-plan review inventory for `v0.1.0`
`docs/imple_plan_0.1.0.md` と現在の repository state を比較し、未解決タスク・未確認事項・整合性ギャップを棚卸しした review ドキュメントを追加しました。

今回の方針:
- 既存の docs / tests / implementation の成熟度は高い一方、`v0.1.0` 実装計画に対して「どこが揃っていて、どこがまだ未解決か」を後続作業向けに明示する
- 特に MCP public surface について、implementation plan / README / visible runtime wiring のズレを整理する
- 後続の作業ループで、そのまま実装タスクに落とし込める形の inventory を `docs/` に保存する

---

### 追加したファイル
- `ctxledger/docs/imple_plan_review_0.1.0.md`

---

### `ctxledger/docs/imple_plan_review_0.1.0.md` の内容
#### 1. review の目的と使い方を明記
追加した内容:
- `docs/imple_plan_0.1.0.md` に対する plan-alignment review であること
- handoff / 実行ガイド / checkpoint として使うこと
- 主な比較対象:
  - `docs/imple_plan_0.1.0.md`
  - `README.md`
  - `src/ctxledger/server.py`
  - tests / operational docs

---

#### 2. 現在状態を `Confirmed aligned` / `Partially aligned` / `Gap` で分類
整理した観点:
- 確認済みで揃っている領域
- 一部揃っているが検証や整合が必要な領域
- plan に対して未解決の可能性が高い領域

主な `Confirmed aligned`:
- PostgreSQL schema / persistence baseline
- workflow service core
- Docker-based local deployment
- memory subsystem stub posture
- docs deliverables
- test layer presence

主な `Partially aligned`:
- MCP workflow surface exists, but naming mismatch may exist
- acceptance criteria likely satisfied internally, but public-surface evidence is incomplete

主な `Gap / likely unresolved`:
- required MCP workflow tool exposure
- required MCP resources
- `workflow_resume` vs `resume_workflow` naming mismatch
- resource-related tests
- public MCP interface audit

---

#### 3. 高優先の未解決タスクを inventory 化
最重要として整理したタスク:
- Task A — required MCP workflow tools の露出確認・不足分の実装
  - `workspace_register`
  - `workflow_start`
  - `workflow_checkpoint`
  - `workflow_complete`
- Task B — `workflow_resume` vs `resume_workflow` の canonical public name 決定と全層整合
- Task C — required MCP resources の実装確認 / 未実装なら実装
  - `workspace://{workspace_id}/resume`
  - `workspace://{workspace_id}/workflow/{workflow_instance_id}`

高優先の次段:
- resource tests の追加/確認
- public surface matrix の作成
- README と実 runtime surface の整合

中優先:
- acceptance criteria evidence table
- 必要なら `docs/imple_plan_0.1.0.md` 自体の revision

---

#### 4. 推奨実行順を明記
`docs/imple_plan_review_0.1.0.md` に記載した recommended next sequence:
1. actual MCP tool registration の audit
2. tool naming mismatch の解消
3. MCP resources の audit / 実装
4. resource tests の追加
5. docs と actual public surface の整合
6. acceptance / surface matrix 作成
7. その後に `v0.1.0` aligned と判断

---

### 今回変更したファイル
- `ctxledger/docs/imple_plan_review_0.1.0.md`
- `ctxledger/last_session.md`

---

### review で特に重要と判断した現時点の open questions
#### 1. required MCP workflow tools が runtime に実際に露出しているか
implementation plan / README では:
- `workspace_register`
- `workflow_start`
- `workflow_checkpoint`
- `workflow_resume`
- `workflow_complete`

が required workflow tools だが、visible runtime registration としては少なくとも:
- `resume_workflow`
- projection failure tools
- memory stub tools

が見えており、plan-required 5 tools の露出状況は未整合または未確認。

#### 2. required MCP resources が実装されているか
plan / README / API docs には:
- `workspace://{workspace_id}/resume`
- `workspace://{workspace_id}/workflow/{workflow_instance_id}`

が required resource として書かれているが、visible implementation evidence は今回 review 時点では未確認。

#### 3. `workflow_resume` と `resume_workflow` の naming mismatch
これは cosmetic ではなく:
- client expectation
- docs correctness
- acceptance criteria traceability
- MCP public surface clarity
に直結するため、高優先の unresolved item と整理した。

---

### 現在の整合状態
projection failure action route まわりの docs / tests / implementation はかなり揃っている一方で、`v0.1.0` implementation plan に対する全体評価では少なくとも以下の整理ができました。

#### 強く揃っている領域
- workflow service core
- postgres persistence baseline
- docker compose deployment
- memory stub behavior
- docs breadth
- test suite existence

#### 未解決の可能性が高い領域
- plan-required MCP tools の公開 surface
- plan-required MCP resources
- runtime naming consistency
- public surface audit

---

### git 状態メモ
- 今回追加した review artifact:
  - `docs/imple_plan_review_0.1.0.md`
- この handoff 更新時点では、今回の review artifact 追加について **まだ git commit 未実施**
- `.gitignore` は引き続き開発上必要な差分として存在しうるが、成果物に含めない前提

---

### 補足
- 今回は production code の変更なし
- 追加 test なし
- planning / inventory docs の追加が中心
- この review document は「実装完了判定」ではなく、「次にどこを掘るべきか」の整理に使う想定
- 特に次の work loop は docs 追加よりも、MCP public surface の実装監査に寄せるのが自然

---

### 次に自然な作業
次に自然なのは以下です。

1. `docs/imple_plan_review_0.1.0.md` を descriptive message で git commit する
2. actual MCP tool registration を監査して、plan-required workflow tools の露出有無を確定する
3. MCP resource registration / resolver 実装の有無を監査する
4. 監査結果をもとに、public surface matrix または acceptance evidence table を追加する