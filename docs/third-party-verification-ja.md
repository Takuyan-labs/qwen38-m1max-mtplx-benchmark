# M1 Max 64GBにおけるQwen3.8-27B高速推論記録

## 第三者検証レポート

調査日: 2026-09-21
対象: Apple M1 Max（32-core GPU / 64GB unified memory）、Qwen3.8-27B Dense、single-stream decode
対象記録: `Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed-FP16` + MTPLX 2.9.0 + native MTP D3

## 1. 調査結果の要約

結論を先に述べると、今回確認した範囲では次のように評価するのが最も正確です。

* 対象リポジトリの短いコード課題では、MTP D3の中央値38.909 tok/s、最大39.897 tok/s（表示上39.90）が、条件・ログ・出力同一性つきで記録されている。
* 同じM1 Max 32-core / 64GBを明示した外部の再現可能なMTPLX測定では、短いコード課題の29.7–32.0 tok/sが確認できる。対象記録はこれを上回る。
* Redditには「M1 Max 64GB、FP16、MTPLXでup to 42 decode」という自己申告がある。しかしprompt、context、output長、反復数、warmup、runtime版、batch、測定ログがなく、第三者が再現できる記録ではない。
* したがって「39.90を超える公開言及はない」とは言えない。一方、「39.90を超える、条件が検証可能なM1 Max 27B single-stream記録が確認できた」とも言えない。
* 公開上の安全な表現は、**「今回調査した再現可能な公開記録では最高クラス。M1 Max 64GBの42 tok/s自己申告はあるが、証跡不足のため順位には入れない」**である。「世界最速」は証明できない。
* 高速度の主因は、M1 Maxの通常AR性能が特別に高いことではない。ARは約13.89–14.32 tok/sで、MTP D3が同じgreedy出力を保ったまま約2.10倍（反復中央値）になった。主因はMTPLXの検証経路、D3、コードでの高いdraft受理率、MTP head、混合量子化の組み合わせである。

このレポートでは、確認済みの測定、外部の自己申告、比較不能な数値を分離する。推定で空欄を埋めない。

## 2. 39.90 tok/sを超える記録の有無

### 2.1 条件が検証可能な公開記録

今回確認した一次情報・再現可能なベンチマーク・詳細な実機報告の中に、次の条件を同時に満たして39.90 tok/sを超える記録は確認できなかった。

* M1 Max（原則32-core GPU、64GB）
* 約27BのDenseモデル
* batch 1 / single-stream
* final output tokenを分子にしたdecode/TG
* MTP/speculativeの有無と条件が明記されている
* ハードウェア、prompt、context、出力長、反復または統計が確認できる

最も近い詳細な外部測定は、同じM1 Max 64GBでMTPLX 2.10.0を使った記事の29.7 tok/s（merge intervals）と32.0 tok/s（two sum）である。こちらはprompt、output長、cache、batch、runtime、モデルが記載されており、比較可能性が高いが、39.90には届かない。

### 2.2 39.90を超える自己申告

Redditの `r/LocalLLM` スレッドには、次の短いコメントがある。

> “M1 Max 64GB fp16 version ... up to 42 decode, 140 prefill with mtplx.”

これは対象機種とMTPLXを示すため、探索上は重要である。ただし、以下が欠落している。

* 使用モデルの正確なrevision/artifact
* prompt内容、prompt token数、context長
* output token数、stop条件
* batchと同時実行数
* `decode`がserver TGかclient wall-clockか
* MTP depth、acceptance、verification回数
* warmup、測定回数、平均/中央値/最大の別
* raw logや再現コマンド

よってこれは**「42 tok/sという公開言及」**としては記録するが、**「検証済みの42 tok/sベンチマーク」**として対象39.90を上回る証拠にはしない。

## 3. M1 Max 27B公開ベンチ比較表

`TG/decode`と`PP/prefill`を分離した。`不明`は元ページに記載がなかった項目であり、推定値ではない。

| Hardware | Model | Runtime | Quant | Workload | Context | Output | Batch | MTP | tok/s | Statistic | Evidence |
|---|---|---|---|---|---:|---:|---:|---|---:|---|---|
| M1 Max 32c / 64GB | Qwen3.8-27B optimized FP16 | MTPLX 2.9.0 | body INT4 g32 + selected INT8 g64 + FP16 | 固定Pythonコード | 29 tokens | 512 final | 1 | native D3 | 38.909 | 中央値、n=5、D3-only | 本リポジトリのraw JSON/README |
| M1 Max 32c / 64GB | 同上 | MTPLX 2.9.0 | 同上 | 固定Pythonコード | 29 tokens | 512 final | 1 | native D3 | 39.897 | 最大、n=5系列 | 本リポジトリのraw JSON/README |
| M1 Max 32c / 64GB | 同上 | MTPLX 2.9.0 | 同上 | 固定Pythonコード | 29 tokens | 512 final | 1 | native D3 | 29.160 | 交互5回中央値 | 本リポジトリのformal run |
| M1 Max 32c / 64GB | 同上 | MTPLX 2.9.0 | 同上 | Python生成（内容mix） | 100前後 | 512 final | 1 | native D3 | 33.05 | 中央値、n=5 | 本リポジトリのcontent-mix |
| M1 Max 32c / 64GB | 同上 | MTPLX 2.9.0 | 同上 | 日本語自由文 | 100前後 | 512 final | 1 | native D3 | 18.67 | 中央値、n=5 | 本リポジトリのcontent-mix |
| M1 Max 32c / 64GB | 同上 | MTPLX 2.9.0 | 同上 | 英語自由文 | 100前後 | 512 final | 1 | native D3 | 22.28 | 中央値、n=5 | 本リポジトリのcontent-mix |
| M1 Max 32c / 64GB | 同上 | MTPLX 2.9.0 | 同上 | 中国語自由文 | 100前後 | 512 final | 1 | native D3 | 19.43 | 中央値、n=5 | 本リポジトリのcontent-mix |
| M1 Max 32c / 64GB | 同上 | MTPLX 2.9.0 | 同上 | 固定コード、1024出力 | 42 tokens | 1024 | 1 | native D3 | 35.061 | 1回、decode | 本リポジトリ、n=1 |
| M1 Max 32c / 64GB | 同上 | MTPLX 2.9.0 | 同上 | 通常greedy AR | 29 tokens | 512 | 1 | なし | 13.892 | 交互5回中央値 | 本リポジトリのformal run |
| M1 Max 32c / 64GB | Qwen3.8-27B FP16 artifact | MTPLX 2.10.0 | FP16 artifact | `merge_intervals`コード | 49 tokens | 190 | 1 | MTP3 | 29.7 | 外部実機報告、単発系 | DubuWorld記事 |
| M1 Max 32c / 64GB | 同上 | MTPLX 2.10.0 | FP16 artifact | `two_sum`コード | 不明 | 64 | 1 | MTP3 | 32.0 | 外部実機報告、単発系 | DubuWorld記事 |
| M1 Max 32c / 64GB | 同上 | MTPLX 2.10.0 | FP16 artifact | 英文/自然文 | 不明 | 314 | 1 | MTP3 | 19.4 | 外部実機報告 | DubuWorld記事 |
| M1 Max 32c / 64GB | Qwen3.8-27B-4bit | oMLX 0.6.3rc2 | 4-bit | Python/code、DFlash2 | 1k/8k/16k/32k | 不明 | 1 | 外部DFlash、oMLX MTP off | 19.8/24.3/25.1/23.5 | TG、context別 | oMLX benchmark |
| M1 Max 32c / 32GB | Qwen3.8-27B-oQ4e-fp16-mtp | oMLX 0.6.0 | oQ4e + FP16 | code mixed | 1k/4k/8k/16k | 不明 | 1 | Lightning MTP | 23.5/27.8/18.2/22.8 | TG、context別 | oMLX benchmark |
| M1 Max 32c / 64GB | Qwen3.8-27B-Uncensored-MLX | oMLX 0.5.7 | 4-bit | code mixed | 1k/8k | 不明 | 1 | off | 15.0/13.6 | TG | oMLX benchmark |
| M1 Max 32c / 64GB | Qwen3.8-27B Q4 | MTPLX | Q4 | 長文context | 262k | 不明 | 不明 | 不明 | 約21 | 自己申告、平均等不明 | Reddit |
| M1 Max 32c / 64GB | Qwen3.8-27B FP16 | MTPLX | FP16 | 不明 | 不明 | 不明 | 不明 | 不明 | “up to 42” | 自己申告、条件不明 | Reddit |
| M5 Max | Qwen3.8-27B BF16 parent | MTPLX | BF16 | coding | 不明 | 不明 | 不明 | MTP | 58.7 | upstream model card、機種違い | Hugging Face |
| M4 Pro 48GB | Qwen3.8-27B 4-bit | mlx-dspark | 4-bit | code/chat/math | 不明 | 不明 | 不明 | DSpark/DFlash2 | 29.5/33.8 | 3-trial mean、機種違い | mlx-dspark README |
| Mac（機種不明） | Qwen3.8-27B | MTPLX + session bank | 不明 | “bare speed”/session bank | 不明 | 不明 | 不明 | 不明 | 175 | 記事の主張、指標不明 | WiselyChen記事 |

表の上位3行は同一リポジトリ内の別統計であり、独立した機種間比較ではない。`39.897`は短いD3-onlyの最大値、`29.160`は数分間の交互反復中央値で、用途と持続性が異なる。

## 4. 各benchmarkのprompt/workload

### 対象リポジトリ

* Formal prompt: 「有効なPythonコードのみを出力し、merge sort、binary search、決定的なunit testを実装せよ」。29 tokens。
* Content mixのPython: 定型的なアルゴリズムとテストを生成させるコード課題。
* 日本語: 量子化、メモリ帯域、speculative decodingを扱う長い日本語散文。見出し、箇条書き、数式、コードを要求しない。
* 英語: 900語以上相当の説明文。
* 中国語: 1800字以上相当の説明文。
* すべて固定長512 final tokens、temperature 0、top-p 1、top-k 1、seed固定、thinking off、prefix cache bypass、batch 1。

この設計の利点は、AR/D1/D2/D3の生成列をSHA-256で一致確認できること、draft tokenを分子に入れていないこと、内容差を比較できることである。一方、コードpromptは完全なrepository editingやagent taskではなく、固定長のdecode microbenchmarkである。また、出力は`finish_reason=length`で切れているため、コードの完成率・テスト通過率・自律タスク成功率を意味しない。

### DubuWorldの外部測定

一行JSON形式の短いコードneedleを使い、`merge_intervals`、`two_sum`、自然文を同一機種で測っている。cache 0、同一出力token数で比較している点は有用だが、反復数と分散が対象リポジトリほど詳細ではない。長文では41kで13.85、82kで8.50 tok/s、131kはOOMと報告されており、短文の約30 tok/sを長文へ外挿できない。

### oMLX benchmark

oMLXはcontext長ごとのTG/PPを分けて表示する。Python/code系でも、DFlash2やLightning MTPを使うか、oMLXの`mtp_enabled`がoffかで経路が異なる。1kのTGと32kのTGは同じ意味ではなく、PPの100–200 tok/sをdecode速度として扱ってはいけない。

### 外部のMTP研究例

`mlx-dspark`のREADMEはM4 Pro 48GBで3試行平均を掲載しているが、M1 Maxではない。KyndのM1 Max報告では、別engineでMTP graft/DFlashを試すとbaselineより遅くなった。これは対象MTPLX記録を否定するものではなく、MTPの効果がモデル、draft、verify kernel、context、実装の組み合わせに依存することを示す。

## 5. MTP acceptanceと速度の関係

対象リポジトリの代表的な512-token D3 runでは、MTPLXログに次がある。

* target verification: 135回
* drafted tokens: 403
* accepted drafts: 377
* rejected drafts: 15
* bonus tokens: 119
* compiled verification fallback: 0
* depth別受理確率: D1 96.30%、D2 95.52%、D3 88.81%

`512 / 135 = 3.79`は、1回のverification cycleで最終的に確定したtoken数の平均に近い。ただし、これはbonus tokenを含むtarget-produced outputの会計であり、accepted draftsへbonusを単純加算してよいという意味ではない。D3の理論depthが3だから速度も3倍、という計算にはならない。draft生成、block verify、accept処理、KV/history管理のコストがあるからである。

内容別D3中央値と受理率は次の通り。

| 内容 | D3中央値 | D3受理率 | verification calls |
|---|---:|---:|---:|
| Pythonコード | 33.05 tok/s | 93.55% | 135 |
| 英語 | 22.28 tok/s | 54.84% | 194 |
| 中国語 | 19.43 tok/s | 40.87% | 230 |
| 日本語 | 18.67 tok/s | 41.00% | 229 |

この実験内では、コードの高い受理率と少ないverification回数が速度差と整合する。しかし、これは4 promptの比較であり、言語一般の性質を証明するものではない。tokenizer、定型性、短い識別子や括弧の継続、promptの長さも影響する。

MTPの正しさについては、AR、D1、D2、D3のgreedy出力SHA-256が一致し、各方式が512 final tokensを返した。従って、少なくともこの固定条件ではdraft tokenを水増しした記録ではない。sampling時の一般的なexact speculationまで、このリポジトリのhash試験が証明するわけではない。

## 6. Optimized-Speed-FP16の量子化構成

### 6.1 公開artifactで確認できる構成

HFのconfig、`mtplx_runtime`、MTP sidecarのsafetensors headerを照合した。対象artifactは普通の一様Q4ではない。

* 本体の基本量子化: affine INT4、group size 32。
* 8-bit g64 override: `embed_tokens`、`lm_head`。
* 8-bit g64 override: 48層の`linear_attn.out_proj`。
* 8-bit g64 override: 層56–63のMLP `gate_proj`、`up_proj`、`down_proj`。
* 上記以外のbodyは原則4-bit g32。
* M1/M2向けFP16 siblingでは、量子化weightはparentとbyte-identicalのまま、残りのfloating tensorをBF16からFP16へ変換する。scales、biases、norms、GDNの畳み込み/状態パラメータ、MTP head周辺が含まれる。
* MTP sidecarは現行artifact headerでpacked matrixがU32（INT4 pack）、scales/biases/normがF16。MTP headのquantization recipeはINT4、group size 64、affine、prequantized。
* MTPは1 hidden layerのdraft headで、runtimeのdefault/max depthは3。

したがって分類は、**「精度と速度の妥協を取ったmixed quantization + MTP sidecar + M1/M2向け浮動小数点cast」**である。単にモデル容量を小さくしただけのQ4ではなく、壊れやすい/帯域負荷の大きい部分を8-bitまたはFP16に残している。ただし、公開recipeに「M1 Maxの受理率を最大化するために学習した」と書かれているわけではない。MTP headは構造契約とflat-or-better acceptanceの検証を経て公開されたが、個別Mac用に再学習した証拠はない。

### 6.2 upstreamと本リポジトリの境界

混合量子化、M1/M2 FP16 artifact、MTP head、MTPLX runtimeはYoussof Altoukhi/MTPLX側の成果である。本リポジトリが行ったのは、artifactを再配布せず、M1 Max上の起動条件、cache bypass、greedy parity、AR/D1/D2/D3 ablation、内容mix、raw JSONL、再現スクリプト、第三者向け監査を公開したことだ。今回の記録を「Takuyan-labsがQ4 recipeを発明した」と表現してはいけない。

計測時のモデルrevisionは`model.lock.json`の`c984b2932d29676a6dabb6431b27da7ca2411508`、artifact fingerprintは`sha256:069c2de291fd15b130383119b13f60c45e0f78481a180cf51887ae87c3986b12`で固定されている。HFの現在のHEADは後から更新されているため、追試ではHEADをそのまま使わず、このrevisionとfingerprintを検証する。

## 7. 通常AR性能とMTPLX version差

### 7.1 AR性能

対象機では、同一prompt/同一512 tokenの通常ARは13.89 tok/s（formal中央値）、別ablationでは14.32 tok/s前後だった。これはM1 Max 27B Denseの通常decodeとして外部のMLX/oMLX報告（おおむね13–20 tok/s）から大きく外れない。したがって、39.90はM1 MaxのARが突然40 tok/sになった値ではなく、MTPによってverification回数を圧縮したfinal-output throughputである。

### 7.2 リリースの読み方

MTPLXのrelease notesから確認できる範囲は次の通り。

| Version | 公開情報 | M1 Maxへの含意 |
|---|---|---|
| 2.9.0 | decodeが通常+15–20%、コード系で最大+60%という一般的な主張 | 今回の測定版。Turbo flagの一部が実 runtimeではdeadだったと後版で注意される |
| 2.9.1 | long-context crash、出力cap、Turbo profileの実効性を修正/明確化し、2.9.0の再測定を要請 | 2.9.0の39.90を現行値へ直接外挿できない |
| 2.9.2 | 12k未満のchained greedy draftingを既定化、forge/norm、quantize:false、context copy/allocatorの修正。M5 A/Bで+2.5–9.8% | M1 Maxの同条件A/B値は未公開 |
| 2.10.0 | 3k/88k/147k等のdecode・prefill改善を掲載 | 掲載値はM5 MaxでありM1への速度保証ではない |
| 2.10.1 | M5向けlong-prefill改善 | M1 Maxのdecode比較には使えない |
| 2.11.1 | M5専用tensor-unit flash verify route | M1–M4で誤って有効化された問題が後に判明 |
| 2.11.2 | 2.11.1のM1–M4誤経路をhardware-gate。M1–M4は2.10.2 packed-GQA verify pathへ戻す | 正しさの修正。M1の速度向上値は提示されていない |
| 2.11.3 | 最新。token-id exactness等、correctness-firstの修正。主な速度値はM5/Flash Next | 現行での再測定候補だが、2.9.0比のM1 A/Bは必要 |

したがって「2.9.0には性能バグがあり、更新すればM1で必ず50 tok/sになる」という事実はない。2.9.1のTurbo flag注意と2.11.2のM1–M4 correctness fixは、再測定する理由にはなるが、速度上昇を保証しない。最新版での数値は、2.9.0の記録を置き換えるのではなく、別のversion条件として報告する。

### 7.3 公式の45 tok/s前後という記述

artifact側の`mtplx_runtime`には、generic arm64/macOSでgreedy 19.6、D1 29.5、D2 38.8、D3 45.4前後というspeed evidenceがある。しかし、これはM1 Maxの型番・GPU core・メモリを示した測定ではない。モデルカードもM1/M2の数値は未公開と明記し、掲載される58.7 tok/sはM5 MaxのBF16 parent coding taskである。

従って、45 tok/sを「M1 Maxで公式に測定された値」とは扱えない。「M1/M2向けFP16 artifactである」ことと、「M1 Maxで45 tok/sを実測した」ことは別である。

## 8. 疑わしい、または比較不能な高速値

### “42 tok/s” Reddit

対象機種が近いが条件不足。ランキングには入れず、再現依頼の候補として保存する。

### “175 tok/s” Mac Qwen3.8-27B

中国語記事の「bare speed model + session bank」で175 tok/sという記述は、機種、prompt、context、batch、cold/warm、最終token基準が不明である。`session bank`やキャッシュ済みセッションのburst throughputである可能性を排除できず、single-stream decodeの比較表で速度記録としない。

### 53 tok/sなどのbatch値

batch 4の合計53 tok/sはsingle-stream 53 tok/sではない。1リクエストあたりのTGへ換算できない限り、今回の比較対象にしない。

### 100–900 tok/sのprefill値

PP/prefillはpromptを並列処理する速度であり、生成中のdecode/TGではない。M1 Max 27Bのprefill 80–200 tok/sという報告は、今回の39.90に対する反証にも証明にもならない。

### M4/M5または別モデル

M5 MaxのQwen3.8-27B 58.7、M4 ProのDFlash2 33.8、Qwen3.6-35B-A3Bの55などは、ハードウェアまたはモデル構造が異なる。参考情報としては有用だが、M1 Max 27B Denseの順位には入れない。

## 9. Takuyan-labs測定の位置づけ

### 強い点

* M1 Max 32-core / 64GB、OS、runtime、Python、MLX関連versionを固定している。
* モデルrevisionとartifact fingerprintを固定している。
* single-stream、batch 1、cache bypass、temperature 0、top-p/top-k固定、seed固定。
* AR/D1/D2/D3の出力SHA-256が一致し、draft tokenを速度の分子に入れていない。
* short maximumだけでなく、AR/D3交互5回中央値、content mix、1024 token補助測定を公開している。
* server decode rateとclient end-to-end rateを分けている。

### 限界

* 39.897は短いD3-only burstであり、数分間の主要値は29.160 tok/s。単発最大値を通常の期待速度として書けない。
* promptは固定コード中心で、agent benchmark、repository編集、長いツールループ、unit test実行時間を含まない。
* 1024 tokenはn=1、formal promptと入力長が異なる。
* M1 Maxの全世界記録を探索し尽くしたことは証明できない。42 tok/s自己申告も残る。
* exact target weightsは現在の作業ツリーにないため、quantized tensorそのものをローカル再読込したのではなく、計測lockとHF公開metadataを照合した。再配布モデルの同一性はfingerprintで担保する。

### 推奨する表現

> M1 Max 32-core GPU / 64GBで、Qwen3.8-27BのMTP D3 final-output decodeを短い固定コード課題で最大39.90 tok/s、D3-only中央値38.91 tok/sとして再現した。交互5回の持続的な中央値は29.16 tok/s、通常ARは13.89 tok/sだった。今回確認した再現可能な公開記録では最高クラスだが、世界最速は証明していない。

## 10. 再測定するなら推奨する条件

1. **runtimeを二本立てにする。** MTPLX 2.9.0を再現用に残し、最新版2.11.3を別条件で測る。モデルrevision、runtime commit、依存lockをそれぞれ保存する。
2. **短期と持続を分ける。** 512 token D3-only n=10以上、AR/D3交互 n=10以上、1024/2048/4096 tokenを各n=5以上測る。中央値、IQR、最小、最大を出す。
3. **promptを固定しつつ複数化する。** 既存の固定Python、自然な日本語/英語/中国語に加え、長い既存コードrewrite、AST編集、repository-style issue、tool-call JSONを別suiteにする。
4. **MTP内部値を保存する。** depth、acceptance、accepted token数、bonus、rejected、verification calls、fallback、draft時間、verify時間、accept処理時間をJSONLへ書く。
5. **指標を分離する。** server decode、client final-output、end-to-end、TTFT、prefill、PPを別列にする。PPはTGに混ぜない。
6. **電力・温度・throttleを同時に記録する。** sustained dropが熱、電力、unified-memory pressure、allocatorのどれによるかを切り分ける。
7. **出力同一性を維持する。** ARとMTPでSHA-256を比較し、samplingを使う場合はseed、sampler、token-id exactnessを明記する。
8. **第三者追試用に公開する。** `system.json`、`model.lock.json`、`environment.lock.json`、prompt、raw JSONL、実行command、commit SHA、計測日時を同梱する。
9. **42 tok/s報告を追試する。** Reddit投稿者にmodel path、MTPLX版、depth、prompt、output長、n、raw logの提示を依頼し、同じベンチスクリプトで測る。

## 11. 出典URL

### 一次情報

* 対象ベンチマーク: <https://github.com/Takuyan-labs/qwen38-m1max-mtplx-benchmark>
* 対象FP16 artifact/model card: <https://huggingface.co/Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed-FP16>
* MTPLX README: <https://github.com/youssofal/MTPLX/blob/main/README.md>
* MTPLX releases: <https://github.com/youssofal/MTPLX/releases>
* MTPLX v2.9.0: <https://github.com/youssofal/MTPLX/releases/tag/v2.9.0>
* MTPLX v2.9.1: <https://github.com/youssofal/MTPLX/releases/tag/v2.9.1>
* MTPLX v2.9.2: <https://github.com/youssofal/MTPLX/releases/tag/v2.9.2>
* MTPLX v2.10.0: <https://github.com/youssofal/MTPLX/releases/tag/v2.10.0>
* MTPLX v2.11.2: <https://github.com/youssofal/MTPLX/releases/tag/v2.11.2>
* MTPLX v2.11.3: <https://github.com/youssofal/MTPLX/releases/tag/v2.11.3>
* oMLX benchmark一覧: <https://omlx.ai/benchmarks/performance>
* oMLX M1 Max 64GB Qwen3.8 benchmark: <https://omlx.ai/benchmarks/performance/s4s92tx7>
* oMLX Qwen3.8 oQ4e MTP benchmark: <https://omlx.ai/benchmarks/performance/p04sc5lz>
* mlx-dspark: <https://github.com/ARahim3/mlx-dspark/blob/main/README.md>
* MTPLXとoMLXのM1 Max外部測定: <https://tech.dubuworld.com/en/posts/m1-max-qwen38-27b-mtplx-vs-omlx-2026-08-30/>
* M1 Mac向けMTP検証: <https://www.kyndcode.com/blog/speed-up-qwen-on-m1-mac/>

### コミュニティ・比較不能値

* M1 Max 64GB “up to 42 decode”自己申告: <https://www.reddit.com/r/LocalLLM/comments/1vv2tw5/people_running_qwen_38_27b_on_apple_silicon_whats/>
* M1 Max Qwen3.8/35B-A3B長文自己申告: <https://www.reddit.com/r/LocalLLaMA/comments/1w1ejqy/>
* Macで175 tok/sという条件不明の記述: <https://ai-coding.wiselychen.com/qwen-3-8-27b-all-platform-deployment-guide/>

## 12. 最終判定

### ① 公開最高記録か

「39.90を超える公開言及」は存在する（Redditの42 tok/s）。しかし、その条件は第三者検証に必要な情報を欠く。「M1 Max 32GPU / 64GB / 約27B Dense / single-stream decode」で、39.90を超える**信頼できる再現可能な公開記録**は、今回の調査では確認できなかった。

### ② 再現性のある速度としてどの程度か

短い固定コードでは非常に高い。38.91 tok/s中央値、39.90 tok/s最大は、同一機種の詳細な外部MTPLX報告29.7–32.0 tok/sを上回る。一方、交互反復中央値29.16 tok/s、内容mixの日本語18.67・英語22.28・中国語19.43を併記すべきであり、39.90を「このMacの常時速度」としてはならない。

### ③ 魔改造の効果か

定性的な寄与は次の順で説明するのが妥当である。

1. **MTP D3 + MTPLX verify kernel**: 27B本体の逐次呼び出し回数を減らし、最終tokenをまとめて確定する。
2. **コードpromptの高いdraft受理率**: 93.55%受理、135 verification callsが速度を押し上げる。
3. **混合量子化**: bodyをINT4にしつつ、embed/lm_head、linear-attention out_proj、後段MLPなどをINT8 g64に残し、品質/帯域/実装のバランスを取る。
4. **M1/M2向けFP16浮動小数点**: scale、bias、norm、GDN状態、MTP周辺のBF16→FP16 castでApple Silicon上の実行経路に合わせる。
5. **M1 Maxのハードウェア**: これらを実行する土台だが、ARが14 tok/s前後であるため、40 tok/sの主因とは言えない。

この寄与を個別に加算した因果分解は未実施であり、数値として「FP16が何 tok/s、MTP headが何 tok/s」とは断定できない。

### ④ 「最速」と表現できるか

「世界最速」は不可。公開範囲と検索方法で世界全体を証明できず、42 tok/sの未検証自己申告もある。次の表現なら証拠に対応している。

> **今回調査した再現可能な公開M1 Max 27B single-stream decode記録では最高クラス。短い固定コードのMTP D3で38.91 tok/s中央値、39.90 tok/s最大を再現した。**

これは速度記録の価値を過小評価しない一方、batch、prefill、別SoC、別モデル、単発peak、未検証の自己申告を混ぜない表現である。
