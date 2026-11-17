# Counter-example sweep: prior work on look-ahead bias from social-media engagement counts

Date run: 2026-11-17. Tools: WebSearch (standard/extended, some with allowed_domains filters) and WebFetch. 14 search/fetch calls.

## Did any prior paper already measure or document look-ahead bias from engagement counts (upvotes, likes, retweets, followers, page views) in finance or prediction studies?

### Takeaway
No counter-example found. No paper surfaced that (a) studies engagement-count timing for a finance signal or (b) quantifies the bias. Only adjacent work turned up: generic look-ahead literature, LLM look-ahead, cascade-prediction "time-travel bias", and data-persistence bias. Coverage caveat: Semantic Scholar API returned HTTP 429, arXiv API returned 0 hits for one query, and Google Scholar was not directly reachable, so absence is "not found by a web search engine", not an exhaustive proof.

### Cited Findings
Closest finance-side hits (none quantify engagement-count look-ahead):
- Seeking Alpha research (as summarized by SA's editor-in-chief, secondary source): articles that later proved predictive had above-average page views and reads-to-end in first 48h; researchers discounted returns in the first 48h after publication to remove immediate reactions, and tested earnings surprises to rule out platform influence. This is category (b) at most (it treats a timing/reaction issue), but it is a company-sourced summary; the paper itself was not retrieved. — [talkingbiznews](https://talkingbiznews.com/they-talk-biz-news/seeking-alpha-says-most-read-posts-determine-stock-movement/)
- Seeking Alpha's pageview FAQ says real-time alerts affect how many people open articles and thus page views. — [SA FAQ](https://about.seekingalpha.com/pageview-faq)
- Chawla et al. (Notre Dame) track full retweet histories (counts and timing) and link retweet speed to trading intensity; it does not, per the search summary, frame final-vs-early counts as look-ahead. Not opened in full; uncertain. — [chawla2015catching](https://www3.nd.edu/~dial/publications/chawla2015catching.pdf)
- StockTwits-only stock prediction paper lags signals to t-1 and cuts off collection before close to avoid look-ahead; this concerns post timestamps, not engagement-count staleness (abstract-level only). — [arXiv 2504.10078](https://arxiv.org/pdf/2504.10078)
- Engelberg, Hwang, Lu, Mullins, "Giving Users What they Want: Social Media and Anomalies": bullish StockTwits posts on short-leg stocks get more likes. Uses likes as an outcome; no timing-bias discussion seen (abstract-level). — [SSRN 6908458](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6908458)
- Twitter-sentiment paper maps tweets to next trading day to avoid look-ahead; timestamp alignment only. — [NHSJS 2026](https://nhsjs.com/wp-content/uploads/2026/03/Evaluating-Stock-Return-Predictability-Using-Historical-Prices-and-Twitter-Sentiment.pdf)
- ICE backtest of Reddit sentiment uses day-T signal for T+1 portfolio only; no discussion of score snapshots found. — [ICE](https://www.ice.com/insights/backtesting-a-reddit-derived-strategy-using-ice-signals-and-sentiment-data)
- WSB papers (Bradley et al., Li and Li, "In the Red(dit)") surfaced but nothing found on score timing. The "In the Red(dit)" PDF could not be parsed (binary), so its handling of scores is unverified. — [Bradley et al. SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3806065); [Li and Li SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4947010); [arXiv 2311.09252](https://arxiv.org/pdf/2311.09252)

Adjacent work (not about engagement counts, but relevant framing):
- LLM look-ahead bias in sentiment-based return prediction (Glasserman and Lin): knowledge of future returns embedded in the model; category is model-knowledge leakage. — [arXiv 2309.17322](https://arxiv.org/pdf/2309.17322); also [arXiv 2512.23847](https://arxiv.org/pdf/2512.23847)
- Kelly et al., "Scaling Point-in-Time Language Models" (NBER w35247): lookahead as a backtest-validity problem for LLMs; not engagement counts. — [NBER](https://www.nber.org/papers/w35247)
- Peng et al., "Beyond Leakage and Complexity" (arXiv 2510.25348, 29 Oct 2025): defines "time-travel bias" as temporal leakage from random cascade splits (future platform-wide bursts and nested observation/prediction windows). Evidence is a toy synthetic example plus gains on Twitter, Weibo, APS, Taoke under time-ordered splits; it does not measure how much leakage inflated results. Category: adjacent; about train/test splitting, not about engagement counts read after the decision time. — [arXiv HTML](https://arxiv.org/html/2510.25348v1)
- Elmas (WebSci '23), "The Impact of Data Persistence Bias on Social Media Studies": retrospective collection loses deleted/suspended content (turnout about 61% for a control set, 15% to 70% across topic datasets). Does not analyze likes/retweet counts over time; no finance link. — [ar5iv 2303.00902](https://ar5iv.labs.arxiv.org/html/2303.00902)
- 2018 arXiv Twitter stock-stance paper observes users deleting tweets with poor predictions (survivorship mechanism); not quantified for returns. — [arXiv 1804.02233](https://www.arxiv.org/pdf/1804.02233)
- Reddit popularity-prediction literature: scores depend on timing and visibility; Reddit changed score computation; about 40% of recorded interactions in one study lacked a score because Reddit hides new-post scores. Popularity work, not finance. — [arXiv 1703.01725](https://arxiv.org/pdf/1703.01725); [arXiv 1707.00195](https://arxiv.org/pdf/1707.00195); [survey arXiv 1810.10881](https://arxiv.org/pdf/1810.10881)
- Vote-perturbation experiment (Glenski and Weninger, via press): one upvote raised score 11% four days later, showing scores keep drifting post-submission (secondary reporting). — [psmag](https://psmag.com/news/the-impressive-power-of-an-upvote-on-reddit/)
- SMTPD benchmark states prior popularity datasets were retrospective and instead records new posts, checking popularity every 24h (closest to a "vintage" popularity design; abstract-level). — [arXiv 2503.04446](https://arxiv.org/html/2503.04446v1)
- Macro real-time vs revised vintage evidence (Phillips curve ML paper): shows the vintage-data logic in a different domain. — [arXiv 2608.09033](https://arxiv.org/pdf/2608.09033)
- Vendor documentation: Santiment "point-in-time" social metrics (immutable as-known-at-time view for backtesting) is the only source found that treats social metrics as vintage data; it is vendor docs, not research. — [Santiment](https://academy.santiment.net/metrics/details/point_in_time/)
- Pushshift paper says data is collected in real time; no source found stating whether `score` is an ingestion-time snapshot. — [Pushshift paper](https://ojs.aaai.org/index.php/ICWSM/article/view/7347)

Classification of candidate hits: (a) only final/unspecified engagement: Engelberg et al., WSB papers. (b) discusses timing but not engagement-count staleness: SA 48h discount, StockTwits t-1 lag, next-trading-day mapping. (c) quantifies the effect: none found.

### Inferences
- The gap appears real within web-search reach: no paper found that compares early/snapshot vs later/final engagement counts as a signal and measures return-predictability inflation.
- The nearest conceptual precedents are vintage-data practice in macro, Santiment's PIT metrics (vendor), SMTPD's 24h recording, and Peng et al.'s "time-travel bias"; all would be citable as analogies, not as prior work on this exact question.
- Seeking Alpha's 48h discount is the nearest finance precedent and should be read from the original paper before claiming novelty vs it.

### Gaps
- Semantic Scholar API: HTTP 429 (not retried to avoid hammering). arXiv API: one query returned 0 results; arXiv listing search otherwise only via web search.
- Google Scholar, SSRN site search, NBER search, ACL Anthology were not queried directly; only via WebSearch with domain filters (SSRN/NBER/RePEc/arXiv/ACL combined, not individually exhaustive).
- Not opened in full: Chawla et al., Engelberg et al., Seeking Alpha original paper, "In the Red(dit)" (PDF unparsable), Bradley et al. Their treatment of score timing is unverified.
- Pushshift `score` semantics (ingestion snapshot vs updated) unconfirmed.
- Some arXiv ids surfaced by search (2606.27539, 2608.09033) were not independently verified.

## Query log (all run 2026-11-17)
1. WebSearch: "upvotes look-ahead bias Reddit stock returns score snapshot" (no filter)
2. WebSearch: "retweet count look-ahead bias stock prediction engagement measured after posting" (no filter)
3. WebSearch: "point-in-time social media data finance Pushshift score staleness" (no filter)
4. WebSearch: "time-travel bias observation window leakage popularity prediction social media" (no filter)
5. WebFetch: Semantic Scholar API search "look-ahead bias social media engagement stock returns" -> 429
6. WebFetch: export.arxiv.org API all:"look-ahead" AND all:reddit AND all:stock -> 0 results
7. WebSearch: "WallStreetBets upvotes comments score returns predictability look-ahead" (domains: papers.ssrn.com, ssrn.com, nber.org, ideas.repec.org)
8. WebSearch: "StockTwits likes engagement timing look-ahead bias sentiment returns" (domains: ssrn, arxiv, aclanthology, semanticscholar, scholar.google)
9. WebSearch: "Seeking Alpha page views look-ahead bias article readership returns"
10. WebSearch: "deleted tweets survivorship bias stock returns social media backtest"
11. WebSearch: "Reddit score changes after posting vote score time-dependent data collection bias research"
12. WebSearch (extended): "look-ahead bias" social media likes/upvotes/retweets final vs real-time count finance
13. WebFetch: arXiv 2311.09252 (unparsable); arXiv 2510.25348v1 (read); ar5iv 2303.00902 (read)
14. WebSearch: Pushshift score field ingestion time; WebSearch (domains ssrn/nber/repec/arxiv/aclanthology): real-time vs ex post popularity vintage revision
