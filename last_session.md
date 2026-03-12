今回の変更
#### HTTP surface contract cleanup
closed projection failure history を含む HTTP surface の concrete contract 整理を進め、runtime/debug examples との整合性を見直しました。

主な対象:
- `workflow_resume` HTTP read surface
- closed projection failure history 用 HTTP read surface
- `/debug/runtime`
- `/debug/routes`
- `/debug/tools`
- startup summary に出る runtime route list

---

#### `ctxledger/src/ctxledger/server.py`
前段の修正で、HTTP runtime adapter の route registration は次で揃っています。

- `runtime_introspection`
- `runtime_routes`
- `runtime_tools`
- `workflow_resume`
- `workflow_closed_projection_failures`

また、closed projection failures 用 handler の invalid path 時 message は次で統一済みです。

- `closed projection failures endpoint requires /workflow-resume/{workflow_instance_id}/closed-projection-failures`

dedicated endpoint path は引き続き次です。

- `/workflow-resume/{workflow_instance_id}/closed-projection-failures`

---

#### `ctxledger/docs/mcp-api.md`
HTTP surface contract cleanup の一環として、operational status / debug endpoint の example route list を実装に合わせて更新しました。

更新意図:
- `health()` example の HTTP routes を実装に一致させる
- `readiness()` example の HTTP routes を実装に一致させる
- `/debug/runtime` example の routes を実装に一致させる
- `/debug/routes` example の routes を実装に一致させる

反映対象の route:
- `workflow_closed_projection_failures`

これで `docs/mcp-api.md` 内では、少なくとも次の 2 系統が揃っています。

1. dedicated HTTP read surface
   - `/workflow-resume/{workflow_instance_id}/closed-projection-failures`
2. debug / runtime introspection examples 上の registered route name
   - `workflow_closed_projection_failures`

---

#### docs 全体の現在の整合
少なくとも次の docs は、新しい dedicated HTTP surface に追従済みの状態です。

- `ctxledger/README.md`
- `ctxledger/docs/mcp-api.md`
- `ctxledger/docs/architecture.md`
- `ctxledger/docs/specification.md`
- `ctxledger/docs/CHANGELOG.md`

主な反映内容:
- dedicated endpoint の明記
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
- runtime/debug examples における route 名
  - `workflow_closed_projection_failures`

---

### 現在の状態
closed projection failure history まわりは、少なくとも次の観点で揃っている想定です。

- server 実装の route registration
- dedicated endpoint path
- invalid path error message
- docs 上の HTTP surface contract
- runtime/debug examples
- startup summary example

history 専用 surface は次で読める前提です。

- `/workflow-resume/{workflow_instance_id}/closed-projection-failures`

---

### 補足
`.gitignore` は保守対象外として扱う前提です。  
この handoff でも `.gitignore` は作業対象に含めません。

---

### 次に自然な作業
次に自然なのは、別の surface や未完了機能に進むことです。例えば:

1. 他の HTTP surface の concrete contract を docs と実装で横並び確認
2. projection failure lifecycle の operator action surface 設計
3. debug / deployment / security docs の最終整理
4. workflow / memory 系の未完成 surface 実装へ進む

この closed projection failure history の dedicated HTTP surface については、いったん完了扱いで次の作業へ進める状態です。