今回の変更
#### deployment / security docs cleanup
closed projection failure history を含む HTTP surface の concrete contract 整理の流れで、deployment / security docs 側の debug surface 説明も揃えました。

主な対象:
- `ctxledger/docs/deployment.md`
- `ctxledger/docs/SECURITY.md`

---

#### `ctxledger/docs/deployment.md`
`/debug/*` の exposure policy 説明に、runtime/debug surfaces から見える representative HTTP route names を追記しました。

追加・整理した主な内容:
- current debug surfaces
  - `/debug/runtime`
  - `/debug/routes`
  - `/debug/tools`
- representative HTTP route names exposed by these debug surfaces
  - `runtime_introspection`
  - `runtime_routes`
  - `runtime_tools`
  - `workflow_resume`
  - `workflow_closed_projection_failures`
- `/debug/*` payloads が reveal しうる registered HTTP routes の具体例
  - `runtime_introspection`
  - `runtime_routes`
  - `runtime_tools`
  - `workflow_resume`
  - `workflow_closed_projection_failures`

意図:
- deployment doc 上でも、runtime/debug examples や server 実装と同じ route vocabulary を使う
- `/debug/*` が operationally sensitive である理由を、抽象論だけでなく concrete route 名でも説明する

---

#### `ctxledger/docs/SECURITY.md`
security doc 側にも同様に、`/debug/*` が expose しうる representative HTTP route names を追記しました。

追加・整理した主な内容:
- representative HTTP route names exposed by debug surfaces
  - `runtime_introspection`
  - `runtime_routes`
  - `runtime_tools`
  - `workflow_resume`
  - `workflow_closed_projection_failures`
- registered HTTP routes の具体例として
  - `runtime_introspection`
  - `runtime_routes`
  - `runtime_tools`
  - `workflow_resume`
  - `workflow_closed_projection_failures`
  を明記

意図:
- security doc 上でも、`/debug/*` の observability exposure を具体的に理解できるようにする
- route 名の記述を README / MCP API / deployment / security の間で揃える

---

#### docs 全体の現在の整合
少なくとも次の docs は、新しい dedicated HTTP surface と runtime/debug route naming に追従している状態です。

- `ctxledger/README.md`
- `ctxledger/docs/mcp-api.md`
- `ctxledger/docs/architecture.md`
- `ctxledger/docs/specification.md`
- `ctxledger/docs/deployment.md`
- `ctxledger/docs/SECURITY.md`
- `ctxledger/docs/CHANGELOG.md`

主な整合ポイント:
- dedicated endpoint path
  - `/workflow-resume/{workflow_instance_id}/closed-projection-failures`
- representative payload
  - `workflow_instance_id`
  - `closed_projection_failures`
- closed failure record fields
  - `projection_type`
  - `target_path`
  - `attempt_id`
  - `error_code`
  - `error_message`
  - `occurred_at`
  - `resolved_at`
  - `open_failure_count`
  - `retry_count`
  - `status`
- runtime/debug examples や exposure docs における route 名
  - `workflow_closed_projection_failures`

---

### 現在の状態
closed projection failure history の dedicated HTTP read surface については、少なくとも次の観点で一通り揃っている想定です。

- server 実装
- route registration
- README
- MCP API docs
- architecture docs
- specification docs
- deployment docs
- security docs
- changelog
- tests
- diagnostics

特に、history 専用 surface は次で読める前提で docs / 実装 / tests が揃っています。

- `/workflow-resume/{workflow_instance_id}/closed-projection-failures`

また、runtime/debug surfaces 上の route 名は次で揃っています。

- `runtime_introspection`
- `runtime_routes`
- `runtime_tools`
- `workflow_resume`
- `workflow_closed_projection_failures`

---

### 補足
- `.gitignore` は保守対象外として扱う前提
- この handoff でも `.gitignore` は作業対象に含めない

---

### 次に自然な作業
次に自然なのは、別の surface や未完了機能に進むことです。例えば:

1. 他の HTTP surface の concrete contract を docs と実装で横並び確認
2. projection failure lifecycle の operator action surface 設計
3. workflow / memory 系の未完成 surface 実装へ進む
4. deployment / security / debug endpoint 周辺の残りの表現統一を続ける

この closed projection failure history の dedicated HTTP surface については、いったん完了扱いで次の作業へ進める状態です。