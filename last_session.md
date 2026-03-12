今回の変更
#### `ctxledger/docs/mcp-api.md`
projection failure lifecycle の operator action surface について、実装状態に合わせて docs を更新しました。

主な反映内容:
- `projection_failures_ignore`
- `projection_failures_resolve`

を「future examples」ではなく、**implemented MCP tools** として明記しました。

---

#### docs に反映した内容
`workflow_resume` セクション配下の projection failure lifecycle 関連説明を更新し、少なくとも以下を明文化しました。

- implemented MCP tools:
  - `projection_failures_ignore`
  - `projection_failures_resolve`
- implemented response contents:
  - `workspace_id`
  - `workflow_instance_id`
  - `projection_type`
  - `updated_failure_count`
  - `status`
- implemented response statuses:
  - `ignored`
  - `resolved`
- implemented validation / error handling:
  - `workspace_id` の required UUID validation
  - `workflow_instance_id` の required UUID validation
  - optional `projection_type` validation
  - `server_not_ready`
  - representative MCP error mapping:
    - `not_found`
    - `invalid_request`
    - `server_error`

また、`/debug/tools` の representative response shape にも以下を追加しました。

- `projection_failures_ignore`
- `projection_failures_resolve`

さらに、`Initial v0.1.0 Contract Summary` では、両 tool を `Allowed Stub Surface` から分離し、`Implemented Optional Surface` として整理しました。

---

### diagnostics 確認
今回確認した範囲では、少なくとも次は clean でした。

- `ctxledger/tests/test_server.py`: diagnostics 問題なし
- `ctxledger/docs/mcp-api.md`: diagnostics 問題なし

このため、前回 handoff にあった `tests/test_server.py` の古い unused import warning は、現時点の状態では再現していません。

---

### 現在の状態
projection failure lifecycle まわりは、少なくとも次の public surface が揃っています。

#### read-side
- `workflow_resume`
- `/workflow-resume/{workflow_instance_id}/closed-projection-failures`

#### mutation-side
- `projection_failures_ignore`
- `projection_failures_resolve`

また、stdio runtime の registered tool surface は少なくとも次を含む状態です。

- `resume_workflow`
- `projection_failures_ignore`
- `projection_failures_resolve`
- `memory_remember_episode`
- `memory_search`
- `memory_get_context`

---

### 補足
- `.gitignore` は引き続き保守対象外前提
- 今回は docs 更新のみで、コード実装自体の追加変更はしていません
- 今回の作業では `last_session.md` の更新と git commit は未実施のまま残っています

---

### 次に自然な作業
次に自然なのは以下です。

1. `last_session.md` を今回の docs 反映内容ベースで継続更新する
2. 必要なら HTTP action endpoint 版を追加する
3. service / integration tests 側へ projection failure lifecycle の public surface coverage を広げる
4. 作業ループ完了として descriptive message で git commit する