今回の変更
#### `ctxledger/docs/mcp-api.md`
projection failure lifecycle の **HTTP action endpoint 実装済み状態** を、MCP API ドキュメントへ反映しました。

今回の方針:
- 既存 docs の責務分離を崩さず、MCP tool surface と HTTP route surface の両方を明示
- すでに実装済みの server/runtime/test の状態に合わせて、future wording を implemented wording へ更新
- HTTP action surface の request / response / error / runtime registration を docs 上で追跡できるように整理

---

### ドキュメントで反映した主な内容
#### 1. HTTP operator action surface を「実装済み」として明記
`docs/mcp-api.md` の projection failure lifecycle 説明で、以前は future 扱いだった内容を実装済みの記述に更新しました。

追加・明記した route / surface:
- `projection_failures_ignore`
- `projection_failures_resolve`

明記したポイント:
- concrete server surface として存在すること
- MCP tool に加えて HTTP route surface もあること
- canonical projection failure lifecycle state を更新するための action であること

---

#### 2. HTTP action route の入力 contract を docs に追加
HTTP action surface の request shape を docs に明記しました。

反映した内容:
- 既存の HTTP handler contract は `path: str` のまま維持
- selector は query parameter から取得
- representative query parameters:
  - `workspace_id`
  - `workflow_instance_id`
  - `projection_type` (optional)
  - `authorization` (auth enabled 時)

これにより、今回の server 実装が
- handler signature を壊していない
- query-string parse で action を実現している
ことが docs から読める状態になりました。

---

#### 3. operator action semantics を HTTP も含めて整理
projection failure lifecycle の mutation-side docs を更新し、MCP tool だけでなく HTTP action route も含む形に整理しました。

反映した主な内容:
- `projection_failures_ignore`
  - matching open failures を `ignored` で close
- `projection_failures_resolve`
  - matching open failures を `resolved` で close
- failure history は削除せず保持
- `ignored` と `resolved` の意味論を区別
- `projection_type` による optional scope があること

response の代表 shape として引き続き:
- `workspace_id`
- `workflow_instance_id`
- `projection_type`
- `updated_failure_count`
- `status`

を docs に残しています。

---

#### 4. HTTP action error behavior を docs に追加
HTTP route surface 側の representative error behavior を docs に追記しました。

反映した内容:
- validation failure
  - `400`
  - `error.code = "invalid_request"`
- workflow service 未初期化
  - `503`
  - `error.code = "server_not_ready"`
- service exception mapping
  - `404` / `not_found`
  - `400` / `invalid_request`
  - `500` / `server_error`
- auth failure
  - 既存 bearer-auth surface に従う `401`

---

#### 5. debug / health / readiness docs の registered route 例を更新
HTTP runtime の registered routes に action endpoints が入ることを docs の example payload に反映しました。

更新した example 箇所:
- `health()`
- `readiness()`
- `/debug/runtime`
- `/debug/routes`

HTTP route list の example は少なくとも次を含む状態へ更新:
- `runtime_introspection`
- `runtime_routes`
- `runtime_tools`
- `workflow_resume`
- `workflow_closed_projection_failures`
- `projection_failures_ignore`
- `projection_failures_resolve`

stdio tool list の example は引き続き少なくとも次を含みます:
- `resume_workflow`
- `projection_failures_ignore`
- `projection_failures_resolve`
- `memory_remember_episode`
- `memory_search`
- `memory_get_context`

---

#### 6. `v0.1.0` contract summary を更新
`Implemented Optional Surface` に、HTTP route surface としての projection failure actions も明記しました。

追加した summary:
- HTTP route surface for `projection_failures_ignore`
- HTTP route surface for `projection_failures_resolve`

---

### 今回変更したファイル
- `ctxledger/docs/mcp-api.md`
- `ctxledger/last_session.md`

---

### 確認結果
今回確認できている範囲:
- `ctxledger/docs/mcp-api.md`: diagnostics 問題なし

前回までに確認済みの状態:
- `ctxledger/src/ctxledger/server.py`: diagnostics 問題なし
- `ctxledger/tests/test_server.py`: diagnostics 問題なし
- `pytest -q tests/test_server.py`
  - `103 passed`

今回は docs 更新のみで、追加の test 実行は未実施です。

---

### git commit
- 今回の docs 更新については、まだ git commit 未実施

---

### 補足
- `.gitignore` は引き続き変更対象に含めない前提
- 今回の handoff は docs 反映後の状態に更新
- この session では `last_session.md` を docs 更新内容へリフレッシュ

---

### 現在の状態
projection failure lifecycle の public surface は、少なくとも以下が docs / implementation 上で整合しています。

#### read-side
- `workflow_resume`
- `/workflow-resume/{workflow_instance_id}/closed-projection-failures`

#### mutation-side (MCP / stdio)
- `projection_failures_ignore`
- `projection_failures_resolve`

#### mutation-side (HTTP runtime route surface)
- `projection_failures_ignore`
- `projection_failures_resolve`

#### docs
- `docs/mcp-api.md` に HTTP action surface 実装済み状態を反映済み

---

### 次に自然な作業
次に自然なのは以下です。

1. 今回の docs 更新を descriptive message で git commit する
2. 必要なら `docs/CHANGELOG.md` に docs / API surface の補足を追記する
3. integration / service 層で HTTP-oriented coverage を広げる
4. 実際の HTTP route contract 例をさらに具体的な request example 付きで docs に追加する