# X投稿用原稿

## 1. まず出す短文（正式公開ベンチ）

M1 Max（32-core GPU / 64GB）でQwen3.8-27Bを測定。MTPLX 2.9.0のMTP D3で、AR/D3交互5回の中央値は13.89→29.16 tok/s（2.10倍）。短いD3単独系列は最大39.90 tok/s。日本語18.67、英語22.28、中国語19.43、Pythonコード33.05。最終確定tokenのみ、cache bypass、greedy。世界記録や通常AR速度とは主張しません。

https://github.com/Takuyan-labs/qwen38-m1max-mtplx-benchmark

## 2. 俺たちの無検閲・最速派生を出す短文

M1 Max 64GBで、Qwen3.8-27B Abliterated + MTPLX MTP D3を実測。固定コードではAR 15.56→D3 37.21 tok/s。内容別D3は日本語20.90、コード32.55、数学33.87（平均29.11）。AR/D1/D2/D3の出力SHA-256は一致。draft tokenは加算していません。重みは再配布せず、測定データと再現条件を公開。

https://github.com/Takuyan-labs/qwen38-m1max-mtplx-benchmark/tree/main/results/abliterated-m1max-20260919

## 3. スレッド（無検閲・最速派生）

### 1/5

M1 Max（32-core GPU / 64GB）で、Qwen3.8-27B Abliteratedの最速構成を測定しました。MTPLX 2.9.0、native MTP D3、single-stream、prefix cache bypassです。

### 2/5

固定コード課題では、通常AR 15.56 tok/sに対しMTP D3は37.21 tok/s。AR/D1/D2/D3で出力SHA-256が一致し、draft tokenは速度の分子に加えていません。

### 3/5

自由度の違う内容では、D3は日本語20.90、Pythonコード32.55、数学33.87 tok/s。3種平均は29.11 tok/s。コードや数式は予測しやすいため速く、全用途の期待値ではありません。

### 4/5

コード検証では、生成したpalindrome実装が6個のassertを通過しました。ただし512-token固定測定の一部は`finish_reason=length`なので、速度記録とエージェント完遂能力は分けて評価します。

### 5/5

無検閲派生の重みはこのリポジトリに再配布していません。モデル出典、ライセンス、測定JSON、条件を公開しています。通常版の正式反復ベンチも同じリポジトリにあります。

https://github.com/Takuyan-labs/qwen38-m1max-mtplx-benchmark

## 4. 投稿時の注意

- 「世界最速」「27B本体が37 tok/s」とは書かない。
- `37.21 tok/s`は無検閲派生の固定コードD3 1回の記録、`29.16 tok/s`は通常版の交互5回中央値で、別artifact。
- 「無検閲＝安全」や「能力が全面的に上」とは書かない。
- MTPLX、Qwen、派生artifactの出典を残す。
