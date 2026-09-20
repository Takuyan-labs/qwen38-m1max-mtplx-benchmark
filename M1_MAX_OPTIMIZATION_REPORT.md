# M1 Max Qwen3.8-27B 最速構成 改良可能性検証レポート

調査日: 2026-09-21
Hardware: Apple M1 Max、32-core GPU、64GB unified memory
Model: `Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed-FP16`
Pinned revision: `c984b2932d29676a6dabb6431b27da7ca2411508`
Target artifact fingerprint: `sha256:069c2de291fd15b130383119b13f60c45e0f78481a180cf51887ae87c3986b12`

## 1. 結論

今回の検証で、fresh code generationの39.90 tok/sを更新する変更は確認できなかった。

* 2.9.2、2.10.2、2.11.3のruntime更新だけでは、同一artifactの小規模A/Bで+3%採用基準を満たさなかった。
* 最新2.11.3のfresh Python code、512 tokens、D3-only、n=5は中央値36.610 tok/s、平均36.631 tok/s、最大36.833 tok/sだった。出力SHAは5回で一致した。
* 同じ2.11.3を再測定すると中央値38.932 tok/s、平均38.949 tok/s、最大39.034 tok/sまで回復した。前回との差から、runtime版だけでなく熱状態・測定時状態の影響が大きい。
* 2.11.3の128-token depth sweepでは、Python・英語・日本語ともD3が最速だった。中国語はD3が最速だったが、D1/D2とARの出力SHAが一致せず、速度改善として採用しない。
* 内部時間ではtarget verifyが最大で、最新D3 n=5でもverify約83%、draft約14%、残り約2–3%。最初に触るべきはdraftではなくverify/target forwardである。
* ExpectedValue adaptive policyは、3回とも実効D3のままで中央値34.921 tok/s。固定D3の128-tokenスクリーニング中央値36.741 tok/sより約5%遅く、不採用。
* Rewrite/Edit専用ではstock Context Copyが有効だった。ONは43.871 tok/s中央値、OFFは38.232 tok/s中央値で、約14.8%向上。ONでは10 copy rounds、128 accepted copy tokens、出力correctnessを確認した。これはfresh codeの39.90とは別競技である。
* stock MTPLX 2.11.3にRAMP実装は見つからなかったため、独自再実装は行わず保留した。
* `MTPLX_PROJ_REQUANT=q4`（対象は主に上位MLPのq8→q4）ではD3 36.83 tok/s前後だったが、baselineとgreedy出力SHAが変わり、受理率も低下したため不採用。

### 現時点の推奨設定

**Fresh codeの再現性重視:**

`Optimized-Speed-FP16`（固定revision） + MTPLX 2.9.0 turbo + native MTP D3 + serial/solo + cache bypass + greedy。既知の最高値は短期D3最大39.897 tok/s。2.11.3の再測定は中央値38.932で、旧中央値と同等だが旧最大値は更新していない。

**Rewrite/Editの実用速度:**

MTPLX 2.11.3 + native MTP D3 + stock Context Copy ON。ただしContext Copyの43.87 tok/sは既存コード再出力prompt専用で、fresh生成の速度として掲示しない。

**最も再現性の高い公開値:**

AR/D3交互5回の既存formal中央値（AR 13.89、D3 29.16 tok/s）を主値とし、短期D3-only中央値38.91・最大39.90はburst値として併記する。

## 2. Baseline

既存公開測定の主条件は、single-stream、batch 1、512 final tokens、temperature 0、top-p 1、top-k 1、seed 123、thinking off、prefix/cache bypass、MTPLX 2.9.0、MTP D3である。

| 指標 | 既存公開値 |
|---|---:|
| AR/D3交互5回 AR中央値 | 13.892 tok/s |
| AR/D3交互5回 D3中央値 | 29.160 tok/s |
| Python content-mix D3中央値 | 33.05 tok/s |
| 1024-token追加測定 | 35.061 tok/s（n=1） |
| 短期D3-only中央値 | 38.909 tok/s（n=5） |
| 短期D3-only最大 | 39.897 tok/s |
| Python D3 draft acceptance | 93.55% |

短期値と交互反復値は持続条件が異なるため、単一の「通常速度」にまとめない。

今回再測定した2.9.0 formal512は、別のruntimeプロセスが同時に存在した時間帯と熱状態が重なり、AR 14.62→7.58、D3 35.60→16.80 tok/sまで単調低下した。このrunは熱・メモリ競合の診断資料として保存し、runtime順位のbaselineには採用しない。

## 3. Runtime version比較

### 3.1 128-token pilot

同一model revision、同一Python prompt、greedy、cache bypass、AR/D3各2回。2.10.2/2.11.3は依存関係を分離したuv環境で実行した。

| MTPLX | MLX | Transformers | AR median | D3 median | 判定 |
|---|---|---|---:|---:|---|
| 2.9.2 | 0.32.1 | 5.9系 | 14.600 | 37.408 | pilotのみ、+3%採用判定は不可 |
| 2.10.2 | 0.32.2 | 5.9系 | 14.624 | 37.584 | 2.9.2比+0.47%、実質同等 |
| 2.11.3 | 0.32.2 | 5.12.1 | 14.350 | 36.647 | 2.10.2比約-2.5%、不採用 |

2.9.2以降は`MTPLX_BATCH_TARGET_ARRAYS=0`、`MTPLX_LAZY_TARGET_DISTRIBUTIONS=1`を標準にする設計変更がある。2.9.0のhealthで見えた`BATCH_TARGET_ARRAYS=1`とは異なるため、version番号だけでなく実効runtime pathを記録した。2.11.3はM1/M4でNAX設定が有効でも、health上は`capacity_below_threshold`でNAXを使用していなかった。

### 3.2 2.9.2 formal512

2.9.2のformal512はD3中央値35.145 tok/s、最大36.837 tok/sだったが、D3に24.302、ARに7.903という外れ値が含まれ、CVはD3 15.4%、AR 21.9%だった。速度差の結論をこの1回のn=5だけで出さず、pilotと併記する。

### 3.3 最新2.11.3 fresh code n=5（初回）

条件: 512 tokens、D3-only、prompt 29 tokens、cache bypass、依存関係を満たしたisolated uv環境。

| run | server decode tok/s | draft s | verify s | target forward s |
|---:|---:|---:|---:|---:|
| 1 | 36.552 | 2.029 | 11.652 | 12.002 |
| 2 | 36.833 | 2.002 | 11.589 | 11.954 |
| 3 | 36.610 | 2.000 | 11.640 | 11.988 |
| 4 | 36.517 | 2.021 | 11.639 | 11.986 |
| 5 | 36.645 | 1.993 | 11.642 | 11.992 |
| **median** | **36.610** |  |  |  |
| mean | 36.631 |  |  |  |
| min–max | 36.517–36.833 |  |  |  |

全runで135 verify calls、403 drafted、377 accepted、15 rejected、119 bonus、compiled verify fallback 0、出力SHA一致。旧2.9.0 burst中央値38.909、最大39.897は更新しなかった。

**回答1: 2.9.0から最新版へ更新するだけで速くなるか。**
常に速くなるとは言えない。初回2.11.3は36.610 tok/sだったが、同条件の再測定では38.932 tok/sまで上がった。2.11.3は旧2.9.0中央値と同等になり得る一方、旧最大39.897 tok/sを安定して超える証拠はまだない。

### 3.4 最新2.11.3 fresh code n=5（再測定）

条件は3.3と同じ。別の推論サーバーを停止し、同一artifact・同一prompt・512 tokens・D3・cache bypassで再実行した。

| 指標 | 値 |
|---|---:|
| median | 38.932 tok/s |
| mean | 38.949 tok/s |
| min–max | 38.849–39.034 tok/s |
| sample stddev | 0.073 tok/s |
| CV | 0.188% |

5回とも135 verify calls、403 drafted、377 accepted、15 rejected、119 bonus、compiled verify fallback 0、出力SHA一致。2.9.0 burst中央値38.909比+0.06%、最大39.897比-2.42%。生データは[`fresh-code-d3-2.11.3-rerun-512.json`](results/optimization-20260921/fresh-code-d3-2.11.3-rerun-512.json)。

## 4. Profiling結果

### 4.1 D3内部時間

最新2.11.3 n=5の代表値から、`decode_elapsed = generated / decode_tok_s`で比率を計算した。serverが返していない値は推定せず、保存値だけを使っている。

* final tokens / verify call: `512 / 135 = 3.7926`
* draft time: 約14.3%（約2.00 s）
* verify time: 約83.2%（約11.64 s）
* その他: 約2.5%前後
* target forward: 約11.99 s
* compiled verify calls: 135
* compiled verify fallback: 0
* peak memory: 21.43 GB前後（このrunのhealth/report値）

過去の2.9.0 burstでもverify 82.44%、draft 15.36%、その他2.20%で、同じ結論だった。

**回答2: 最も時間を使うのはどこか。**
target verify（特にtarget forward）が支配的。draftは約14–15%なので、draftだけを軽くしても伸び幅には上限がある。

### 4.2 記録したフィールド

`benchmark.py`、`benchmark_content_mix.py`、depth sweepは、以下をruntimeが返す範囲で保存するよう拡張した。

`generated_tokens`、decode/request時間、decode tok/s、verify calls、drafted/accepted/rejected、depth別受理、draft/verify/target forward/verify eval、accept/commit/capture/repair/bonus/snapshot/rollback、Context Copy counters、compiled calls/fallback、active/peak memory、output SHA-256。存在しない値は`null`で、他の時間から推定しない。

GPU/CPU同期の独立した名前付き時間はMTPLXの公開statsに存在しないため、`取得不可`として扱った。

## 5. D1/D2/D3比較

最新版2.11.3、128-token screening、各内容×各depth n=5。512-token正式ベンチの置換ではなく、depth傾向を調べるための追加測定である。

| 内容 | AR | D1 | D2 | D3 | 受理率の代表値 | correctness |
|---|---:|---:|---:|---:|---:|---|
| 日本語 | 14.375 | 18.110 | 16.104 | **20.388** | D3 43.2% | SHA一致 |
| 英語 | 14.325 | 18.953 | 16.932 | **22.214** | D3 49.7% | SHA一致 |
| 中国語 | 14.262 | 18.709 | 16.247 | **21.435** | D3 44.5% | **SHA不一致** |
| Python | 14.377 | 21.962 | 23.257 | **36.741** | D3 94.0% | SHA一致 |

ChineseではAR/D3とD1/D2のSHAが分かれた。従って「D3が速度最速」という観測は残すが、correctness条件を満たさないため採用深度は決めない。中国語については512-token n=5の再試験が必要である。

**回答3: PythonコードでD3は本当に最適か。**
今回のdepth screeningではD3が明確に最速で、SHAも一致。PythonではD3を維持する。

**回答4: 日本語・英語・中国語もD3が最適か。**
速度だけなら今回のscreeningでは3言語ともD3。ただし中国語はSHA不一致のため、correctness込みでは未確定。日本語・英語はD3を候補にできるが、長い512-token反復での確認が望ましい。

## 6. Adaptive policy

MTPLX 2.11.3の`--adaptive-policy expected_value`を、固定D3と同じPython promptで比較した。

* n=3、128 tokens、greedy、cache bypass
* 3回とも実効depthは3
* verify calls 34、drafted100、accepted94、SHAは固定D3と一致
* adaptive median: **34.921 tok/s**
* 同じスクリーニングの固定D3中央値: **36.741 tok/s**
* 差: adaptiveが約5%遅い

MTPLX sourceではadaptive policyまたはmargin gateを有効にすると、`device_d2/device_core`のcompiled/device fast path eligibilityから外れる。従って、単なる判断オーバーヘッドだけでなく実行経路が変わる。

**回答5: Adaptive depthは固定D3より速いか。**
今回のPython実測では遅い。複雑化に見合う3%改善がなく、不採用。

## 7. Context Copy

### 7.1 Workload

fresh codeとは別に、既存Pythonファイルをpromptに埋め込み、「完全再出力し、関数名を1箇所変更する」Rewrite/Edit promptを作った。Context Copy ON/OFF以外は同じserver条件で、各3回、256 max tokens。

### 7.2 結果

| 条件 | median decode | Context Copy rounds | accepted copy tokens | 出力SHA |
|---|---:|---:|---:|---|
| ON（stock default） | **43.871 tok/s** | 10 | 128 | 全run一致 |
| OFF（`MTPLX_CONTEXT_COPY=0`） | 38.232 tok/s | 0 | 0 | 全run一致 |

改善率は`43.871 / 38.232 - 1 = 14.8%`。両条件とも`sum_two`への変更を確認し、古い`add(2, 3)` callは残らなかった。

**回答6: Context Copyは実際のコード編集で有効か。**
はい。今回のRewrite/Editでは10%以上改善し、correctnessも維持した。fresh codeでは既存のD3 burstでprobeはあってもround/accepted tokenは0だったため、fresh速度とは分離する。

## 8. RAMP

stock MTPLX 2.11.3 packageを検索したが、Context Copy RAMP実装、`ramp.py`、RAMP用CLI/PR識別子は確認できなかった。見つかった`ramp`はfan ramp、RoPE/YaRN、GDNなど別機能だった。

**回答7: RAMPをM1 Maxで使う価値はあるか。**
今回のstock構成では実装がないため未検証。Context Copyが有効になったRewrite/Editでも、まずstock ONが14.8%改善しているので、外部実装を導入する前に互換性とcorrectnessを確認すべき。独自再実装は今回の範囲外。

## 9. Mixed quantization探索

安全な候補として、artifactの8-bit保持領域のうちMTPLXが対象にする上位MLP projectionを`MTPLX_PROJ_REQUANT=q4`で再量子化した。embedding、lm_head、linear_attn.out_proj、expert bank、MTP sidecarは変更していない。

2.11.3、128-token Python prompt、AR/D3各2回。

| 条件 | AR median | D3 median | D3 acceptance | 出力SHA |
|---|---:|---:|---:|---|
| baseline clean 2.11.3 pilot | 14.350 | 36.647 | 94/100 | `145634…` |
| `PROJ_REQUANT=q4` | 15.084 | 36.830 | 93/102 | `9aa477…` |

ARだけは約5%速くなったが、D3は約0.5%で採用基準未達。さらにgreedy output SHAがbaseline artifactと変わった。AR/D3間のSHAは一致していたが、元モデルとの品質同一性を確認できないため不採用とした。

MTP sidecarはすでにINT4/group64/prequantizedであり、CLIでbitsだけを変更するのは安全な高品質比較にならない。新しいMTP sidecarの再量子化・品質試験なしに深追いしない。

**回答8: Optimized-Speed-FP16からmixed quantをさらに攻める価値はあるか。**
現状は低い。小規模候補はARだけ改善したが、D3が+3%未満でSHAも変わった。今後行うなら上位MLPを1領域ずつ、AR/D3/acceptance/品質を同時に測る。3–5候補で一貫改善がなければ停止する。

## 10. 不採用になった案と理由

| 案 | 結果 | 理由 |
|---|---|---|
| MTPLX最新版へ更新 | 不採用 | 2.9.2/2.10.2はpilotで実質同等、2.11.3はやや遅い。+3%未達 |
| Adaptive ExpectedValue | 不採用 | 実効D3のまま、固定D3より約5%遅い |
| 中国語のD3採用 | 保留 | 速度は最速だがSHA不一致 |
| RAMP | 保留 | stock実装なし。独自実装は範囲外 |
| q8→q4 projection requant | 不採用 | D3 +0.5%程度、baseline SHA変更、受理率低下 |
| MTP head bit変更 | 不実施 | prequantized INT4 sidecarで、単純変更が正当なA/Bにならない |
| Splash/DFlash/Metal移植 | 不実施 | M1非対応またはkernel全面改造であり、今回の停止条件に該当 |

## 11. Metalで触るならどこか

実装は行わず、profilingから候補だけを残す。

1. **MTP verifyのtarget forward**: decodeの約83%、約12秒/512 tokensを占める。
2. **verify forward内のquantized matmul/attention**: compiled verify fallback 0でも支配的なので、M1のtile、memory traffic、GQA/paged attentionの実効経路をprofileする価値がある。
3. **verify eval/commit**: 約1.2秒規模で、target forwardより小さいが、同期とlogits materializationを確認する。

ただし、M5/NAX専用経路をM1へ強制する、M4をM8へpaddingする、scratch/barrierを追加する、といった変更は性能保証がなく、今回の測定から実装に進む根拠はない。次の作業はMetal改造ではなく、M1でのGPU traceとkernel別時間の取得である。

## 12. 現時点の最速設定

### Fresh code generation

* Artifact: pinned `Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed-FP16`
* Runtime: MTPLX 2.9.0 turbo（既存公開burst条件）
* MTP: native D3
* scheduler: serial / solo
* cache: prefix/session bypass
* sampling: greedy (`temperature=0`, `top_p=1`, `top_k=1`, seed123)
* fan: default（変更なし）
* 代表値: D3-only中央値38.909、最大39.897 tok/s

### Rewrite/Edit

* Runtime: MTPLX 2.11.3 + MLX 0.32.2
* Native MTP D3
* stock Context Copy ON
* 代表値: 256-token rewrite promptで43.871 tok/s中央値

この43.871は既存コードの再出力を含むため、39.897との順位比較に使わない。

**回答9: 39.90 tok/sを再現または更新できるか。**
最新版2.11.3の再測定では中央値38.932、最大39.034 tok/sまで出たが、旧2.9.0の最大39.897は更新していない。旧最大値は引き続きburst記録として扱う。

**回答10: 新しい最高値の条件は何か。**
今回の新しい最高値43.871はfresh codeではなく、Context Copyを使ったRewrite/Edit workload。cache reuseの単純なfresh測定でもなく、既存コードを逐語再出力するcopy proposalを含む。fresh generationの最高値は39.897のまま。

## 13. 生データと再現スクリプト

* Runtime pilot: [`results/runtime-pilots-2026-09-21.jsonl`](results/runtime-pilots-2026-09-21.jsonl)、[`results/runtime-pilots-2026-09-21.md`](results/runtime-pilots-2026-09-21.md)
* 2.9.0 formal/診断: [`results/optimization-20260921/runtime-2.9.0/formal512a/`](results/optimization-20260921/runtime-2.9.0/formal512a/)
* 2.9.2 formal: [`results/optimization-20260921/runtime-2.9.2/formal512/`](results/optimization-20260921/runtime-2.9.2/formal512/)
* 最新depth sweep: [`results/optimization-20260921/depth-sweep-2.11.3-128b/`](results/optimization-20260921/depth-sweep-2.11.3-128b/)
* 最新fresh D3 n=5: [`results/optimization-20260921/fresh-code-d3-2.11.3-512.json`](results/optimization-20260921/fresh-code-d3-2.11.3-512.json)
* Adaptive: [`results/optimization-20260921/adaptive-expected-value-2.11.3-128.json`](results/optimization-20260921/adaptive-expected-value-2.11.3-128.json)
* Context Copy ON/OFF: [`results/optimization-20260921/context-copy/`](results/optimization-20260921/context-copy/)
* Mixed quant: [`results/optimization-20260921/mixed-quant-proj-requant-q4-2.11.3-128.json`](results/optimization-20260921/mixed-quant-proj-requant-q4-2.11.3-128.json)
* Depth sweep harness: [`scripts/benchmark_content_depths.py`](scripts/benchmark_content_depths.py)
* Context Copy harness: [`scripts/benchmark_context_copy.py`](scripts/benchmark_context_copy.py)

## 14. 最終判断

M1 Maxのこのartifactでは、fresh codeの追加高速化余地は残っているが、今回の安全な高水準A/Bで3%以上の改善を再現できる変更は見つからなかった。既存のOptimized-Speed-FP16 + native MTP D3は、受理率が高いPythonコードではすでに良いbit allocationとruntime経路にあり、次の大きな改善はmixed quantの小変更ではなく、M1向けverify kernelのprofileと設計になる可能性が高い。

一方、実際のCoding Agent用途に近いRewrite/EditではContext Copyが明確に効いた。速度記録を一つに混ぜず、fresh生成、rewrite、copy利用、cache利用を別ベンチとして公開するのが、現時点で最も実用的な改善である。
