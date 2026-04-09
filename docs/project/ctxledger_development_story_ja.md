# ctxledger開発史 — 「last_session.md」から始まった durable な記憶装置へ

## はじめに

`ctxledger` の履歴を追っていくと、最初から完成された「文脈記憶システム」があったわけではないことがよく分かる。むしろ逆で、開発初期の `ctxledger` は、**セッションをまたいで作業を継続したい**、**AIエージェントの作業状態を失いたくない**、**ローカルのメモや一時ファイルに頼る運用を卒業したい**という切実な要求から、少しずつ形を得ていった。

その過程には、いかにも試行錯誤らしい痕跡が残っている。たとえば `last_session.md` のような handoff 用ファイル、`.agent/resume.json` や `.agent/resume.md` のようなローカル投影、projection failure の扱い、HTTP と MCP の境界の整理、observability の後付け、そして memory 機能の段階的な実装である。  
今の `ctxledger` は PostgreSQL を canonical system of record とし、workflow・memory・resume・file-work・interaction を durable に扱うが、そこに至るまでの道筋は一直線ではなかった。

この文書では、その履歴を単なる変更列挙ではなく、**「どういう困りごとから始まり、どこで方針転換し、どの時点から実用に耐えるようになったのか」**という物語として再構成する。技術的な節目は押さえつつ、開発の空気感が伝わるように書く。

---

## 1. 最初に用意されたもの — まずは「最低限動く durable workflow runtime」

開発の出発点でまず明確だったのは、`ctxledger` を単なるメモ帳ではなく、**durable workflow runtime** として成立させることだった。初期の `v0.1.0` 実装計画を見ると、目標はかなりはっきりしている。

- remote MCP server skeleton
- workflow control layer
- PostgreSQL-backed canonical state
- Docker-based local deployment
- memory features は後回し
- repository projection は non-canonical output

ここで重要なのは、最初から「canonical state は PostgreSQL に置く」という思想があったことだ。  
つまり、ローカルファイルは便利でも真実ではない。真実は DB にある。これは後の `ctxledger` を貫く最重要原則になる。

ただし、思想が最初からあったことと、実際にその思想だけで運用できたことは別だ。初期段階では、workflow を durable に保存する仕組みを作りつつも、**人間やエージェントが次のセッションで何を見ればよいか**という問題はまだ十分に解けていなかった。  
そこで登場したのが、後に「過渡期の装置」として振り返られることになるローカル projection と handoff メモ群だった。

---

## 2. `last_session.md` の時代 — durable state はあるが、再開の導線が弱い

履歴を辿ると、かなり早い段階から「session handoff」「continuation notes」「last session note」といった語が繰り返し現れる。これは偶然ではない。  
初期の `ctxledger` は、workflow を DB に保存できても、**次の作業者や次のエージェントが、その durable state をどう読めばよいか**がまだ弱かった。

そのギャップを埋めるために使われたのが、`last_session.md` のようなファイルだったと考えるのが自然だ。  
これは canonical state ではない。だが、実務上は非常に役に立つ。なぜなら、次のセッションで必要なのは必ずしも完全な DB 状態ではなく、

- 何をやっていたか
- どこまで終わったか
- 何が未解決か
- 次に何をすべきか

という、**人間にもエージェントにも読みやすい要約**だからだ。

この時期の `ctxledger` は、言ってみれば「DB に真実はあるが、真実への入り口がまだ不親切」な状態だった。  
だから `last_session.md` のような handoff ファイルが必要だった。これは設計の敗北ではなく、むしろ bootstrap 期の現実的な工夫だったと言える。

面白いのは、その後の履歴でも handoff note の更新が何度もコミットされていることだ。  
つまり、開発者自身が `ctxledger` を作りながら、まだ `ctxledger` だけでは自分の作業継続を十分に支えられず、**補助輪としてのローカルメモ**を使い続けていた。ここに、このプロジェクトの自己言及的な面白さがある。  
「文脈を失わないためのシステム」を作る過程で、文脈を失わないための暫定メモが必要だったのである。

---

## 3. `.agent/resume.json` と `.agent/resume.md` — canonical ではないが、実用的だった projection

`last_session.md` と並んで、初期から中期の `ctxledger` を象徴するのが `.agent/resume.json` と `.agent/resume.md` だ。  
これらは repository projection として設計されていた。つまり PostgreSQL にある canonical state を、ローカルリポジトリ内のファイルとして投影したものだ。

この設計には明確な利点があった。

- エージェントがローカルファイルとして簡単に読める
- 人間にも中身が分かりやすい
- Git 管理下の作業ディレクトリに近い場所に置ける
- 「今どの workflow を再開すべきか」を即座に見られる

特に、まだ MCP や HTTP の利用体験が十分に整っていない段階では、この projection はかなり実用的だったはずだ。  
durable state は DB にある。しかし、再開のために毎回 DB や API を直接叩くのは重い。ならば、derived artifact として `.agent/resume.*` を置けばよい。  
これは bootstrap 期の設計として非常に筋が良い。

ただし、この方式には最初から緊張関係があった。  
それは、**便利な derived artifact が、いつの間にか supported surface に見えてしまう**ことだ。

設計上は non-canonical でも、CLI があり、docs に書かれ、tests があり、Docker 例でも有効になっていると、利用者はそれを「正式な機能」と受け取る。  
履歴上、まさにそのことが起きた。projection writer は便利だったが、便利すぎたために、`ctxledger` の本来の思想――canonical truth は PostgreSQL にある――を曇らせ始めたのである。

---

## 4. v0.1.0 — 「最低限使える」状態に達した最初の節目

`v0.1.0` の計画と acceptance evidence を見ると、この時点で `ctxledger` はすでにかなり多くのものを持っていた。

- server startup
- PostgreSQL schema bootstrap
- workflow tools
- workflow resources
- Docker-based local deployment
- resume reconstruction after restart
- basic tests
- docs

つまり、**workflow runtime としての骨格**はこの時点で成立していた。  
特に重要なのは、`workspace_register`、`workflow_start`、`workflow_checkpoint`、`workflow_resume`、`workflow_complete` という基本ツール群が揃い、PostgreSQL-backed durability が確認されていたことだ。

この段階をどう評価するか。  
私は、「`ctxledger` が概念実証を超えて、最低限の実用品になった最初の瞬間」だと見る。

ただし、ここでの「使える」は、今の意味での「十分に使いやすい」とは違う。  
まだ memory は stub に近く、resume の UX は projection や handoff note に支えられており、HTTP/MCP surface も整理途上だった。  
それでも、**workflow を durable に保存し、再起動後に再構成できる**という一点だけで、すでに単なるメモ運用とは質が違っていた。

`ctxledger` が「ある程度利用可能」になった最初のラインをどこに引くかと問われれば、私はまずこの `v0.1.0` を挙げる。  
ただし、それは「基礎体力がついた」という意味であって、「運用が滑らかになった」という意味ではない。

---

## 5. HTTP-first への整理 — MCP server としての輪郭がはっきりする

初期履歴には stdio transport の痕跡も濃く残っているが、その後かなり大きな整理が入る。  
HTTP runtime builder の抽出、FastAPI 化、`/mcp` endpoint の整備、そして最終的な stdio removal である。

この流れは単なる transport の置き換えではない。  
`ctxledger` が「ローカルで何となく動くツール群」から、**remote MCP server として一貫した public surface を持つシステム**へ変わっていく過程だった。

履歴上も、

- MCP lifecycle scaffolding
- HTTP handler extraction
- resource response builders
- runtime introspection
- FastAPI MCP runtime smoke validation
- authenticated MCP smoke validation
- stdio removal

といったコミットが連続している。  
これは、開発の重心が「とにかく機能を足す」から「公開面を整える」へ移ったことを示している。

この時期の重要な変化は二つある。

### 5.1 public surface が明確になった

workflow tools や resources が、HTTP `/mcp` を通じてどう見えるかが整理された。  
これにより、`ctxledger` は内部実装の集合ではなく、**外から呼べる durable service** としての輪郭を得た。

### 5.2 debug / introspection が整った

`/debug/runtime`、`/debug/routes`、`/debug/tools` のような introspection surface は、単なるおまけではない。  
bootstrap 期のシステムにとって、「今何が expose されているか」「runtime がどう見えているか」を確認できることは極めて重要だ。  
これは、まだ fully polished ではないシステムを実運用に近づけるための、現実的な observability だった。

この段階で `ctxledger` は、少なくとも workflow runtime としては「人に説明できる形」になった。  
それは、利用可能性の第二の節目だった。

---

## 6. projection failure と lifecycle — 過渡期の複雑さが露出した時代

履歴を見ていて印象的なのは、projection failure lifecycle にかなりの労力が割かれていることだ。  
ignore、resolve、closed projection failures、HTTP action routes、docs、tests。かなり丁寧に作られている。

なぜここまで必要だったのか。  
答えは簡単で、projection が単なる補助ファイルではなく、**運用上それなりに重要な surface になっていた**からだ。

`.agent/resume.json` や `.agent/resume.md` を書く以上、

- 書けなかったらどうするか
- 失敗をどう記録するか
- 後で無視・解決できるか
- resume 時にどう見せるか

を考えなければならない。  
つまり、derived artifact を実用に供すると、その失敗管理まで必要になる。  
これは bootstrap 期の pragmatic design が、次第に maintenance cost を持ち始めたことを示している。

この時期の `ctxledger` は、ある意味で最も「悪戦苦闘」していた。  
canonical truth は DB にあるはずなのに、実際の運用では projection の成否も重要で、その failure lifecycle まで public surface に出てくる。  
設計思想と実務上の便利さがせめぎ合っていた時代だ。

だが、この複雑さは無駄ではなかった。  
後に projection を捨てるとき、何を捨て、何を残すべきかを判断する材料になったからだ。  
一度本気で運用したからこそ、「これは本当に canonical ではない」「ここは product surface から外すべきだ」と言えるようになった。

---

## 7. v0.4.0 observability — 「保存できる」から「見える」へ

workflow と persistence がある程度整うと、次に問題になるのは observability だ。  
DB に state があるだけでは足りない。運用者がそれを読めなければ、durable でも扱いづらい。

`0.4.0` observability milestone は、まさにその問題意識から生まれている。

- `ctxledger stats`
- `ctxledger workflows`
- `ctxledger memory-stats`
- `ctxledger failures`
- optional Grafana support

ここでの転換は大きい。  
`ctxledger` はこの頃から、「状態を保存するシステム」から「状態を観測できるシステム」へ進み始める。

これは地味だが重要な変化だ。  
durable system は、保存だけでは不十分で、**今どうなっているかを operator が把握できること**が必要になる。  
特に `ctxledger` のように workflow、memory、failure、embedding、graph など複数層を持つシステムでは、observability がないと運用はすぐブラックボックス化する。

この milestone は、後の memory や graph 機能の土台にもなった。  
なぜなら、複雑な機能を足す前に「見える化」を入れたことで、後の段階的な拡張が追跡可能になったからだ。

---

## 8. v0.5.0 と v0.5.1 — 機能追加より、構造整理と安定化へ

`0.5.0` は refactoring milestone として位置づけられている。  
これは、開発が一段落したからではなく、むしろ逆で、**機能が増えた結果、内部構造を整理しないと次に進めなくなった**からだろう。

- duplicated logic の削減
- module boundary の改善
- tests の整理
- helper extraction
- maintainability の向上

この時期のコミット群も、extract、cleanup、simplify、refactor が並ぶ。  
これは、`ctxledger` が「作りながら考える」段階から、「継続的に育てられる構造を作る」段階へ移ったことを示している。

さらに `0.5.1` では PostgreSQL pooling hardening や resume-path wiring fixes が入る。  
ここは見逃せない。  
durable system にとって、resume path が不安定なのは致命的だからだ。  
つまりこの頃には、resume はもはや将来機能ではなく、**実際に使われる前提の重要経路**になっていた。

このあたりから、`ctxledger` は「ある程度動く」だけでなく、「継続利用に耐える」方向へ明確に舵を切っている。

---

## 9. 大きな方針転換 — `.agent/` projection の廃止

`ctxledger` の歴史で最も象徴的な方針転換の一つが、`v0.5.3` と `v0.5.4` にかけて行われた **local `.agent/` projection の廃止** だ。

これは単なる cleanup ではない。  
初期から中期にかけて実用を支えた仕組みを、あえて product surface から外す決断だった。

### 9.1 なぜ projection を捨てたのか

理由は明快だ。

- local `.agent/` files が supported interface に見えてしまった
- canonical truth が PostgreSQL であるという原則を曇らせた
- projection failure lifecycle まで抱え込み、複雑さが増した
- resume は canonical APIs から読むべきだという方向が固まった

つまり、bootstrap 期には有効だった projection が、成熟期にはむしろ設計負債になり始めたのである。

### 9.2 何が変わったのか

`v0.5.3` では user-facing local `.agent/` projection access を deprecate。  
`v0.5.4` では projection remnants をさらに削除し、workflow・memory・MCP・HTTP の canonical surface に集中する方向へ進んだ。

これは、`ctxledger` がようやく補助輪を外した瞬間だった。  
`last_session.md` や `.agent/resume.*` に頼っていた時代から、**DB-backed canonical state と API surface だけで再開できるシステム**へ移行したのである。

この転換は、開発史の中でも特にドラマがある。  
なぜなら、かつて自分たちを助けた仕組みを、自分たちの手で退役させたからだ。  
便利だったものを捨てるには、代替が十分に育っていなければならない。  
projection 廃止は、`ctxledger` がその段階に達した証拠でもあった。

---

## 10. では、どの辺りから `ctxledger` は本当に「動くようになった」のか

この問いには、段階的に答えるのが正確だと思う。

### 10.1 最初に「使える」ようになったのは v0.1.0

workflow control、PostgreSQL durability、resume reconstruction、Docker local deployment が揃った。  
この時点で、少なくとも durable workflow runtime としての最小要件は満たしていた。

### 10.2 「人に見せられる形」で動くようになったのは HTTP/MCP 整備後

FastAPI ベースの `/mcp`、resources、debug surfaces、smoke validation が揃い、remote MCP server としての public surface が明確になった。  
ここで `ctxledger` は、内部実装の寄せ集めではなく、外部から利用できる service になった。

### 10.3 「補助輪なしで動く」ようになったのは v0.5.3〜v0.5.4 以降

`.agent/` projection を product surface から外せたということは、canonical APIs と runtime surface だけで resume / continue が成立する見込みが立ったということだ。  
この意味で、真に `ctxledger` らしい形で動くようになったのはこの頃だと言える。

### 10.4 「記憶装置として面白くなった」のは v0.6.0 以降

hierarchical memory、summary、AGE-backed derived graph、task recall、remember path、interaction memory、file-work memory。  
この辺りから `ctxledger` は単なる workflow ledger を超え、**durable memory system** として独自性を持ち始める。

---

## 11. v0.6.0 — hierarchical memory で「ただの workflow ledger」ではなくなる

`0.6.0` は、開発史の中で第二の創業期のようなものだ。  
それまでの `ctxledger` は主に workflow durability のシステムだった。  
しかし `0.6.0` で hierarchical memory が入ることで、プロジェクトの重心が変わる。

- canonical `memory_summaries`
- `memory_summary_memberships`
- summary-first retrieval
- grouped hierarchy-aware output
- AGE-backed auxiliary traversal
- explicit summary build path

ここで重要なのは、graph を導入しながらも canonical truth を relational PostgreSQL に置き続けたことだ。  
つまり、graph-first に飛びつかなかった。  
AGE は supporting graph layer であり、derived and degradable なものとして扱われる。  
この慎重さが `ctxledger` らしい。

`0.6.0` によって、`ctxledger` は「workflow を保存する」だけでなく、「過去の作業を階層的に思い出す」方向へ踏み出した。  
この時点で、初期の `last_session.md` 的な handoff の願いが、ようやくシステム内部に取り込まれ始めたとも言える。  
人間が手で書いていた要約や継続メモを、summary や grouped context として durable に扱う道が開けたからだ。

---

## 12. v0.7.0 と v0.8.0 — 「何を再開すべきか」をより賢くする

`0.7.0` task-recall milestone では、`memory_get_context` と `memory_search` が、単なる検索結果返却ではなく、**continuation selection** を説明できるようになっていく。

- latest considered workflow
- selected continuation target
- primary objective
- next intended action
- detour-like classification
- prior-mainline recovery
- latest-versus-selected comparison

これは、初期の `last_session.md` が担っていた役割を、より構造化された形でシステムが引き受け始めたことを意味する。  
「前回何をしていたか」だけでなく、「今どの thread に戻るべきか」まで説明できるようになった。

さらに `0.8.0` remember-path milestone では、記録の質そのものが問題化される。  
retrieval quality は recording quality の下流にある、という認識が明確になった。

- checkpoint-origin と completion-origin の区別
- grouped primary surface
- `primary_only`
- remember-path quality
- canonical summary volume
- derived graph posture metrics

ここで `ctxledger` は、単に「思い出す」だけでなく、「思い出せるように記録する」システムへ進化している。  
これは初期の bootstrap 期にはなかった視点だ。  
当初は durable state を残すだけで精一杯だったが、この頃には **どんな形で残せば後で役立つか** が主題になっている。

---

## 13. v0.9.0 — interaction と file-work が入り、AIエージェントの作業履歴が durable になる

`0.9.0` は、`ctxledger` が AIエージェント運用に本格的に寄っていく節目だ。

- interaction memory の自動 capture
- file-work metadata の durable capture
- failure reuse explanation
- grouped interaction-memory output
- operator-facing interaction/file-work observability

ここで初めて、エージェントの「何を触ったか」「どんなやり取りをしたか」が durable memory として扱われる。  
これは、初期の `last_session.md` や handoff note を、さらに一段抽象化して systematize したものだと言える。

昔は「次のセッションのために人間がメモを書く」必要があった。  
その後は workflow checkpoint や summary がそれを補い始めた。  
そして `0.9.0` では、interaction と file-work まで durable に残ることで、**作業の痕跡そのものが再開材料になる**。

この進化は非常に象徴的だ。  
`ctxledger` は最初、文脈を失わないための補助メモを必要としていた。  
しかし今では、補助メモに頼らずとも、interaction・workflow・memory・file-work の組み合わせから、かなりの文脈を再構成できるところまで来ている。

---

## 14. 開発史を貫く一本の線 — 「ローカル補助」から「canonical resumability」へ

ここまでの流れを一本の線でまとめると、`ctxledger` の開発史は次のように読める。

### 第1期: まず durable に保存したい
workflow state を PostgreSQL に保存し、再起動後も復元できるようにする。  
この時点では memory はまだ先で、resume UX は弱い。

### 第2期: 補助輪として handoff note と projection を使う
`last_session.md` や `.agent/resume.*` によって、次のセッションへの橋をかける。  
canonical truth は DB にあるが、実務上は derived artifact が重要になる。

### 第3期: public surface と observability を整える
HTTP/MCP、FastAPI、debug routes、stats、Grafana などを整え、外から使える durable service にする。

### 第4期: projection を捨て、canonical surface に寄せる
`.agent/` projection を deprecate / remove し、resume は canonical APIs と runtime surface から読む方針へ転換する。

### 第5期: memory を本格化する
summary、hierarchy、task recall、remember path、interaction memory、file-work memory を積み上げ、resume / continue を durable memory の問題として扱う。

この線を見ると、`ctxledger` は単に機能を増やしたのではなく、**「文脈継続の責任を、ローカル補助物から canonical system に移していった」**のだと分かる。  
これがこのプロジェクトの一番面白いところだと思う。

---

## 15. `last_session.md` は失敗の証拠ではなく、成功への足場だった

開発史を物語として読むとき、`last_session.md` や `.agent/resume.md` を「未熟さの証拠」とだけ見るのはもったいない。  
むしろそれらは、`ctxledger` が本当に解きたかった問題を最も率直に示している。

- セッションをまたいで継続したい
- 途中経過を失いたくない
- 次に何をすべきかを明確にしたい
- AIエージェントの作業を durable にしたい

これらの要求は、最初は手書きメモや derived file として現れた。  
その後、workflow checkpoint、resume resource、summary、task recall、interaction memory、file-work memory へと吸収されていった。

つまり `last_session.md` は、`ctxledger` が未完成だった証拠であると同時に、**何を完成させるべきかを教えてくれた設計入力**でもあった。  
過渡期の workaround が、後の product direction を形作ったのである。

---

## 16. 結論 — ctxledger は「自分で自分の必要性を証明しながら育った」

`ctxledger` の開発史を一言で言うなら、**自分で自分の必要性を証明しながら育ったシステム**だった。

最初は durable workflow runtime を作ろうとした。  
だが実際に使おうとすると、handoff note が必要になり、projection が必要になり、failure lifecycle が必要になり、observability が必要になり、summary が必要になり、task recall が必要になり、interaction と file-work の記録まで必要になった。

そのたびに、開発者は「本当に必要なもの」を一段ずつ system に取り込んでいった。  
その結果、今の `ctxledger` は単なる workflow DB ではなく、

- workflow progress の canonical record
- resumability の durable substrate
- memory の relational-first system
- derived graph を伴う hierarchical recall layer
- AIエージェントの interaction / file-work を含む operational memory

を持つシステムになった。

そして振り返ると、`last_session.md` のような素朴なファイルに残っていた願い――  
**「次の自分が困らないようにしたい」**  
**「次のエージェントが迷わないようにしたい」**  
――こそが、`ctxledger` 全体の原点だったように見える。

今の `ctxledger` は、その願いをローカルメモではなく canonical state と durable memory で実現しようとしている。  
開発史の面白さは、そこにある。