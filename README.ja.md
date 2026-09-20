# M1 MaxのQwen3.8-27B：MTPLX 2.11.3を基本構成に更新

Apple M1 Max（32-core GPU、64 GB unified memory）上で、Qwen3.8-27BをMTPLX 2.11.3、MLX 0.32.2、MTP depth 3で測定する再現可能なsingle-streamベンチマークです。

> **現在の基本構成（MTPLX 2.11.3）：fresh PythonコードのD3を5回測定し、中央値38.932、最大39.034 tok/s。**
> 5回の出力SHAは一致し、受理Draftは377/403、Compiled verification fallbackは0回でした。
> 旧MTPLX 2.9.0のFormal・Burst記録は比較用に保持しています。

> **旧MTPLX 2.9.0のAR/D3交互5回の中央値は、AR 13.89、MTP D3 29.16 tok/s。**
> 数分間の交互連続測定で2.10倍。短いD3単独系列では最大39.90 tok/s。
> Prefix Cacheは無効。AR/D1/D2/D3のgreedy出力は完全一致。
> 別の内容別D3中央値：日本語18.67、英語22.28、中国語19.43、Pythonコード33.05 tok/s。

これは「27B本体が通常の逐次生成で29〜40 tok/s出た」という記録ではありません。MTP speculative decodingを含め、最終的に確定した出力トークンだけを数えた速度です。Draft tokenは速度の分子に含めていません。旧Formal値は固定長リクエストを交互に連続実行した測定で、現在の基本構成のfresh-code値とは別系列です。

固定条件は29-token prompt、512 output tokens、Greedy生成です。全方式が`finish_reason=length`で止まり、出力コードは未完成でした。したがって、これは予測しやすいcode-like Decodeのマイクロベンチであり、コード能力・Agent完遂率・自由な日本語会話の速度を示すものではありません。

詳しい技術解説は[日本語記事](docs/article-ja.md)にまとめています。

## 結果

| 指標 | AR | MTP D3 |
|---|---:|---:|
| 5回平均 | 13.854 tok/s | 30.173 tok/s |
| 5回中央値 | **13.892 tok/s** | **29.160 tok/s** |
| 最小〜最大 | 13.372〜14.340 | 27.251〜33.097 |
| Client側中央値 | 13.744 tok/s | 28.438 tok/s |

同一出力比較：

| モード | Decode | AR比 |
|---|---:|---:|
| AR | 14.321 tok/s | 1.00倍 |
| MTP D1 | 21.931 tok/s | 1.53倍 |
| MTP D2 | 21.749 tok/s | 1.52倍 |
| **MTP D3** | **35.434 tok/s** | **2.47倍** |

別の42-token promptを使った1,024トークン追加測定1回では35.061 tok/sでした（`n=1`）。Formal runとの出力長だけの直接比較には使いません。

### 現在の基本構成：MTPLX 2.11.3再測定

固定Revision、同一Prompt、Greedy、Cache bypass、native MTP D3、512 tokensで再測定しました。

| 指標 | 値 |
|---|---:|
| 回数 | 5 |
| Decode中央値 | **38.932 tok/s** |
| Decode平均 | 38.949 tok/s |
| 最小〜最大 | 38.849〜39.034 tok/s |
| 標準偏差 | 0.073 tok/s |
| 出力SHA | 5回一致 |

旧2.9.0 Burst中央値38.909 tok/sと同等ですが、旧最大39.897 tok/sは更新していません。生データは[`fresh-code-d3-2.11.3-rerun-512.json`](results/optimization-20260921/fresh-code-d3-2.11.3-rerun-512.json)です。

### 日本語・英語・中国語・コードで速度はどう変わるか

別途、512-token Greedy、Cache bypass、AR/D3の同一条件で、4種類の出力を合計40回測定しました。各プロンプト・各モードを5回ずつ実行し、カテゴリ順を回転させ、AR→D3とD3→ARの順序も交互にしています。

| 出力 | AR中央値 | MTP D3中央値 | D3範囲 | D3/AR中央値比 | D3 Draft受理率 | D3 Unicode code points/秒中央値 |
|---|---:|---:|---:|---:|---:|---:|
| 日本語の技術文 | 14.73 | **18.67** | 18.41〜20.12 | 1.27倍 | 41.00% | 33.84 |
| 英語の技術文 | 14.87 | **22.28** | 20.94〜23.72 | 1.50倍 | 54.84% | 127.24 |
| 簡体字中国語の技術文 | 14.55 | **19.43** | 18.50〜19.89 | 1.34倍 | 40.87% | 36.17 |
| Pythonコード | 14.76 | **33.05** | 31.83〜34.70 | 2.24倍 | 93.55% | 107.74 |

40件すべて512 final tokens、Cache 0、Compiled verification fallback 0でした。同じプロンプトでは、全AR/D3反復の出力SHA-256が一致しています。コードだけを短く測った最大39.90 tok/sは引き続き有効ですが、日本語など自由文の期待速度としては扱えません。

観測された速度差と直接対応したのは、言語の優劣ではなくDraft受理率、つまりこの出力における予測しやすさです。この課題では512 tokensあたりのTarget verificationが、コード135回、英語194回、日本語229回、中国語230回でした。コードでは構文・記号・定型句と高いDraft受理率が同時に観測され、複数tokenを一度に確定できました。なお、これは各カテゴリ1プロンプトの出力ドメイン速度テストであり、一般的な言語能力・品質ベンチではありません。Tokenizerの分割が異なるため、tok/sと文字/秒のどちらも意味情報量そのものではありません。

2026-08-31時点で、[同一FP16 Artifactのモデルカード](https://huggingface.co/Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed-FP16)は、Publisher自身によるM1/M2の数値は未公開としています。M5 Max上のBF16親モデルではコード課題58.7 tok/sが掲載されていますが、Chip、Sampling、停止条件が異なるため直接比較はしません。本リポジトリは世界順位の断定ではなく、追試できるM1 Maxの公開データ点です。

## 再現方法

モデル[`Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed-FP16`](https://huggingface.co/Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed-FP16)とMTPLXを別途用意します。モデル本体はこのリポジトリには含みません。

`huggingface_hub`の`hf`コマンドで、計測時と同じRevisionを取得できます。

```bash
export MODEL_PATH="$PWD/models/Qwen3.8-27B-MTPLX-Optimized-Speed-FP16"
hf download Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed-FP16 \
  --revision c984b2932d29676a6dabb6431b27da7ca2411508 \
  --local-dir "$MODEL_PATH"
```

RevisionとArtifact fingerprintは[`model.lock.json`](model.lock.json)にも保存しています。

現在の基本構成は、分離したPython環境に固定依存関係を入れて再現します。

```bash
python3 -m venv .venv-mtplx-2.11.3
source .venv-mtplx-2.11.3/bin/activate
python -m pip install "mtplx==2.11.3" "mlx==0.32.2" "mlx-lm==0.31.3" "transformers==5.12.1"
```

混合量子化、M1/M2向けFP16 Artifact、MTP head、MTPLX runtimeはYoussof Altoukhi/MTPLXによる上流成果です。このリポジトリの成果は、M1 Max上の構成、反復測定、Ablation、監査、再現ハーネスです。

> Powered by MTPLX by Youssof Altoukhi — https://github.com/youssofal/MTPLX

```bash
# Download時に設定済みなら、MODEL_PATHの再設定は不要です。
export MODEL_PATH="/absolute/path/to/Qwen3.8-27B-MTPLX-Optimized-Speed-FP16"
export MTPLX_BIN="mtplx"
./scripts/start_server.sh
```

起動スクリプトは既定でMTPLX 2.11.3を確認します。過去のruntimeを意図的に再現する場合だけ、`MTPLX_ALLOW_VERSION_MISMATCH=1`を指定してください。

別ターミナルで：

```bash
./scripts/benchmark.sh
```

日本語・英語・中国語・コードの比較を再実行する場合：

```bash
python3 scripts/benchmark_content_mix.py
```

全コンテンツでAR・D1・D2・D3を比較する深度スイープ（既定5回）は次で実行します。

```bash
python3 scripts/benchmark_content_depths.py --runs 5 --tokens 512 --output-dir results/raw/content-depths-YYYYMMDD
```

出力JSONLには、最終出力SHA-256、decode時間、Draft/Verify時間、受理率、Verification回数、Context Copy統計、メモリ値を保存します。runtimeが返さない値は推定せず`null`のままにします。

ローカル結果はGit管理外の`results/raw/`へ保存され、公開済み証跡を上書きしません。保存先を変える場合は`--output-dir`を指定します。

再現時は、他の大規模モデルサーバーを停止してメモリ競合を避けてください。

### Claude Code CLIから使う

サーバーを起動したまま、別のターミナルでこのリポジトリに移動して実行します。

```bash
./scripts/claude-code-mtplx.sh
```

Claude Code CLIからMTPLXのAnthropic互換Messages APIへ直接接続します。Ollamaのモデル一覧に登録したり、Claude Desktopの設定を変更したりはしません。専用のCLI設定保存先`~/.claude/mtplx-27b`を使い、継承した`ANTHROPIC_API_KEY`も外すため、この起動ではAnthropicアカウントではなくローカル接続を使います。ツール呼び出しを実機確認できたClaude Codeの最小モード`--bare`を既定にし、作業ディレクトリを明示的に追加してプロジェクトの`CLAUDE.md`を読み込みます。一方、Hooks・Plugins・LSP・Auto Memoryは無効になります。初回起動時にモデル選択テンプレートを専用プロファイルへコピーします（既存の設定があれば上書きしません）。Qwen IDはSonnet相当のクライアント設定として扱いますが、MTPLXへ送るモデルIDは`qwen3.8-27b-mtplx`のままです。既定のEffortは`low`です。速度より熟考を優先する場合は`MTPLX_CLAUDE_EFFORT=medium`や`high`を指定できます。フル設定を試す場合は`MTPLX_CLAUDE_BARE=0`を指定します。Bashの読み取り専用ツール呼び出し一往復は確認済みですが、大規模な自律コーディング品質まで保証するものではありません。

## 正確な主張

公開時は次の表現を推奨します。

> 現在の基本構成では、M1 Max 64 GB上のQwen3.8-27BをMTPLX 2.11.3 MTP D3で測定し、fresh Pythonコードのsingle-stream Decode中央値38.932 tok/s、最大39.034 tok/sを記録した。旧2.9.0のAR/D3交互中央値29.16 tok/sと短期最大39.90 tok/sも比較用に公開している。

これは第三者認定の世界記録ではなく、条件と生データを公開したローカル実測記録です。

## ライセンス

独自のベンチスクリプト、文書、プロンプト、設定、および測定記録の選択・構成について管理者が保有する著作権上の利益はMIT Licenseです。個々の測定事実は著作物に当たらない場合があります。モデル生成文を私たちの著作物とは主張せず、現在の公開結果には本文を含めず、SHA-256、Byte数、Token数、時間、Runtime統計だけを保存します。

Qwenモデル、最適化Artifact、MTPLX、MLX、mlx-lmなどの第三者成果物には各上流条件が適用されます。詳しくは[第三者Notice](THIRD_PARTY_NOTICES.md)と[測定データの範囲](results/README.md)を参照してください。

第三者による公開ベンチマーク、同一機種の外部報告、MTPLXのversion差を比較した検証は[第三者検証レポート](docs/third-party-verification-ja.md)にまとめています。39.90 tok/sを超える未検証自己申告と、条件を確認できる再現可能な記録を分けて記載しています。

追加高速化のA/B検証（runtime、profiling、depth、adaptive、Context Copy、mixed quant）は[最適化検証レポート](M1_MAX_OPTIMIZATION_REPORT.md)にまとめています。
