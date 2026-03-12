今回の変更
#### dispatch-level invalid path coverage for HTTP projection failure action routes
projection failure lifecycle の HTTP action surface について、**runtime dispatch level での invalid path -> `404 not_found` coverage** を追加しました。

今回の方針:
- これまでの handler-level invalid path coverage に加えて、HTTP runtime dispatch 経由でも same contract を明示的に固定する
- `projection_failures_ignore` / `projection_failures_resolve` について、registered route に対して wrong path を渡したときの behavior を tests で直接担保する
- implementation / handler contract / runtime dispatch surface / docs の整合をさらに強める

---

### `ctxledger/tests/test_server.py` で追加した内容
#### 1. ignore action route の dispatch-level invalid path coverage を追加
追加した test:
- `test_http_projection_failures_ignore_route_returns_not_found_for_invalid_path()`

確認した内容:
- `runtime.dispatch("projection_failures_ignore", "/not_projection_failures_ignore?...")` が `404` を返すこと
- payload が expected `not_found` contract になること
- `content-type` header が維持されること

代表 assertion:
- `status_code == 404`
- `error.code == "not_found"`
- `projection failure ignore endpoint requires /projection_failures_ignore`

---

#### 2. resolve action route の dispatch-level invalid path coverage を追加
追加した test:
- `test_http_projection_failures_resolve_route_returns_not_found_for_invalid_path()`

確認した内容:
- `runtime.dispatch("projection_failures_resolve", "/not_projection_failures_resolve?...")` が `404` を返すこと
- payload が expected `not_found` contract になること
- `content-type` header が維持されること

代表 assertion:
- `status_code == 404`
- `error.code == "not_found"`
- `projection failure resolve endpoint requires /projection_failures_resolve`

---

### 今回の変更で追加で固定された contract
今回の追加により、projection failure lifecycle の HTTP mutation surface は少なくとも以下を dispatch-level でも明示的に固定しています。

#### ignore
- auth enforcement
- success payload
- validation failure
- invalid path -> `404 not_found`
- server-not-ready

#### resolve
- auth enforcement
- success payload
- validation failure
- invalid path -> `404 not_found`
- server-not-ready

これにより、mutation-side HTTP surface は
- handler 直呼び
- runtime dispatch
の両レベルで invalid path handling が明示的に固定された状態になりました。

---

### 今回変更したファイル
- `ctxledger/tests/test_server.py`
- `ctxledger/last_session.md`

---

### 確認結果
今回確認できている範囲:
- `ctxledger/tests/test_server.py`: diagnostics 問題なし
- `pytest -q tests/test_server.py`
  - `127 passed`

直前までに確認済みの状態:
- `ctxledger/src/ctxledger/server.py`: diagnostics 問題なし
- `ctxledger/docs/mcp-api.md`: diagnostics 問題なし
- `ctxledger/docs/SECURITY.md`: diagnostics 問題なし
- `ctxledger/docs/deployment.md`: diagnostics 問題なし
- `ctxledger/docs/CHANGELOG.md`: diagnostics 問題なし

---

### git 状態メモ
- 直前の commit:
  - `c44ae90 Add HTTP action route proxy example`
- この handoff 更新時点では、今回の dispatch-level invalid path coverage 追加について **まだ git commit 未実施**
- `.gitignore` は引き続き変更対象に含めない前提

---

### 補足
- 今回は production code の追加変更はなし
- 既存 implementation の strict path validation を、runtime dispatch level でも明示的に tests で固定した
- public HTTP mutation contract について、少なくとも
  - implementation
  - handler-level tests
  - dispatch-level tests
  - MCP API docs
  - security docs
  - deployment docs
  - changelog
 でかなり明示的に整合している状態

---

### 現在の状態
projection failure lifecycle の public surface は、少なくとも以下が docs / tests / implementation 上で整合しています。

#### read-side
- `workflow_resume`
- `/workflow-resume/{workflow_instance_id}/closed-projection-failures`

#### mutation-side (MCP / stdio)
- `projection_failures_ignore`
- `projection_failures_resolve`

#### mutation-side (HTTP runtime route surface)
- `projection_failures_ignore`
- `projection_failures_resolve`

#### mutation-side (HTTP handler contract)
- valid path shape required for:
  - `/projection_failures_ignore`
  - `/projection_failures_resolve`
- invalid path shape returns `404 not_found`
- validation failures return `400 invalid_request`
- unmapped service failures fall through to `500 server_error`

#### mutation-side (HTTP dispatch-level contract)
- `runtime.dispatch(...)` through `projection_failures_ignore` / `projection_failures_resolve` also preserves:
  - invalid path -> `404 not_found`
  - expected `content-type`
  - expected route-specific `not_found` message

#### docs
- `docs/mcp-api.md`
  - auth enabled / disabled request examples を反映済み
  - success / validation error examples を反映済み
  - strict path requirement を反映済み
- `docs/SECURITY.md`
  - HTTP action route cautions を反映済み
  - strict path guidance を反映済み
  - proxy/gateway exact path alignment guidance を反映済み
  - observability guidance を反映済み
- `docs/deployment.md`
  - HTTP action routes の deployment guidance を反映済み
  - strict path handling を反映済み
  - reverse-proxy exact path expectations を反映済み
  - request logging guidance を反映済み
  - representative reverse proxy example を反映済み
- `docs/CHANGELOG.md`
  - strict path validation / docs alignment を反映済み

#### tests
- `tests/test_server.py`
  - HTTP action route の auth / validation / success / server-not-ready を coverage 済み
  - HTTP action handler の success / validation edge cases / service error mapping を coverage 済み
  - HTTP action handler の invalid path -> `404 not_found` を coverage 済み
  - HTTP action route dispatch の invalid path -> `404 not_found` を coverage 済み

---

### 次に自然な作業
次に自然なのは以下です。

1. 今回の dispatch-level invalid path coverage 追加を descriptive message で git commit する
2. 必要なら `docs/SECURITY.md` に representative edge logging example を追加する
3. action route の observability guidance を `docs/mcp-api.md` / `docs/CHANGELOG.md` に軽く波及させる
4. 必要なら projection failure action routes の response examples に `404 not_found` example も追加する