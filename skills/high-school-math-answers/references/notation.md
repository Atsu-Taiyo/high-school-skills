# 記号と表記の一覧

教科書（数研出版・東京書籍）の表記と，Markdown＋LaTeX（KaTeX・MathJax のどちらでも描画できる形）での書き方をまとめる。「ソース」の列は `$...$` の中にそのまま書ける。

表の中では縦線 `|` が区切りと衝突するので，この一覧では絶対値を `\lvert`，`\rvert` で書いている。表の外の本文では `|x|` と書いてよい。

## 目次

1. 共通
2. 数と式・集合と命題（数学Ⅰ）
3. 図形（数学Ⅰ・A）
4. データの分析・統計（数学Ⅰ・B）
5. 場合の数と確率（数学A）
6. 整数（数学A）
7. 式と方程式・図形と方程式（数学Ⅱ）
8. 指数・対数・三角関数（数学Ⅱ）
9. 数列（数学B）
10. 極限・微分・積分（数学Ⅱ・Ⅲ）
11. ベクトル（数学C）
12. 複素数平面・曲線（数学C）
13. 描画できなくなる書き方と式番号

## 1. 共通

| 内容 | 表示 | ソース | 備考 |
|---|---|---|---|
| 分数 | $\dfrac{a}{b}$ | `\dfrac{a}{b}` | 指数・添字の中は `\frac` |
| 以下，以上 | $a\leqq b$，$a\geqq b$ | `a\leqq b`，`a\geqq b` | 教科書は ≦ ≧ |
| 等しくない | $a\neq b$ | `a\neq b` | |
| ほぼ等しい | $\sqrt{2}\fallingdotseq 1.41$ | `\fallingdotseq` | |
| 積 | $2\cdot 3$，$2\times 3$ | `\cdot`，`\times` | 文字式では省略。数どうしは `\cdot` か `\times` |
| 省略 | $1+2+\cdots+n$ | `\cdots` | 和・積の途中は `\cdots`，列挙は `\dots` |
| 複号 | $x=\pm 2$ | `\pm`，`\mp` | 「複号同順」と添える |
| 絶対値 | $\lvert x\rvert$ | `\lvert x\rvert` | 表の外では縦線2本で挟む書き方でよい |
| 平方根 | $\sqrt{2}$，$\sqrt[3]{2}$ | `\sqrt{2}`，`\sqrt[3]{2}` | |
| 式番号 | 　$x+y=3$　……① | `　$x+y=3$　……①` | 本文では「① より」と参照する |
| ならば | $p\Rightarrow q$ | `\Rightarrow` | |
| 同値 | $p\iff q$ | `\iff` | 本当に同値のときだけ |
| 連立 | $\begin{cases}x+y=3\\x-y=1\end{cases}$ | `\begin{cases}x+y=3\\x-y=1\end{cases}` | |
| そろえた複数行 | | `\begin{aligned}a&=b\\&=c\end{aligned}` | `$$` の中で使う |
| 循環小数 | $0.\dot{3}$，$0.\dot{1}2\dot{3}$ | `0.\dot{3}` | |
| 円周率，自然対数の底 | $\pi$，$e$ | `\pi`，`e` | |

## 2. 数と式・集合と命題（数学Ⅰ）

| 内容 | 表示 | ソース | 備考 |
|---|---|---|---|
| 要素である | $a\in A$，$b\notin A$ | `\in`，`\notin` | |
| 部分集合 | $A\subset B$ | `\subset` | $A=B$ の場合も含む。`\subseteq` は使わない |
| 共通部分，和集合 | $A\cap B$，$A\cup B$ | `\cap`，`\cup` | |
| 補集合 | $\overline{A}$ | `\overline{A}` | $A^{c}$ は使わない |
| 空集合 | $\varnothing$ | `\varnothing` | |
| 集合の書き方 | $\{x\mid x>0\}$ | `\{x\mid x>0\}` | 表の外でも区切りは `\mid` |
| 要素の個数 | $n(A)$ | `n(A)` | 絶対値記号や `\#` は使わない |
| 命題の否定 | $\overline{p}$ | `\overline{p}` | `\lnot p` は使わない |
| 全体集合 | $U$ | `U` | |
| 判別式 | $D=b^{2}-4ac$ | `D` | $\dfrac{D}{4}$ も使う |

数の集合は記号にしない。「$x$ は実数」「$n$ は自然数」「$m$，$n$ は整数」と書く。

## 3. 図形（数学Ⅰ・A）

| 内容 | 表示 | ソース | 備考 |
|---|---|---|---|
| 点 | $\mathrm{A}$，$\mathrm{P}(x,y)$ | `\mathrm{A}`，`\mathrm{P}(x,y)` | 点の名前は立体 |
| 線分，長さ | $\mathrm{AB}=5$ | `\mathrm{AB}=5` | 上線は付けない |
| 三角形 | $\triangle\mathrm{ABC}$ | `\triangle\mathrm{ABC}` | |
| 角 | $\angle\mathrm{ABC}=60^{\circ}$ | `\angle\mathrm{ABC}=60^{\circ}` | |
| 辺と角の慣用 | $a,b,c$ と $A,B,C$ | `a`，`A` | $\triangle\mathrm{ABC}$ で $a=\mathrm{BC}$，$A=\angle\mathrm{A}$ |
| 平行，垂直 | $\mathrm{AB}\parallel\mathrm{CD}$，$\mathrm{AB}\perp\mathrm{CD}$ | `\parallel`，`\perp` | |
| 合同，相似 | $\triangle\mathrm{ABC}\equiv\triangle\mathrm{DEF}$，$\triangle\mathrm{ABC}\backsim\triangle\mathrm{DEF}$ | `\equiv`，`\backsim` | 対応する頂点の順にそろえる |
| 弧 | $\overset{\frown}{\mathrm{AB}}$ | `\overset{\frown}{\mathrm{AB}}` | |
| 面積 | $S$，$\triangle\mathrm{ABC}$ | `S` | 「$\triangle\mathrm{ABC}$ の面積を $S$ とする」 |
| 外接円・内接円の半径 | $R$，$r$ | `R`，`r` | |
| 三角比 | $\sin 30^{\circ}$，$\sin^{2}\theta$ | `\sin 30^{\circ}`，`\sin^{2}\theta` | 数学Ⅰは度数法 |

## 4. データの分析・統計（数学Ⅰ・B）

| 内容 | 表示 | ソース | 備考 |
|---|---|---|---|
| 平均値 | $\overline{x}$ | `\overline{x}` | |
| 分散，標準偏差 | $s^{2}$，$s$（$s_{x}^{2}$，$s_{x}$） | `s_{x}^{2}` | $n$ で割る |
| 共分散，相関係数 | $s_{xy}$，$r$ | `s_{xy}`，`r` | |
| 四分位数 | $Q_{1},Q_{2},Q_{3}$ | `Q_{1}` | 四分位範囲は $Q_{3}-Q_{1}$ |
| 確率変数 | $X$，$P(X=k)$，$P(a\leqq X\leqq b)$ | `P(X=k)` | 数学B |
| 期待値（平均） | $E(X)$ | `E(X)` | $E[X]$，$\mu$ だけの表記は使わない |
| 分散，標準偏差 | $V(X)$，$\sigma(X)$ | `V(X)`，`\sigma(X)` | $\mathrm{Var}$ は使わない |
| 二項分布 | $B(n,p)$ | `B(n,p)` | 「$X$ は二項分布 $B(n,p)$ に従う」 |
| 正規分布 | $N(m,\sigma^{2})$ | `N(m,\sigma^{2})` | 標準正規分布は $N(0,1)$。$X\sim N$ の記号 $\sim$ は使わない |
| 標準化 | $Z=\dfrac{X-m}{\sigma}$ | `Z=\dfrac{X-m}{\sigma}` | |
| 標本平均，標本比率 | $\overline{X}$，$R$ | `\overline{X}`，`R` | 母平均 $m$，母標準偏差 $\sigma$，母比率 $p$ |

## 5. 場合の数と確率（数学A）

| 内容 | 表示 | ソース | 備考 |
|---|---|---|---|
| 階乗 | $n!$ | `n!` | |
| 順列 | ${}_{n}\mathrm{P}_{r}$ | `{}_{n}\mathrm{P}_{r}` | |
| 組合せ | ${}_{n}\mathrm{C}_{r}$ | `{}_{n}\mathrm{C}_{r}` | `\binom` は使わない |
| 重複組合せ | ${}_{n}\mathrm{H}_{r}$ | `{}_{n}\mathrm{H}_{r}` | 使うときは ${}_{n+r-1}\mathrm{C}_{r}$ に直す式を添える |
| 重複順列 | $n^{r}$ | `n^{r}` | |
| 円順列 | $(n-1)!$ | `(n-1)!` | |
| 確率 | $P(A)$ | `P(A)` | $\mathrm{Pr}$，$\mathbb{P}$ は使わない |
| 余事象 | $\overline{A}$ | `\overline{A}` | |
| 積事象，和事象 | $A\cap B$，$A\cup B$ | `\cap`，`\cup` | |
| 条件付き確率 | $P_{A}(B)$ | `P_{A}(B)` | $A$ が起こったときの $B$ の確率 |
| 乗法定理 | $P(A\cap B)=P(A)P_{A}(B)$ | | |

## 6. 整数（数学A）

記号をほとんど使わず，言葉で書く。

| 内容 | 書き方 |
|---|---|
| 割り切れる | 「$a$ は $b$ の倍数である」「$b$ は $a$ の約数である」 |
| 最大公約数，最小公倍数 | 「$a$ と $b$ の最大公約数を $g$ とする」 |
| 互いに素 | 「$a$ と $b$ は互いに素である」 |
| 割り算 | 「$a$ を $b$ で割った商を $q$，余りを $r$ とすると $a=bq+r$，$0\leqq r<b$」 |
| $n$ 進法 | $1011_{(2)}$（ソースは `1011_{(2)}`） |
| ガウス記号 | $[x]$。「$[x]$ は $x$ を超えない最大の整数を表す」と添える |
| 合同式（発展） | $a\equiv b\pmod{m}$（ソースは `a\equiv b\pmod{m}`）。定義を書いてから使う |

## 7. 式と方程式・図形と方程式（数学Ⅱ）

| 内容 | 表示 | ソース | 備考 |
|---|---|---|---|
| 虚数単位 | $i$ | `i` | $i^{2}=-1$。$j$ や立体の $\mathrm{i}$ は使わない |
| 共役な複素数 | $\overline{\alpha}$ | `\overline{\alpha}` | $\alpha^{*}$ は使わない |
| 1の3乗根 | $\omega$ | `\omega` | 「$1$ の3乗根のうち虚数であるものの1つを $\omega$ とする」と定義して使う |
| 2点間の距離 | $\mathrm{AB}=\sqrt{(x_{2}-x_{1})^{2}+(y_{2}-y_{1})^{2}}$ | | |
| 直線 | $y=mx+n$，$ax+by+c=0$ | | |
| 円 | $(x-a)^{2}+(y-b)^{2}=r^{2}$ | | |
| 領域 | 「不等式 $y>x^{2}$ の表す領域」 | | 境界を含むかどうかを必ず書く |

## 8. 指数・対数・三角関数（数学Ⅱ）

| 内容 | 表示 | ソース | 備考 |
|---|---|---|---|
| 累乗根 | $\sqrt[n]{a}$ | `\sqrt[n]{a}` | |
| 対数 | $\log_{a}M$ | `\log_{a}M` | $a>0$，$a\neq 1$，$M>0$ |
| 常用対数 | $\log_{10}2$ | `\log_{10}2` | 底を省略しない |
| 自然対数（数学Ⅲ） | $\log x$ | `\log x` | 底 $e$ を省略する。`\ln` は使わない |
| 弧度法 | $\dfrac{\pi}{3}$ | `\dfrac{\pi}{3}` | 単位「ラジアン」は書かない |
| 一般角 | $\theta=\dfrac{\pi}{6}+2n\pi$（$n$ は整数） | | 「$n$ は整数」を添える |
| 三角関数 | $\sin\theta$，$\cos\theta$，$\tan\theta$ | `\sin\theta` | $\cot$，$\sec$，$\csc$ は使わない |
| 累乗 | $\sin^{2}\theta$ | `\sin^{2}\theta` | $\sin^{-1}$ は使わない |
| 合成 | $r\sin(\theta+\alpha)$ | | $\alpha$ が有名角でなければ「$\cos\alpha=\dfrac{3}{5}$，$\sin\alpha=\dfrac{4}{5}$ を満たす角」と定める |

## 9. 数列（数学B）

| 内容 | 表示 | ソース | 備考 |
|---|---|---|---|
| 数列 | $\{a_{n}\}$ | `\{a_{n}\}` | |
| 初項，公差，公比 | $a$，$d$，$r$ | | |
| 和 | $S_{n}$ | `S_{n}` | |
| 総和 | $\displaystyle\sum_{k=1}^{n}a_{k}$ | `\displaystyle\sum_{k=1}^{n}a_{k}` | 文中では `\displaystyle` を付ける |
| 階差数列 | $\{b_{n}\}$，$b_{n}=a_{n+1}-a_{n}$ | | $\Delta a_{n}$ は使わない |
| 漸化式 | $a_{n+1}=2a_{n}+1$ | | |

総乗の記号は使わない。積は $a_{1}a_{2}\cdots a_{n}$ と書く。

## 10. 極限・微分・積分（数学Ⅱ・Ⅲ）

| 内容 | 表示 | ソース | 備考 |
|---|---|---|---|
| 極限 | $\displaystyle\lim_{n\to\infty}a_{n}=\alpha$ | `\displaystyle\lim_{n\to\infty}a_{n}` | |
| 片側極限 | $\displaystyle\lim_{x\to +0}$，$\displaystyle\lim_{x\to 1-0}$ | `\lim_{x\to +0}`，`\lim_{x\to 1-0}` | $x\to 0^{+}$ は使わない |
| 発散 | $\displaystyle\lim_{n\to\infty}a_{n}=\infty$ | | 「正の無限大に発散する」 |
| 近づく | $x\to a$ のとき $f(x)\to\alpha$ | `\to` | $\lim$ の下と同じ矢印にそろえる。`\longrightarrow` と混ぜない |
| 無限級数 | $\displaystyle\sum_{n=1}^{\infty}a_{n}$ | `\sum_{n=1}^{\infty}` | |
| 導関数 | $f'(x)$，$y'$，$\dfrac{dy}{dx}$ | `f'(x)`，`\dfrac{dy}{dx}` | $\dot{y}$，$Df$ は使わない |
| 第2次導関数 | $f''(x)$，$y''$，$\dfrac{d^{2}y}{dx^{2}}$ | `f''(x)` | |
| 第 $n$ 次導関数 | $f^{(n)}(x)$ | `f^{(n)}(x)` | |
| 微分係数 | $f'(a)$ | | |
| 式の微分 | $(x^{3}+2x)'=3x^{2}+2$ | `(x^{3}+2x)'` | |
| 不定積分 | $\displaystyle\int f(x)\,dx=F(x)+C$ | `\int f(x)\,dx` | 「$C$ は積分定数」を添える |
| 定積分 | $\displaystyle\int_{a}^{b}f(x)\,dx$ | `\int_{a}^{b}f(x)\,dx` | |
| 定積分の計算 | $\Bigl[\,F(x)\,\Bigr]_{a}^{b}$ | `\Bigl[\,F(x)\,\Bigr]_{a}^{b}` | |
| 区間（数学Ⅲ） | $[a,b]$，$(a,b)$ | | 数学Ⅲ以外では不等式で書く |
| 増減表の矢印 | $\nearrow$，$\searrow$ | `\nearrow`，`\searrow` | 凹凸つきは「下に凸で増加」と言葉を添える |

増減表は Markdown の表で書く。

| $x$ | $\cdots$ | $-1$ | $\cdots$ | $1$ | $\cdots$ |
|---|---|---|---|---|---|
| $f'(x)$ | $+$ | $0$ | $-$ | $0$ | $+$ |
| $f(x)$ | $\nearrow$ | 極大 $2$ | $\searrow$ | 極小 $-2$ | $\nearrow$ |

置換積分の区間の対応も表で書く。

| $x$ | $0$ | $\longrightarrow$ | $1$ |
|---|---|---|---|
| $\theta$ | $0$ | $\longrightarrow$ | $\dfrac{\pi}{4}$ |

## 11. ベクトル（数学C）

| 内容 | 表示 | ソース | 備考 |
|---|---|---|---|
| ベクトル | $\vec{a}$ | `\vec{a}` | 太字にしない |
| 有向線分 | $\overrightarrow{\mathrm{AB}}$ | `\overrightarrow{\mathrm{AB}}` | |
| 零ベクトル | $\vec{0}$ | `\vec{0}` | |
| 大きさ | $\lvert\vec{a}\rvert$ | `\lvert\vec{a}\rvert` | 二重線にしない |
| 成分 | $\vec{a}=(a_{1},a_{2})$ | `\vec{a}=(a_{1},a_{2})` | 横に並べる。縦ベクトルにしない |
| 内積 | $\vec{a}\cdot\vec{b}$ | `\vec{a}\cdot\vec{b}` | $\cdot$ を省略しない。$\vec{a}\cdot\vec{a}=\lvert\vec{a}\rvert^{2}$ と書き，$\vec{a}^{2}$ とは書かない |
| 平行，垂直 | $\vec{a}\parallel\vec{b}$，$\vec{a}\perp\vec{b}$ | `\parallel`，`\perp` | |
| 位置ベクトル | $\mathrm{P}(\vec{p})$ | `\mathrm{P}(\vec{p})` | |
| 単位ベクトル | $\vec{e}$ | | $\hat{a}$ は使わない |
| 添字つきのベクトル | $\vec{e}_1$，$\vec{a}_n$ | `\vec{e}_1`，`\vec{a}_n` | 添字は矢印の外。`\vec{e_1}` にしない |
| 直線のベクトル方程式 | $\vec{p}=\vec{a}+t\vec{d}$ | | $t$ は実数（媒介変数） |

## 12. 複素数平面・曲線（数学C）

| 内容 | 表示 | ソース | 備考 |
|---|---|---|---|
| 複素数 | $z=x+yi$ | `z=x+yi` | 「$x$，$y$ は実数」を添える |
| 絶対値，偏角 | $\lvert z\rvert$，$\arg z$ | `\arg z` | 偏角の範囲を書く |
| 極形式 | $z=r(\cos\theta+i\sin\theta)$ | | $r>0$。$e^{i\theta}$ や $\mathrm{cis}$ は使わない |
| 点 | $\mathrm{A}(\alpha)$ | `\mathrm{A}(\alpha)` | |
| 実部，虚部 | 「$z$ の実部」「$z$ の虚部」 | | $\mathrm{Re}$，$\mathrm{Im}$ は使わない |
| 楕円 | $\dfrac{x^{2}}{a^{2}}+\dfrac{y^{2}}{b^{2}}=1$ | | |
| 双曲線 | $\dfrac{x^{2}}{a^{2}}-\dfrac{y^{2}}{b^{2}}=1$ | | |
| 放物線 | $y^{2}=4px$ | | 焦点 $(p,0)$，準線 $x=-p$ |
| 離心率 | $e$ | | |
| 極座標 | $(r,\theta)$ | | 極方程式 $r=f(\theta)$ |
| 媒介変数表示 | $x=f(t)$，$y=g(t)$ | | |

## 13. 描画できなくなる書き方と式番号

描画できなくなる書き方（独自マクロ，`align`，`\tag`，数式の中の丸数字，`$` の閉じ忘れなど）と式番号の書式は `scripts/hs_check.py` が検査し，出力に「なぜだめか → 何に直すか」を出す（一覧は `check-rules.md`）。式番号は後で参照する式だけに付け，参照は地の文で「① より」と書く。

**番号の系列。** 既定は丸数字 ①②③…。ただし，問題文の番号と衝突する系列は使わない。

| 問題文にあるもの | 式番号に使う系列 |
|---|---|
| 丸数字が無い | ①②③… |
| 丸数字の選択肢・空欄・条件（「① 正　② 負」「条件 ①」） | (a)(b)(c)…（`　$式$　……(a)`） |
| 丸数字も，(a)(b) の小問もある | (i)(ii)(iii)…，それも場合分けに使うなら (A)(B)(C)… |

- 書き始める前に，問題文の番号（小問，選択肢，条件，図）を確かめて系列を決め，1題を通して変えない。
