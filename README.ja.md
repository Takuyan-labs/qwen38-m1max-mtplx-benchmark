# M1 MaxでQwen3.8-27Bを交互連続測定で2.10倍高速化

Apple M1 Max（32-core GPU、64 GB unified memory）上で、Qwen3.8-27BをMTPLX 2.9.0とMTP depth 3により高速化した再現可能なsingle-streamベンチマークです。

> **AR/D3交互5回の中央値は、AR 13.89、MTP D3 29.16 tok/s。**
> 数分間の交互連続測定で2.10倍。短いD3単独系列では最大39.90 tok/s。
> Prefix Cacheは無効。AR/D1/D2/D3のgreedy出力は完全一致。

これは「27B本体が通常の逐次生成で29〜40 tok/s出た」という記録ではありません。MTP speculative decodingを含め、最終的に確定した出力トークンだけを数えた速度です。Draft tokenは速度の分子に含めていません。また、長文1本の耐久試験ではなく、固定長リクエストを交互に連続実行した測定です。

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

混合量子化、M1/M2向けFP16 Artifact、MTP head、MTPLX runtimeはYoussof Altoukhi/MTPLXによる上流成果です。このリポジトリの成果は、M1 Max上の構成、反復測定、Ablation、監査、再現ハーネスです。

> Powered by MTPLX by Youssof Altoukhi — https://github.com/youssofal/MTPLX

```bash
# Download時に設定済みなら、MODEL_PATHの再設定は不要です。
export MODEL_PATH="/absolute/path/to/Qwen3.8-27B-MTPLX-Optimized-Speed-FP16"
export MTPLX_BIN="mtplx"
./scripts/start_server.sh
```

別ターミナルで：

```bash
./scripts/benchmark.sh
```

ローカル結果はGit管理外の`results/raw/`へ保存され、公開済み証跡を上書きしません。保存先を変える場合は`--output-dir`を指定します。

再現時は、他の大規模モデルサーバーを停止してメモリ競合を避けてください。

## 正確な主張

公開時は次の表現を推奨します。

> M1 Max 64 GB上のQwen3.8-27Bで、MTPLX 2.9.0 MTP D3 speculative decodingを使用し、AR/D3交互5回のsingle-stream Decode中央値29.16 tok/sを記録。AR中央値13.89 tok/sに対して2.10倍。別の短いD3単独系列では最大39.90 tok/s。Prefix Cache無効。

これは第三者認定の世界記録ではなく、条件と生データを公開したローカル実測記録です。
