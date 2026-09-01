# M1 MaxでQwen3.8-27Bを交互連続測定で2.10倍へ――MTP D3の瞬間値と反復値を分けて測った

## 結論

Apple M1 Max（32-core GPU、64 GB unified memory）上で、Qwen3.8-27BをMTPLX 2.9.0のMTP depth 3で実行した。短いD3単独系列では最大39.90 tok/s、中央値38.91 tok/sを観測した。一方、ARとD3を交互に各5回、数分間連続で測ったFormal runでは、AR中央値13.89 tok/s、D3中央値29.16 tok/s、高速化率2.10倍だった。

性能はランの進行とともに低下した。これは持続負荷や温度の影響と整合するが、温度・消費電力を計測していないため原因は断定しない。本記事では、見栄えのよい瞬間値と、数分間の連続反復値を別の指標として公開する。ここでいう連続反復測定は、長文1本の耐久試験ではない。

重要なのは、この数字が並列リクエストの合計Throughputでも、予測しただけのDraft tokenを足した数字でもないことだ。single-streamで最終的に確定した出力トークン数を、実際のDecode時間で割った値である。

ただし「M1 Maxが27Bモデルを通常生成で36 tok/s動かした」と表現するのは正確ではない。正しくは次のようになる。

> Qwen3.8-27B reached a 29.16 tok/s interleaved repeated-run median with MTPLX MTP D3 versus a 13.89 tok/s interleaved AR median (2.10x); a separate short D3-only series peaked at 39.90 tok/s.

## 測定環境

- MacBook Pro `MacBookPro18,2`
- Apple M1 Max、32-core GPU
- 64 GB unified memory
- macOS 26.6.2（25G83）
- MTPLX 2.9.0
- `Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed-FP16`
- `turbo` profile
- MTP depth 3
- Scheduler `serial`
- Batching `solo`
- Thinking無効
- Prefix Cache無効
- Apple標準ファン制御

モデルはYoussof Altoukhi/MTPLXが公開した[`Qwen3.8-27B-MTPLX-Optimized-Speed-FP16`](https://huggingface.co/Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed-FP16)を使用した。量子化済み整数パックを維持しながら、BF16だったScale、Bias、Norm、GDN状態、MTP周辺の浮動小数点テンソルをFP16へ変換したM1/M2向け上流Artifactである。私たちがモデルを変換・学習したわけではない。私たちの成果は、M1 Maxでの構成、再現、反復測定、Ablation、監査、公開ハーネスである。

大部分の本体重みは4bit・group size 32で、埋め込み、出力ヘッド、Linear Attention出力、終盤MLPなど精度に敏感な74のWeight-matrix moduleは8bit・group size 64で保持される。MTP Draft headの8行列は4bit・group size 64で事前量子化されている。

配布ページ上のDownload表示は20.4 GB。今回観測したActive memoryは約20.5 GB、Peak memoryは約23.0 GBだった。測定時には他の大規模モデルサーバーを停止し、SwapやGPUメモリ競合を避けた。

> Powered by MTPLX by Youssof Altoukhi — https://github.com/youssofal/MTPLX

## 測定方法

固定プロンプトは次のとおり。Tokenizer適用後の入力は29トークンだった。

```text
Output only valid Python code implementing merge sort, binary search,
and deterministic unit tests.
```

条件は`temperature=0`、`top_p=1`、`top_k=1`、Seed固定、512 final output tokens。AR、MTP D1、D2、D3を同じ条件で実行した。

各リクエストには`cache_mode: bypass`を指定し、Prefix Cacheや過去セッションからの復元を使わなかった。各モードの初回コンパイルは64トークンのWarmupで先に完了させ、計測から除外した。

さらに、AR・D1・D2・D3の出力本文をPythonの`hashlib.sha256`で比較した。4方式は同じ512トークン列を返し、Hashも完全一致した。速度を上げるために回答を簡略化したわけではない。ただし全方式とも`finish_reason=length`でコードは途中終了しているため、これはコード能力やタスク完遂率のベンチではなく、コード形式の固定長Decodeマイクロベンチである。

## 結果

### Greedy parity/Ablation

| モード | Decode | AR比 |
|---|---:|---:|
| AR | 14.321 tok/s | 1.00倍 |
| MTP D1 | 21.931 tok/s | 1.53倍 |
| MTP D2 | 21.749 tok/s | 1.52倍 |
| MTP D3 | **35.434 tok/s** | **2.47倍** |

### 短いD3単独系列

| Run | Decode tok/s |
|---:|---:|
| 1 | 36.847 |
| 2 | 39.897 |
| 3 | 39.871 |
| 4 | 38.909 |
| 5 | 35.201 |

- 平均：38.145 tok/s
- 中央値：38.909 tok/s
- Sample standard deviation：2.061 tok/s
- 最小〜最大：35.201〜39.897 tok/s

この系列は高い一方で変動が大きく、持続性能とは扱わない。

### AR/D3交互5回の連続反復測定

| 指標 | AR | MTP D3 |
|---|---:|---:|
| 平均 | 13.854 tok/s | 30.173 tok/s |
| 中央値 | **13.892 tok/s** | **29.160 tok/s** |
| 最小〜最大 | 13.372〜14.340 | 27.251〜33.097 |
| Sample standard deviation | 0.415 | 2.521 |
| Client wall-clock中央値 | 13.744 tok/s | 28.438 tok/s |

中央値同士のSpeedupは2.099倍。D3は33.10から27.25 tok/sへ、ARも14.34から13.37 tok/sへ低下した。このFormal runを本記事の主要値とする。

### 1,024トークン

別の42-token promptを使った1,024トークン生成1回では、Decode 35.061 tok/s、End-to-end 34.046 tok/s、Decode時間29.207秒だった。Formal runの入力は29 tokensなので、出力長だけの直接比較ではない。長い出力での補助測定であり、`n=1`なので反復統計としても扱わない。

## 公開情報との比較

2026-08-31時点で、[今回と同じFP16 Artifactのモデルカード](https://huggingface.co/Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed-FP16)は「M1/M2の数値はまだ公開していない」と明記している。同ページには、BF16親モデルをM5 Maxで測ったコード課題58.7 tok/s、長いxhigh reasoning 35.1〜37.3 tok/sが掲載されている。

ただし、これはM5 Max、公式Qwen Sampling、モデル自身のStopまで生成した測定であり、今回のM1 Max、Greedy、固定512トークンとは条件が異なる。したがって速度の上下を直接の勝敗にはできない。本記録の価値は、同じFP16 Artifactについて、未公開だったM1 Max条件を生データと再現スクリプト付きで示した点にある。「世界最速」ではなく「現時点で確認できる、条件を明示した公開M1 Maxデータ点」と表現する。

## なぜ36 tok/sまで上がったのか

通常のARでは、512トークンを生成するために対象モデルをほぼ512回逐次実行する。MTP D3では軽量なDraft headが最大3トークン先まで候補を出し、27B本体が候補列をまとめて検証する。

詳細を取得した1回では、512 final output tokensに対してTarget verificationは135回だった。単純平均すると、1回のVerificationあたり約3.79 final tokensを確定している。

MTPの位置別受理率は次のとおりだった。

| Draft位置 | 平均受理確率 |
|---|---:|
| 1トークン先 | 96.30% |
| 2トークン先 | 95.52% |
| 3トークン先 | 88.81% |

Pythonコードはインデント、括弧、識別子、`return`、`assert`、定型的な制御構造が続くため、自由な文章より先読みが当たりやすい。この高い受理率がD3の効果を引き出した。

Runtimeは403 Draft tokens、377 Accepted drafts、15 Rejected drafts、119 Bonus tokensを別々の内部Counterとして報告した。これらは単純な排他的内訳ではなく、Bonus tokenはTarget側出力Accountingの一部なので、Accepted draftsへ足してFinal totalを作ってはいけない。速度の分子はあくまで512 final output tokensである。

MTPLXのTurbo経路も重要である。同梱した`results/burst-2026-08-31/ablation-mtp-d3.json`では、135回のVerification cycleが全てCompiled pathを通り、Fallbackは0回だった。計測された時間は、Draft生成2.386秒、Verification 11.574秒、Accept処理0.194秒、Decode全体14.334秒。ブロック検証はARの1ステップより重く、Draft生成コストもあるため、`512 / 135 = 3.79`がそのまま3.79倍の高速化になるわけではない。Formal runの交互測定中央値Speedupは2.10倍だった。

## 精度は変わっていないのか

Greedy条件ではAR/D1/D2/D3の出力が完全一致した。Speculative decodingではDraft headが候補を提案するだけで、対象モデルによる検証に合格したPrefixだけを採用する。

Samplingを使う場合も、MTPLXはProbability ratioとResidual resamplingによるExact speculationを掲げている。ただし本リポジトリでHash一致を実証した範囲は、今回のGreedy固定プロンプトである。

## この数字が意味しないもの

今回の29〜40 tok/sは次の主張ではない。

- Qwen3.8-27Bの通常AR速度が36 tok/s
- あらゆるプロンプトで36 tok/s
- 長いAgent履歴を含むEnd-to-end速度が36 tok/s
- 世界中の全M1 Maxで最速だと証明済み

自由文章ではMTP受理率が変わり得て、長い履歴ではPrefill時間も支配的になる。本結果は、短い入力からの予測しやすいコード生成におけるsingle-stream Decode記録として読むべきである。

また、RTX 5090やM5 MaxのMTP記録も同じ「最終確定トークンのSpeculative Decode」というカテゴリーに置けるが、モデルArtifact、量子化、Prompt、Context、Output length、Sampling、Cache、Throughput定義を揃えない限り直接比較はできない。

## 再現方法

このリポジトリの`start_server.sh`は、利用者のローカルパスを環境変数で受け取る。個人名を含む固定パスはない。

計測に使用したモデルRevisionは`model.lock.json`に固定し、READMEには同じSHAを指定する`hf download --revision`コマンドを掲載した。

```bash
export MODEL_PATH="/absolute/path/to/Qwen3.8-27B-MTPLX-Optimized-Speed-FP16"
export MTPLX_BIN="mtplx"
./scripts/start_server.sh
```

別ターミナルで以下を実行する。

```bash
./scripts/benchmark.sh
```

スクリプトは各モードをWarmupし、まずAR/D1/D2/D3のGreedy出力一致を検証する。続いてARとD3をABBA順で交互に各5回測定し、サーバー側Decode時間とClient wall-clockの両方を保存する。公開JSONLには生成本文を含めず、出力のSHA-256、Byte数、Cache状態、MTP統計だけを記録する。

通常の実行結果はGit管理外の`results/raw/`へ保存されるため、同梱したFormal resultは上書きされない。

## まとめ

高速化の技術そのものは上流ArtifactとMTPLXによるもので、次の組み合わせで説明できる。

1. M1/M2向けFP16 Artifact
2. 4bit本体＋重要部分8bitの混合量子化
3. 4bit MTP Draft head
4. MTP depth 3
5. コード生成での高いD3受理率
6. MTPLX TurboのCompiled verification
7. Single-stream、Solo、Cache bypass
8. 他の大規模モデルを停止したメモリ管理

AR/D3交互測定では、AR中央値13.89 tok/sからMTP D3中央値29.16 tok/sへ、同じGreedy出力を維持したまま2.10倍になった。短いD3単独系列の最大値は39.90 tok/sだった。世界記録という肩書きより、瞬間値と連続反復値の違い、生JSONL、Client wall-clock、再現スクリプトを公開し、他のM1 Maxで追試可能にしたことの方が技術的には重要である。

## ライセンス・クレジット

- Qwen3.8-27B: [Model card](https://huggingface.co/Qwen/Qwen3.8-27B) / [Apache-2.0 License](https://huggingface.co/Qwen/Qwen3.8-27B/blob/main/LICENSE)
- 使用Artifact: [`Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed-FP16`](https://huggingface.co/Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed-FP16)（HF metadata上Apache-2.0、計測Revisionは`model.lock.json`参照）
- MTPLX 2.9.0: [LICENSE](https://github.com/youssofal/MTPLX/blob/v2.9.0/LICENSE) / [NOTICE](https://github.com/youssofal/MTPLX/blob/v2.9.0/NOTICE) / [CITATION.cff](https://github.com/youssofal/MTPLX/blob/v2.9.0/CITATION.cff)
- MLX / mlx-lm: [MLX MIT License](https://github.com/ml-explore/mlx/blob/main/LICENSE) / [mlx-lm MIT License](https://github.com/ml-explore/mlx-lm/blob/main/LICENSE)

> Powered by MTPLX by Youssof Altoukhi — https://github.com/youssofal/MTPLX
