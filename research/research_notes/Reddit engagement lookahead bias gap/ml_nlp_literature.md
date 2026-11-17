# ML/NLP literature: engagement features (Reddit / Twitter / StockTwits) and look-ahead bias from engagement timing

Scope note: about 17 tool calls (WebSearch / WebFetch). Many pages were only partially readable (compressed PDFs, 404s, snippet-level summaries). Claims are marked [verified-on-page], [search-snippet only] or [uncertain]. Nothing here was found to quantify engagement-timing leakage. That absence is a negative result from a limited search, not proof of absence.

Classification used: A = uses final/scraped engagement without discussing timing; B = discusses timing; C = quantifies the effect.

## Q1. How common is engagement as feature/weight, and which concrete papers/datasets do it (with timing of the engagement values)?

### Takeaway
Engagement features (upvotes/score, comment counts, likes, retweets, followers) are common in practitioner and workshop-level work. Mainstream benchmarks such as StockNet appear to carry no engagement fields. For every example found, the timing of the engagement values is either undocumented or a scrape-time snapshot. Only one non-peer-reviewed source (Arabesque) explicitly flags the snapshot issue.

### Cited Findings
1. Kmak et al., "Predicting stock prices with ChatGPT-annotated Reddit sentiment" (arXiv 2507.22922, ICCS 2025 per search summary). Uses r/wallstreetbets for GME/AMC. The only engagement feature named on the abstract page is comment volume, and the paper reports it and Google Trends as stronger signals than sentiment. Timing of comment counts, windows and leakage controls could not be read. Class A [uncertain; full PDF not read]. [arXiv](https://arxiv.org/abs/2507.22922)
2. A GameStop study (cited in a search summary only) reported comment count (0.44) and score (0.27) as the most important features, with weak correlations overall. Source and venue not identified. [uncertain] Found via [search results](https://derekkuang.github.io/wallstreetbets_sentiment_analysis/) and related items listed there; the specific study was not isolated.
3. Student/practitioner WSB project: mention counts and upvote score sums plus VADER, aggregated per ticker-day, to predict next-day "heat". Not peer reviewed. Timing of scores not stated [search-snippet only]. [Derek Kuang](https://derekkuang.github.io/wallstreetbets_sentiment_analysis/)
4. A practitioner skill/guide weights Reddit posts by upvote_ratio x log(score+1). Heuristic, not research. [search-snippet only] [skills.sh](https://skills.sh/tradeinsight-info/investment-analysis-skills/reddit-sentiment)
5. Big Data 2019 (Dalhousie) paper on finance tweets: the best-performing setup weighted sentiment by maximum followers. It also reports that tweets posted from market close to next-day open are the most predictive. Whether follower counts were as-of-tweet or as-of-scrape is not stated in what I read. Class A [search-snippet only]. [PDF](https://web.cs.dal.ca/~vlado/papers/BigData2019Y.pdf)
6. A 2017 IEEE paper defining "smart" users by likes, follower count and historical accuracy. Details not verified. [search-snippet only]. [IEEE refs page](https://ieeexplore.ieee.org/document/8328513/references)
7. A 2025 study with rank-based weighting with time decay (RBWTD) for non-textual features (views, likes, retweets) plus FinBERT. Identity and exact venue not confirmed. The search summary returned it alongside arXiv 2504.10078, "Unleashing Expert Opinion from Social Media for Stock Prediction" (Zhou et al., cs.CE), which is StockTwits-API based. These two may be the same or different papers [uncertain]; the PDF text was not extractable. [arXiv PDF](https://www.arxiv.org/pdf/2504.10078)
8. Arabesque AI blog on Twitter features (average retweets, retweet ratio per day). The search summary says it explicitly notes a look-ahead problem: features are end-of-day snapshots and likes/retweets keep increasing after posting. This is the only source found that names the issue. It is a company blog, not peer reviewed, and the page now redirects to autocio.com (the deep link returned 404), so I could not read the original wording. Class B, no quantification. [search-snippet only] [Arabesque (archive link)](https://arabesque.com/insights/archive/what-can-twitter-tell-you-about-the-stock-market)
9. Sawhney et al., EMNLP 2020 (MAN-SF), tweets plus company correlation graph on S&P 500. The search summary found no mention of follower/retweet features; full text not checked. Treat as probably text-only [uncertain]. [ACL Anthology](https://aclanthology.org/2020.emnlp-main.676)
10. StockNet (Xu & Cohen, ACL 2018). The preprocessed tweet files carry only text, user_id_str and created_at, per the repo page. No engagement fields; no note on collection timing. Raw tweets are Twitter JSON, which would include counts at collection time [inference; not verified]. Prices cover 2014-01-01 to 2016-01-01, 88 stocks. [GitHub](https://github.com/yumoxu/stocknet-dataset)
11. StockTwits comprehensive records 2008-2022 (Quantitative Description of Digital Media). Abstract page lists poster ID, text, timestamp and user bullish/bearish tag. No mention of likes, reshares or followers, so engagement is apparently not part of it (full data dictionary not read). [journalqd](https://journalqd.org/article/view/8780)
12. PeerJ CS 2023 (StockTwits + FinBERT + SVM) uses rolling windows "to prevent look-ahead bias", but this concerns model validation, not engagement metadata. Class B for general look-ahead, not for engagement. [PeerJ](https://peerj.com/articles/cs-1403)

Dataset engagement-field semantics:
- Reddit financial discussion network datasets (arXiv 2410.05002; GME/AMC/BB; Jun 2020 to Dec 2021). Fields are from/to/time/utc/post.id/comment.id/parent.id/subreddit; no score field. Paper does not state pull date. Re-querying GME post IDs three months apart returned one extra post, i.e. retrieval can change over time. No leakage discussion. [arXiv HTML](https://arxiv.org/html/2410.05002v1)
- SocialGrep r/wallstreetbets Aug 2021 (Hugging Face): loading script has score and created_utc integer fields; scrape date not stated on pages seen. [HF](https://huggingface.co/datasets/SocialGrep/reddit-wallstreetbets-aug-2021/tree/main)
- Temple GameStop Reddit dataset defines score (upvotes plus downvotes combined) and num-comments, with no snapshot timing seen in the snippet. [Temple](https://scholarshare.temple.edu/server/api/core/bitstreams/41222cc7-61af-44b4-b311-a4d05d2c3c9e/content)
- A FinNLP (ACL) paper used a Kaggle corpus of 44,293 WSB posts from Sep 2020 to Mar 2021, and noted that Pushshift was missing a significant amount of data. I could not open the PDF to read score handling. [FinNLP 2021](https://preview.aclanthology.org/author-url/2021.finnlp-1.4.pdf) [search-snippet only]
- Sentdex wsb_reddit_v001 (HF): about 2017-2018 comments "that had at least a few upvotes". This is a selection on final upvotes, itself a potential survivorship/lookahead filter [inference]. [HF](https://huggingface.co/datasets/Sentdex/wsb_reddit_v001)
- Pushshift: per practitioner forum posts, scores are captured once at ingestion and rarely refreshed, so many are near 1, and all scores are "probably off". Anecdotal; no published quantitative study of score drift was found. Pushshift access was cut off, which hurts reproducibility, per a 2026 ACL demo paper. [r/pushshift thread](https://reddit.birdcat.cafe/r/pushshift/comments/zkggt0/update_on_colo_switchover_bug_fixes_reindexing/j1f3fii/?context=3); [ACL 2026 demo](https://aclanthology.org/2026.acl-demo.42.pdf) [search-snippet only]
- FinSen (arXiv 2408.01005): news and market data, 2007-2023, about 160k records; it is a news dataset with FinBERT sentiment, no engagement fields found. FNSPID (2402.06698) is likewise news plus prices. [FinSen](https://arxiv.org/pdf/2408.01005); [FNSPID](https://arxiv.org/abs/2402.06698v1)

### Inferences
- Reddit `score` and Twitter `like_count`/`retweet_count` fetched via API or dumps at some later date are final-ish values that accrue after post time, so any feature built from them at decision time T is look-ahead unless snapshotted. The mechanism is plain, but I found no paper in this set measuring it.
- The widely used benchmarks (StockNet, FinSen, FNSPID, StockTwits records) appear to avoid the issue mostly by not shipping engagement metadata, not by solving it.
- Per-paper timing semantics are mostly undocumented, so most engagement-feature papers are Class A by default; this is a classification from absent documentation, not from reading each paper.

### Gaps
- Full text of items 1, 5, 7 and 9 not read; engagement collection time unknown.
- No systematic survey count (e.g. "N of M papers use engagement") exists; I could not produce a prevalence figure.
- Kaggle WSB dataset column definitions not read.
- Raw StockNet tweet JSON fields not verified.

## Q2. Does any paper discuss or quantify "engagement leakage", "popularity leakage", or temporal leakage of social features? Does the Kapoor & Narayanan taxonomy cover it?

### Takeaway
No paper was found that names or quantifies engagement/popularity leakage in stock prediction. The nearest hits are a company blog (Arabesque, qualitative), general temporal-split warnings, and cascade-prediction literature that handles the same mechanism by design. Kapoor & Narayanan's taxonomy covers the case only implicitly, through L2.

### Cited Findings
- Kapoor & Narayanan (2022/2023) taxonomy has 8 types: L1.1 no test set, L1.2 pre-processing on train+test, L1.3 feature selection on train+test, L1.4 duplicates, L2 features that are not legitimate, L3.1 temporal leakage, L3.2 non-independence, L3.3 sampling bias. L2 is defined as features that would not be available at prediction time (their example is a proxy for the outcome). L3.1 is defined in terms of test data being earlier than training data. Social media engagement was not seen in the first ~100k of 157k characters; the remainder was not read. [arXiv HTML](https://arxiv.org/html/2207.07048v1)
- Searches for "engagement leakage", "popularity leakage", "temporal leakage" + social metrics returned no paper using those terms for stock prediction. Closest: a 2026 NHSJS study of Twitter sentiment under chronological, leakage-free evaluation finding little added value (it attributes earlier strong results to random splits or same-day targets; engagement metadata not addressed). [NHSJS](https://nhsjs.com/2026/evaluating-stock-return-predictability-using-historical-prices-and-twitter-sentiment/)
- A 2025 information-cascade paper describes a "time-travel bias" (random splits let models see future propagation events). This is the closest analogue in the social-media ML literature, but it concerns cascade prediction, not trading. [alphaXiv 2510.25348](https://www.alphaxiv.org/abs/2510.25348)
- Tweet-popularity literature (SEISMIC, KDD 2015; Zaman et al.) deliberately predicts final retweet counts from early observation windows, which is a point-in-time-correct treatment of the same quantity. The searched snippets did not discuss leakage. [SEISMIC](https://arxiv.org/pdf/1506.02594)
- Arabesque blog (see Q1 item 8) is the only explicit statement of the snapshot-timing problem found. [search-snippet only]

### Inferences
- In Kapoor & Narayanan's scheme, final-snapshot engagement is an L2 case (feature not legitimately available at decision time). It is not their L3.1 case, which is about splitting. This distinction is my reading, not theirs, and it may be a useful positioning point: the taxonomy does not name the case, so a new subtype could be defended.
- The gap looks real but unproven: a stronger claim would need a search of Semantic Scholar / ACL Anthology full text, which I could not do.

### Gaps
- Final ~57k characters of Kapoor & Narayanan not read; a social-media example may appear there.
- No Google Scholar / Semantic Scholar full-text search was run.

## Q3. Does any benchmark provide point-in-time snapshots of engagement?

### Takeaway
None found. Datasets either omit engagement (StockNet, StockTwits records, FinSen, FNSPID, Reddit network dataset 2410.05002) or ship a single value with no snapshot time (SocialGrep, Temple GME, Kaggle WSB; Pushshift scores captured at ingestion).

### Cited Findings
- See dataset list under Q1; none documents multiple time-stamped engagement observations per item. [sources above]
- Re-querying the same Reddit posts three months apart changed what was retrieved (one extra post), which shows scrape-time dependence of at least membership. [arXiv 2410.05002](https://arxiv.org/html/2410.05002v1)

### Inferences
- A forward ledger recording engagement at decision time would be new relative to the datasets examined.

### Gaps
- I did not check Kaggle dataset pages directly, TweetFinSent, StockEmotions, or Reddit dumps with periodic re-scrapes.

## Q4. Related LLM look-ahead work: any extension to engagement metadata?

### Takeaway
These papers address model-knowledge look-ahead (what the LLM weights know), not metadata timing. None of the search summaries mention engagement metadata.

### Cited Findings
- Look-Ahead-Bench (arXiv 2601.13770, Benhenda, Jan 2026): measures look-ahead bias in point-in-time LLMs in financial workflows; reports significant look-ahead bias in standard LLMs via alpha decay; compares Llama 3.1 8B/70B and DeepSeek 3.2 against PiT-Inference models. [arXiv](https://arxiv.org/abs/2601.13770v1)
- DatedGPT (arXiv 2603.11838, Yan et al., Mar 2026): twelve 1.3B models with annual cutoffs 2013-2024. [arXiv](https://arxiv.org/abs/2603.11838)
- Chronologically Consistent LLMs (arXiv 2502.21206; authors He, Lv, Manela, Wu, not Kelly): ChronoBERT/ChronoGPT per year since 1999; news-based next-day return test estimates a modest look-ahead bias. [arXiv](https://arxiv.org/pdf/2502.21206)
- Glasserman & Lin (2023) not re-verified in this session.

### Inferences
- Positioning: the LLM line covers the model side of look-ahead; the data-side timing of social engagement metadata appears unaddressed in these papers [based on abstracts only].

### Gaps
- Full texts not read; Glasserman & Lin not checked.
