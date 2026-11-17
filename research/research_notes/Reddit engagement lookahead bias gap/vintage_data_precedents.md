# Vintage / point-in-time data precedents for a social-media engagement look-ahead bias study

Research date: 2026-11-17. Items marked [UNVERIFIED] come from memory or secondary summaries and need checking before citation.

## 1. Classic precedents with quantified effects (macro vintages, Compustat, I/B/E/S, hedge-fund backfill, CRSP delisting)

### Takeaway
The closest methodological template is Ljungqvist, Malloy & Marston (2009, JF): same backtest on different historical downloads of one database, then compare returns. Lyle, Siano & Yohn (2024) do the same for Compustat using Snapshot vintages. Croushore & Stark supply the macro "vintage" framing. Note the sign is not always inflation: LMM find that older I/B/E/S tapes sometimes understate profitability and sometimes overstate it.

### Cited Findings
**Ljungqvist, Malloy & Marston (2009), "Rewriting History," Journal of Finance 64(4):1935-1960**
- Across seven I/B/E/S downloads obtained 2000-2007, between 6,580 (1.6%) and 97,582 (21.7%) of matched observations differ from one download to the next. Changes include altered recommendations, record additions and deletions, and removal of analyst names. — [JF paper PDF (Gwern mirror)](https://www.Gwern.net/doc/statistics/bias/2009-ljungqvist.pdf); [NYU working paper page](https://archive.nyu.edu/handle/2451/27384)
- Changes are nonrandom: they cluster by analyst reputation, broker size and status, and recommendation boldness. They affect trading-signal classifications and backtests of three stylized facts: signal profitability, consensus-change profitability, and analyst persistence. — [JF paper PDF](https://www.Gwern.net/doc/statistics/bias/2009-ljungqvist.pdf)
- 3-day event returns to upgrades average 3.02% on the 2007 tape but 2.30% on the 2004 tape (72 bp, a 31% difference). Downgrades average -4.72% (2007) vs -3.79% (2004), a 93 bp difference. — [JF paper PDF](https://www.Gwern.net/doc/statistics/bias/2009-ljungqvist.pdf)
- Calendar-time abnormal returns: upgrades earn 16.1 bp/day on the adjusted 2007 tape vs 14.8 bp/day on the 2004 tape. The difference is 1.3 bp/day (3.3% annualized) over the full period and 3.6 bp/day (9.1% annualized) post-March 2000. For downgrades the difference is 1.6 bp/day (4% annualized), rising to 4 bp/day (10.1% annualized) post-bubble. In this case the 2004 tape UNDERSTATES profitability. — [JF paper PDF](https://www.Gwern.net/doc/statistics/bias/2009-ljungqvist.pdf)
- The opposite sign also occurs: the consensus-change strategy performs better on the 2003/2004/2005 tapes than on 2002 or 2007 over the identical period, by 1.9-2.1 bp/day (4.8-5.3% annualized). Those tapes overstate profitability by 7.1-7.8% relative to the 2007 tape. The authors describe this as a temporary boost to pre-2001 backtests that vanishes on the 2007 tape. — [JF paper PDF](https://www.Gwern.net/doc/statistics/bias/2009-ljungqvist.pdf)
- Method: a fixed backtest design is re-run on different vintages of the same database over the same sample period, and differences are tested. The effect is measured as difference in calendar-time portfolio returns (including four-factor alphas) and 3-day event returns, and in analyst persistence spreads. — [JF paper PDF](https://www.Gwern.net/doc/statistics/bias/2009-ljungqvist.pdf)
- Thomson Financial began issuing confidential guidance to select clients on May 22, 2007, in reaction to an earlier version of the paper. — [JF paper PDF](https://www.Gwern.net/doc/statistics/bias/2009-ljungqvist.pdf)
- A 2020 Review of Accounting Studies paper reports a much smaller incidence for a different comparison: 0.25% deletions, 4.38% additions, 0.07% value changes. I did not verify which comparison or sample this refers to. — [Springer RAST](https://link.springer.com/article/10.1007/s11142-020-09560-x) [UNVERIFIED; from a search summary]

**Lyle, Siano & Yohn (July 2024), "Re-Standardized Financial Statement Data" (working paper; Emory / UT Dallas)**
- Compustat common products (Annual/Quarterly files) are re-standardized and rewritten each time a new vintage is released. The authors say this "introduces a form of look-ahead bias" and makes precise replication of prior studies "nearly impossible." — [Working paper PDF](https://som.yale.edu/sites/default/files/2024-07/Re-Standardized%20Financial%20Statement%20Data.pdf)
- Method: they use Compustat Snapshot products, which preserve data as it existed at each point in time, and compare. Hedge returns around earnings announcements (high vs low SUE deciles) and for high vs low annual accrual deciles "can differ substantially depending on when the data are accessed." — [Working paper PDF](https://som.yale.edu/sites/default/files/2024-07/Re-Standardized%20Financial%20Statement%20Data.pdf)
- A search summary reported that the sign of earnings flips about 14% of the time. I did not see that figure in the abstract or introduction I read; locate it in the body before citing. — [Working paper PDF](https://som.yale.edu/sites/default/files/2024-07/Re-Standardized%20Financial%20Statement%20Data.pdf) [UNVERIFIED]
- S&P markets a Compustat Point-In-Time database holding originally reported and restated data, and states that mimicking it with custom lags is difficult. This is a vendor claim. — [S&P Global PIT note](https://www.spglobal.com/marketintelligence/en/documents/spgmi687_point-in-time-relevance-for-apac-markets_s.joseph_p-fruin_oct_2019.pdf)

**Croushore & Stark real-time data (macro vintages)**
- Croushore & Stark (2001), "A real-time data set for macroeconomists," Journal of Econometrics 105:111-130. Data set of quarterly "vintages" (snapshots of major US macro series as available in real time), hosted by the Philadelphia Fed. Motivation: analyses based on final revised data may mislead about real-time forecast performance. — [Philadelphia Fed WP 01-10 / search summary](https://www.philadelphiafed.org/-/media/FRBP/Assets/working-papers/2001/wp01-10.pdf?sc_lang=en); [Croushore note](https://facultystaff.richmond.edu/~dcrousho/docs/hef_croushore.pdf)
- Related work (Croushore & Stark, "Forecasting with a real-time data set for macroeconomists," Philadelphia Fed WP 01-10): real-time data matters for some questions (lag length, short-horizon forecasts) but less for others, and RMSE/MAE can look deceptively low when computed against latest-available data. — [EconPapers summary](https://econpapers.repec.org/paper/scescecf1/258.htm); [EconPapers WP 01-10](https://econpapers.repec.org/RePEc:fip:fedpwp:01-10)
- The project began when modelers claimed new models beat the Survey of Professional Forecasters using latest-available data (per Croushore's own description). — [Croushore note](https://facultystaff.richmond.edu/~dcrousho/docs/hef_croushore.pdf)
- Not verified (my fetch of the review failed): Croushore (2011) "Frontiers of Real-Time Data Analysis," Journal of Economic Literature, is the standard survey; Diebold & Rudebusch (1991) on leading indicators and Orphanides (2001) on Taylor rules are canonical examples. I did not retrieve effect sizes. [UNVERIFIED, from memory]

**Hedge-fund database backfill / instant-history bias**
- Fung & Hsieh describe "instant history bias": a vendor records pre-entry returns when a fund joins the database, and these are typically strong because managers join after good performance. Estimates differ: Fung & Hsieh (2000) 1.4%/yr; Barry (2003) 0.4%; Ackermann et al. (1999) found no impact. Backfill periods can run up to ten years. — [Fung & Hsieh 2002 (FAJ) listing](https://ideas.repec.org/a/taf/ufajxx/v58y2002i1p22-34.html); [secondary summary of table](https://ryanoconnellfinance.com/hedge-fund-benchmarks/) [UNVERIFIED figures; secondary source]
- Jorion & Schwarz argue that dropping an initial window of returns leaves most backfill bias in place and propose inferring listing dates. — [Conference paper](https://aeaweb.org/conference/2018/preliminary/paper/NKb6h4BS) [preprint]

**Survivorship / CRSP delisting bias**
- Shumway (1997), JF 52(1):327-340: CRSP lacks delisting returns for most stocks delisted for negative reasons since 1962; omitted returns are large. — [EconPapers](https://econpapers.repec.org/RePEc:bla:jfinan:v:52:y:1997:i:1:p:327-40)
- Shumway & Warther (1999), JF 54(6):2361-2379: for Nasdaq, a corrected return of about -55% for missing performance-related delistings removes the bias; after correction there is no evidence of a size effect on Nasdaq. — [EconPapers](https://econpapers.repec.org/RePEc:bla:jfinan:v:54:y:1999:i:6:p:2361-2379); [Zendy abstract](https://zendy.io/title/10.1111/0022-1082.00192)
- This is a deletion-is-nonrandom precedent: missing items are concentrated in negative outcomes. It is the closest analogue to deleted social posts.

### Inferences
- Template for the paper: (a) fix a signal and backtest pipeline, (b) build two or more vintages of the same underlying data (as-of-time snapshot vs later recollection), (c) report the difference in portfolio return, alpha, Sharpe and event returns, with a significance test, and (d) show the changes are nonrandom (correlated with the signal). LMM and Lyle et al. follow this pattern.
- Bias direction is an empirical question. LMM show revisions can raise or lower measured profitability, so a study should not assume inflation. For engagement, later-collected counts accumulate, and high-engagement posts are the ones that become visible and survive, so inflation is plausible but needs testing.
- Nonrandom deletion (Shumway) and nonrandom editing (LMM) support framing engagement revision as informative, not noise.

### Gaps
- Exact effect sizes from Croushore & Stark and from the Croushore (2011) survey were not retrieved.
- Fung & Hsieh and Barry numbers come from secondary summaries; primary papers not read.
- The 14% Compustat earnings sign-flip figure and the RAST 2020 percentages are not confirmed from the primary text.
- Kothari, Shanken & Sloan (1995) Compustat survivorship was not retrieved.

## 2. Social / alternative-data vendor history revisions (RavenPack, StockTwits, X/Twitter, Reddit, Bloomberg/Refinitiv)

### Takeaway
There is direct evidence that social data erodes after collection, but no paper I found quantifies vendor re-scoring of sentiment history. Deleted-content attrition is well documented for Twitter (up to about 30% within four years) and highly variable for Reddit. Santiment is the one vendor found explicitly documenting revision of social metrics and offering point-in-time versions.

### Cited Findings
**Twitter/X**
- Zubiaga (2018), JASIST 69(8):974-984, recollected 30 Twitter datasets (over 147 million tweets, collected 2012-2016): 81.4% of tweets were still available overall (119,752,714); the share of tweets and unique users can drop below 70% within four years; up to 30% of tweets can disappear within four years. Text content of survivors stayed largely representative, but metadata representativeness declined, partly because fields such as follower counts changed. — [arXiv 1709.09186](https://arxiv.org/pdf/1709.09186.pdf); [arXiv abstract](https://arxiv.org/abs/1709.09186)
- Zubiaga cites earlier work finding 27.3% of a dataset's tweets unavailable within 6 months and about 30% unavailable in another old dataset. — [arXiv 1709.09186](https://arxiv.org/pdf/1709.09186.pdf)
- A 2024 Political Science Research and Methods study ("Nonrandom tweet mortality...") finds sensitive-content datasets are removed at higher rates than nonsensitive ones, and that replicating Kim (2023) gave significantly different results. — [Cambridge Core](https://www.cambridge.org/core/product/17E618F1D395CBBB2360AA424DA5533A)
- X developer documentation: anyone consuming X data via API must use reasonable efforts to honor changes to user content; stored data should reflect the current state of content on X. Batch Compliance returns statuses such as deleted, protected, suspended, scrub_geo; the enterprise Compliance Firehose streams delete, edit, withhold and scrub events and includes tweet_edit events. — [X Batch Compliance docs](https://docs.x.com/x-api/compliance/batch-compliance/introduction); [Compliance Firehose docs](https://docs.x.com/x-api/enterprise-gnip-2.0/fundamentals/firehouse)
- Implication for historical products: compliance obligations mean deleted posts should be purged from stored history. Whether the vendor-delivered "historical" archive is retroactively cleaned is not stated in what I read.

**Reddit / Pushshift**
- Gaffney & Matias (2018), "Caveat Emptor, Computational Social Science": about 0.043% of comments and 0.65% of submissions may be missing from the Pushshift corpus. They say missing IDs are not associated with deleted content. — [ar5iv 1803.05046](https://ar5iv.arxiv.org/html/1803.05046)
- Reagle's analyses (blog, subreddit-specific): 51% of r/relationship_advice submissions in one 2020 sample are now deleted, and 13% of popular non-moderated posts in another sample. Not a Reddit-wide rate. — [Reagle 2020](https://reagle.org/joseph/2020/reddit-deletions.html); [Reagle 2023](https://reagle.org/joseph/pelican/2023/reddit-pushshift-deletion.html) [blog source; moderate reliability]
- Reddit displays fuzzed vote totals; fuzzing and scoring algorithms have changed over time (e.g., the 2016 upvote algorithm change), so a stored score is a noisy, collection-date-dependent value. — [TechCrunch 2016](https://techcrunch.com/2016/12/06/reddit-overhauls-upvote-algorithm-to-thwart-cheaters-and-show-the-sites-true-scale/amp/); [Daily Dot explainer](https://dailydot.com/news/reddit-vote-count-percent-like/) [secondary sources]

**StockTwits**
- Sentiment tags are user-selected (Bullish/Bearish; untagged messages are null). Third-party scrapers state deleted or unavailable content is not exported and a full historical archive is not guaranteed. — [Apify scraper docs](https://apify.com/automation-lab/stocktwits-scraper)
- An academic dataset (Quantitative Finance / Journal of Quantitative Description) claims comprehensive StockTwits records 2008-2022; I did not confirm whether deleted messages are included. — [JQD article](https://journalqd.org/article/view/8780)
- I found no official StockTwits documentation on deleted messages or tag edits.

**RavenPack and other news-sentiment vendors**
- A RavenPack paper on leveraged loans states RavenPack's data is version controlled and no backfilling or historical modification is done (sentence truncated in the snippet). — [RavenPack leveraged loans PDF](https://cdn-static.bizzabo.com/bizzabo.users.files/145245/251725/6341846/Extracting%20Value%20from%20Unstructured%20Big%20Data_%20Leveraged%20Loans%20-%20RavenPack.pdf) [vendor marketing, truncated]
- WRDS describes RavenPack as point-in-time records with sentiment and media-attention scores, 20+ years of history. — [WRDS RavenPack page](https://wrds-www.wharton.upenn.edu/pages/about/data-vendors/ravenpack/)
- Bloomberg/Thomson Reuters/Refinitiv news sentiment point-in-time policy: nothing retrieved.

**Santiment (crypto social data, closest vendor revision documentation)**
- Santiment says social data can change after the fact (scraper gaps, source outages, ML pipeline delays); recomputing history means original metric values change. Its Point-in-Time metrics give an "immutable view" and exclude any document arriving more than 30 minutes after publication; it recommends PIT metrics for backtesting. — [Santiment Academy](https://academy.santiment.net/metrics/details/point_in_time/) [vendor doc]

### Inferences
- Twitter and Reddit attrition studies measure item disappearance, not engagement-count drift. Drift of likes/upvotes is an unquantified gap, and that gap supports the novelty of the proposed study.
- Attrition is nonrandom (sensitive, political, deleted-account content). That parallels LMM and Shumway, and suggests removed posts correlate with the signal.
- Santiment's 30-minute arrival cutoff is a ready-made design precedent for an "as-of" rule.

### Gaps
- No quantification of RavenPack re-scoring rates or of Bloomberg/Refinitiv sentiment revisions.
- No StockTwits primary documentation on deletions or sentiment tag changes.
- No data on how many X historical-API items are retroactively purged versus how many are delivered with stale content.
- The Zubiaga 81.4% figure refers to the whole collection of datasets; per-age breakdown not extracted.

## 3. Does any paper frame engagement metrics (likes, upvotes, retweets) as "revised data" in the vintage sense?

### Takeaway
I found no paper that explicitly frames likes/upvotes/retweets as revised vs unrevised data in the vintage-data sense. The nearest sources are a vendor doc (Santiment) and Zubiaga's finding that metadata such as follower counts change over time.

### Cited Findings
- Santiment's PIT documentation treats social metrics as revisable and recommends vintage-style immutable views. — [Santiment Academy](https://academy.santiment.net/metrics/details/point_in_time/)
- Zubiaga notes that metadata representativity of recollected tweet datasets declined, partly because fields like follower counts changed. — [arXiv 1709.09186](https://arxiv.org/abs/1709.09186)
- ICE's Reddit-signal backtest uses day-T signal only for portfolio construction on T+1 and limits the universe to stocks with at least 60 mentions, which the report says may overstate performance. It does not address engagement-count revision. — [ICE insight](https://www.ice.com/insights/backtesting-a-reddit-derived-strategy-using-ice-signals-and-sentiment-data)
- A 2025 CSCW paper distinguishes likes (low-cost approval) from retweets (stronger endorsement). Not about vintage data. — [arXiv 2509.08128](https://arxiv.org/html/2509.08128v1)

### Inferences
- The gap appears real within this search: the vintage framing (Croushore-style) has not been applied to engagement counts. A claim of novelty should be hedged as "to our knowledge, after a limited search."
- Likes/upvotes are cumulative counters that are mechanically revised upward after posting, unlike macro revisions, which makes a "snapshot at T vs snapshot at T+k" design natural.

### Gaps
- Search was limited (about 15 tool calls). Not checked: Google Scholar / SSRN keyword sweeps ("real-time" "engagement" "look-ahead"), papers on Reddit/WallStreetBets signal studies that discuss score timing, and the Twitter "Love Me Do" likes-and-earnings paper's data timing.

## 4. Methodology used by precedent papers to quantify bias

### Takeaway
Standard design: same fixed model or strategy, run on two data vintages over an identical sample, report differences in return/alpha/error metrics and test significance. Also report the share of records changed and whether changes are nonrandom.

### Cited Findings
- LMM: share of observations changed between downloads (1.6% to 21.7%); characteristics predicting changes; differences in event returns, calendar-time alphas, and persistence spreads between tapes. — [JF paper PDF](https://www.Gwern.net/doc/statistics/bias/2009-ljungqvist.pdf)
- Lyle, Siano & Yohn: compare Compustat Snapshot (as-of) with latest common products for the same firms and recompute hedge-portfolio returns for SUE and accrual deciles. — [Working paper PDF](https://som.yale.edu/sites/default/files/2024-07/Re-Standardized%20Financial%20Statement%20Data.pdf)
- Croushore & Stark: evaluate forecast errors (RMSE, MAE) against real-time vs latest-available data. — [EconPapers summary](https://econpapers.repec.org/paper/scescecf1/258.htm)
- Zubiaga: recollect stored IDs at later dates, compare availability and representativeness of text and metadata. — [arXiv 1709.09186](https://arxiv.org/pdf/1709.09186.pdf)
- Shumway & Warther: impute missing delisting return (-55%) and re-run size-effect tests. — [EconPapers](https://econpapers.repec.org/RePEc:bla:jfinan:v:54:y:1999:i:6:p:2361-2379)

### Inferences
- A study of engagement look-ahead can use: (1) panel of repeated snapshots of the same posts at several delays, (2) signal built from T-snapshot vs final-snapshot engagement, (3) return, alpha and Sharpe differences, (4) test that deletions and count changes correlate with returns (nonrandom selection).

### Gaps
- Sharpe-ratio differences specifically are not reported in the sources read; they used returns, alphas and error metrics.
