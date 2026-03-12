今回の変更
#### `ctxledger/docs/mcp-api.md`
projection failure lifecycle の HTTP action surface について、**具体的な request / response example** を docs に追加しました。

今回の方針:
- すでに実装済みの HTTP route surface を、利用者がそのまま読んで使える粒度まで具体化
- 既存 docs の責務分離を維持しつつ、action route の入力方式と representative payload を明文化
- server 実装に合わせて、query parameter contract と representative error shape を docs に反映

---

### `docs/mcp-api.md` で追加・更新した内容
#### 1. HTTP action request example を追加
projection failure lifecycle の HTTP action route について、representative request example を追加しました。

追加した example 対象:
- `projection_failures_ignore`
- `projection_failures_resolve`

example で表現した内容:
- path ベースの HTTP contract
- query parameter での selector 指定
- bearer token を付ける representative 形

代表 query parameters:
- `workspace_id`
- `workflow_instance_id`
- `projection_type` (optional)

---

#### 2. HTTP success response example を追加
action route の representative success payload を docs に追加しました。

example に含めた主な fields:
- `workspace_id`
- `workflow_instance_id`
- `projection_type`
- `updated_failure_count`
- `status`

代表 example では:
- `status = "ignored"`
- `projection_type = "resume_json"`

を示しています。

---

#### 3. HTTP validation error example を追加
validation failure 時の representative error payload を docs に追加しました。

example で表現した内容:
- `error.code = "invalid_request"`
- invalid UUID に対する message
- `details.field` による field 指定

これにより docs 上で、
- success 時にどの shape が返るか
- validation failure 時にどの shape が返るか
を確認できる状態になりました。

---

#### 4. 既存の HTTP action contract 記述との整合を維持
今回の example 追加は、すでに docs へ反映済みだった以下の内容と整合する形で行っています。

整合対象:
- HTTP action routes
  - `projection_failures_ignore`
  - `projection_failures_resolve`
- query parameter contract
- `projection_type` optional validation
- HTTP error handling
  - `400` / `invalid_request`
  - `503` / `server_not_ready`
  - `404` / `not_found`
  - `500` / `server_error`
  - `401` auth error contract

---

#### `ctxledger/docs/CHANGELOG.md`
Unreleased changelog も更新し、今回の docs 具体化を反映しました。

反映した主な内容:
- HTTP runtime adapter registration の route list に
  - `projection_failures_ignore`
  - `projection_failures_resolve`
  を追加
- projection failure lifecycle の operator action docs について、
  future design 扱いではなく
  **implemented MCP / HTTP route surface**
  として記述
- `docs/mcp-api.md` に以下を追加したことをメモ
  - query-parameter request shape
  - representative request examples
  - representative success response example
  - representative validation error example

---

### 今回変更したファイル
- `ctxledger/docs/mcp-api.md`
- `ctxledger/docs/CHANGELOG.md`
- `ctxledger/last_session.md`

---

### 確認結果
今回確認できている範囲:
- `ctxledger/docs/mcp-api.md`: diagnostics 問題なし
- `ctxledger/docs/CHANGELOG.md`: diagnostics 問題なし

前回までに確認済みの状態:
- `ctxledger/src/ctxledger/server.py`: diagnostics 問題なし
- `ctxledger/tests/test_server.py`: diagnostics 問題なし
- `pytest -q tests/test_server.py`
  - `103 passed`

今回は docs 更新のみで、追加の test 実行は未実施です。

---

### git commit
- 今回の docs example / changelog 更新については、まだ git commit 未実施

---

### 補足
- `.gitignore` は引き続き変更対象に含めない前提
- この handoff は docs example 追加と changelog 更新まで含む状態に更新
- 実装コード自体の変更は今回行っていない

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
- HTTP request / success response / validation error example を追加済み
- `docs/CHANGELOG.md` に docs / route registration 反映を追加済み

---

### 次に自然な作業
次に自然なのは以下です。

1. 今回の docs example / changelog 更新を descriptive message で git commit する
2. 必要なら `docs/mcp-api.md` に auth disabled 時の request example も追加する
3. integration / service 層で HTTP-oriented coverage を広げる
4. deployment / security docs に action endpoints の運用上の注意を補足する