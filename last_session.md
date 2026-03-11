進めました。今回は **実際に `.agent/resume.json` / `.agent/resume.md` を書く projection writer** まで入れました。

## 追加したもの

### 新規モジュール
- `src/ctxledger/projection/writer.py`
- `src/ctxledger/projection/__init__.py`

### できるようになったこと
- `WorkflowService.resume_workflow()` の結果から
  - `.agent/resume.json`
  - `.agent/resume.md`
  を workspace 配下へ生成
- projection 出力先が **workspace root の外へ出ない** ことを検証
- writer が `RecordProjectionStateInput` を返せるので、
  呼び出し側でそのまま `service.record_resume_projection(...)` に流せる

## 今回の実装の範囲
入れたのはまず安全な最小単位です。

- ファイル生成
- JSON/Markdown の整形
- パストラバーサル防止
- projection metadata 更新用 input の生成

まだ今回**未着手**なのは以下です。

- `projection_failures` への durable failure 記録
- 失敗時の `ProjectionStatus.FAILED` 自動反映
- CLI の実運用レベル統合
- server 起動後フックでの自動 projection write

## テスト結果
全体で通っています。

```/dev/null/test-output.txt#L1-1
78 passed in 7.79s
```

## 意味
これで今の状態はこうです。

- canonical workflow state は PostgreSQL
- projection state metadata は DB に保存可能
- resume projection ファイルそのものも生成可能
- workspace 外への unsafe write は防止
- unit / integration とも green

## 次にやるべき本命
次は **failure tracking を本当に canonical にする** ところです。  
つまり projection writer を次の形に進化させるのが自然です。

1. projection write 成功
   - `projection_states` を `fresh` に更新
2. projection write 失敗
   - `projection_failures` に記録
   - `projection_states` を `failed` に更新
3. 既存 open failure の解決/再試行ポリシー整理

ここまで行くと、README にある
- projection diagnostics
- stale / failed / missing
- durable failure tracking

がかなり実体化します。

必要ならこのまま次に、**`projection_failures` write-path と failed 状態遷移** まで進めます。
