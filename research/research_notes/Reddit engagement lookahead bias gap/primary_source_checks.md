# Primary-source checks for the Reddit engagement look-ahead literature review

Method: each source was opened directly (GitHub raw markdown, or PDF downloaded and text-extracted). Search-result summaries were not relied on. Quotes are verbatim from the extracted text and under 25 words. Status codes: VERIFIED, PARTLY VERIFIED, CONTRADICTED, COULD NOT VERIFY.

## Claim 1: Arctic Shift 2023-11+ dumps re-fetch at about 36 h and overwrite engagement fields; `_meta` fields

### Takeaway
VERIFIED, with one wording caveat. The Arctic Shift docs say that from 2023-11 onward all content was "retrieved a second time, with a 36 hour delay". `score`, `num_comments`, `upvote_ratio` and other fields are overwritten with the second-fetch values, and `_meta` records later deletion, removal type and edits. The docs do not say the delay is measured "after creation". That reading is plausible, but it is not stated.

### Cited Findings
- File: `file_content_explanations.md`, section "2023-11+". Quote: "All content has been retrieved a second time, with a 36 hour delay. The original and the new content are merged" — [Arctic Shift file_content_explanations.md](https://github.com/ArthurHeitmann/arctic_shift/blob/master/file_content_explanations.md)
- Overwritten fields: "The following fields are updated to the new value:" followed by `archived`, `controversiality`, `downs`, `hide_score`, `locked`, `num_comments`, `num_crossposts`, `over_18`, `score`, `score_hidden`, `spoiler`, `stickied`, `ups`, `upvote_ratio` — [same file](https://github.com/ArthurHeitmann/arctic_shift/blob/master/file_content_explanations.md)
- `_meta` fields: "Any new meta data is stored in the optional `_meta` field". The documented keys are:
  - `_meta.retrieved_2nd_on`
  - `_meta.was_deleted_later`
  - `_meta.was_initially_deleted`, which comes with the `body`/`selftext` being restored
  - `_meta.removal_type`
  - `_meta.is_edited`
  - `_meta.note` = "initially_unavailable"

  Source: [same file](https://github.com/ArthurHeitmann/arctic_shift/blob/master/file_content_explanations.md)
- Section "2023-04+": "`retrieved_on` is added, to indicate when the object was retrieved (UTC timestamp in seconds)" — [same file](https://github.com/ArthurHeitmann/arctic_shift/blob/master/file_content_explanations.md)
- All data comes through the official API: "All data is retrieved through the official reddit API." The modifications do not apply to "the previous pushshift dumps (2023-03 and earlier)" — [same file](https://github.com/ArthurHeitmann/arctic_shift/blob/master/file_content_explanations.md)
- `download_links.md` contains no re-fetch notes. It lists the 2023-11 torrent as "superseded" — [download_links.md](https://github.com/ArthurHeitmann/arctic_shift/blob/master/download_links.md)

### Inferences
- In 2023-11+ Arctic Shift dumps, `score`, `num_comments` and `upvote_ratio` reflect the second fetch, not the first observation. Any engagement feature built from these fields, used to decide at the close of the posting day, carries roughly 36 h of future information unless it is restricted to posts more than 36 h old at decision time.
- The first-fetch values are not retained for the overwritten fields. The docs only list the second-retrieval timestamp in `_meta`. The first-seen engagement therefore cannot be recovered from these dumps.

### Gaps
- The docs do not state the reference point of the "36 hour delay": after `created_utc` or after first retrieval. The value can be checked empirically as `_meta.retrieved_2nd_on - created_utc`.
- `download_links.md` says the 2026-10 release has small JSON schema differences. Their effect on these fields was not checked.

## Claim 2: Pushshift paper (Baumgartner et al. 2020): `retrieved_on` is ingestion time, `score` is as of retrieval, real-time ingestion and later updates

### Takeaway
PARTLY VERIFIED. The paper defines `retrieved_on` as the time Pushshift "crawled" the object, and says the dataset is "updated in real-time". The paper does not say `score` is as of retrieval. It defines `score` only as accumulated upvotes minus downvotes, which Reddit fuzzes. It does not discuss whether scores are re-fetched or updated later. That part of the claim is an inference, not something the paper states.

### Cited Findings
- Submissions table: "retrieved on UNIX timestamp referring to the time we crawled the submission" — [arXiv 2001.08435 PDF](https://arxiv.org/pdf/2001.08435)
- Comments table: "retrieved on UNIX timestamp that refers to the time that we crawled the comment" — [arXiv 2001.08435](https://arxiv.org/pdf/2001.08435)
- Score: "The score that the submission has accumulated. The score is the number of upvotes minus the number of downvotes." Also "NB: Reddit fuzzes the real score to prevent spam bots." — [arXiv 2001.08435](https://arxiv.org/pdf/2001.08435)
- Real time: "Pushshift's Reddit dataset is updated in real-time, and includes historical data back to Reddit's inception." — [arXiv 2001.08435](https://arxiv.org/pdf/2001.08435)
- A full-text search of the paper for "ingest", "update", "later", "snapshot" and "as of" found no statement about re-ingesting objects or updating `score`/`num_comments` after first collection — [arXiv 2001.08435](https://arxiv.org/pdf/2001.08435)

### Inferences
- `score` was captured at crawl time. If crawling was near real-time, early dumps understate final scores. If objects were re-crawled for monthly dumps, `score` reflects a later time. The paper does not say which. The claim "score is as of retrieval" can be cited only as an inference from `retrieved_on`, not as a statement in the paper.

### Gaps
- Pushshift's actual re-ingestion behaviour (for example, dumps built from a later re-crawl) is not documented in this paper. A different primary source would be needed: Pushshift docs, the r/pushshift announcements, or an empirical `retrieved_on - created_utc` distribution.

## Claim 3: Bradley, Hanousek, Jame & Xiao: engagement measured only within a fixed window (for example 24 h) after posting, with returns starting after that window

### Takeaway
CONTRADICTED as stated. No version I could read uses a 24-hour window.
- **2021 working paper:** comments are limited to those posted between the report and the start of the next trading day. Returns start the day after that, with Day 0 excluded.
- **2023 versions, including the 19 Oct 2023 version closest to RFS publication:** the comment-agreement analysis is gone. The only engagement-based step is a sample filter of "more than one upvote". The paper does not state when that upvote count is observed.

### Cited Findings
- **2021 WP comment window:** "We limit the sample to comments that are posted between the publication of the report and the start of the subsequent trading day." — [Jame site, WP 25 Oct 2021](https://russelljame.com/wsb_10_25_2021.pdf)
- **2021 WP rationale:** "This filter helps eliminate comments that are potentially influenced by ex-post returns" — [WP 25 Oct 2021](https://russelljame.com/wsb_10_25_2021.pdf)
- **2021 WP descriptive:** "The average report receives 65 comments between the time of the report and the start of the subsequent trading day" — [WP 25 Oct 2021](https://russelljame.com/wsb_10_25_2021.pdf)
- **2021 WP data source:** they "scrape all posts on WSB ... using the Pushshift API, which collects new posts and comments in almost real-time" — [WP 25 Oct 2021](https://russelljame.com/wsb_10_25_2021.pdf)
- **Upvote filter, 2023 versions (14 Apr 2023 and 19 Oct 2023):** "We limit the sample to posts that have more than one upvote (which is automatic from the user)." — [WP 19 Oct 2023](https://russelljame.com/wsb_10_19_23.pdf); [WP 14 Apr 2023](https://russelljame.com/wsb_4_14_23.pdf)
- **Return timing (19 Oct 2023 version, footnote 13):** reports outside trading hours are dated to the next tradable day. "We exclude the Day [0] return to reduce the impact of potentially confounding news". The return window is [1,5] days — [WP 19 Oct 2023](https://russelljame.com/wsb_10_19_23.pdf)
- **"Comment agreement" dropped later:** the phrase appears 18 times in the 2021 WP and 0 times in the 14 Apr 2023 and 19 Oct 2023 versions. This is a text count on the extracted PDFs — [WP 2021](https://russelljame.com/wsb_10_25_2021.pdf); [WP Oct 2023](https://russelljame.com/wsb_10_19_23.pdf)
- **Published citation:** Review of Financial Studies 37(5): 1409–1459, 2024, DOI 10.1093/rfs/hhad098 — [IDEAS/RePEc](https://ideas.repec.org/a/oup/rfinst/v37y2024i5p1409-1459..html)

### Inferences
- The 2021 WP does apply a point-in-time cut to comment features. The cut ends at the next market open, not at 24 h, and returns start after it. That is a deliberate guard against look-ahead, and it fits the review's framing.
- The >1-upvote filter in the later versions uses a Pushshift `score`/`ups` value whose observation time is not stated. In principle that is a mild survivorship/look-ahead filter. Its impact is probably small, since it mainly removes posts deleted within minutes. That is an inference, not something the authors state.
- A different paper (an Oxford student thesis, Wildi, surfaced by search) reportedly uses a 24-hour cut. I did not open or verify it, so a "24 hours" attribution may come from that source rather than Bradley et al.

### Gaps
- The published RFS text and its Internet Appendix are paywalled and were not read. The 19 Oct 2023 author version is the closest proxy. The final published wording could differ.
- The Mendelu RePEc WP copy (ftp.mendelu.cz) could not be downloaded.

## Claim 4: Ljungqvist, Malloy & Marston 2009, "Rewriting History", JF 64(4)

### Takeaway
VERIFIED, from the published JF version. The range of altered records is 6,580 (1.6%) to 97,582 (21.7%) of matched observations. The headline return difference is 72 bp over 3 days for upgrades between the 2007 and 2004 tapes. Note that the counts differ slightly from the 2006 working paper (6,594 / 97,579 according to a search snippet; not verified). Cite the published numbers.

### Cited Findings
- Abstract: "we find that between 6,580 (1.6%) and 97,582 (21.7%) of matched observations are different from one download to the next." The comparison spans seven downloads, 2000–2007 — [JF 2009 PDF (gwern mirror)](https://gwern.net/doc/statistics/bias/2009-ljungqvist.pdf)
- Types of change: "alterations of recommendations, additions and deletions of records, and removal of analyst names" — [JF 2009](https://gwern.net/doc/statistics/bias/2009-ljungqvist.pdf)
- Headline return figure, upgrades: "3-day event returns to upgrades average 3.02% on the 2007 tape but only 2.30% on the 2004 tape". The paper calls this "a difference of 72 basis points over 3 days and a 31% increase" — [JF 2009, p. 1936](https://gwern.net/doc/statistics/bias/2009-ljungqvist.pdf)
- Downgrades: −4.72% on the 2007 tape vs −3.79% on the 2004 tape, "a difference of 93 basis points and a 24% decrease" — [JF 2009](https://gwern.net/doc/statistics/bias/2009-ljungqvist.pdf)
- Consensus-change strategy: the 2002 tape "yielded 6.2 basis points more per day ... than according to the adjusted 2007 tape (15.6% annualized)" — [JF 2009](https://gwern.net/doc/statistics/bias/2009-ljungqvist.pdf)
- Changes are "nonrandom, clustering by analyst reputation, broker size and status, and recommendation boldness" — [JF 2009](https://gwern.net/doc/statistics/bias/2009-ljungqvist.pdf)

### Inferences
- This is a direct finance precedent for "a vendor's historical record changes after the fact and changes backtests". It is the same mechanism as Arctic Shift overwriting engagement fields.

### Gaps
- The PDF was read from a gwern.net mirror of the published article. The pagination and header match the JF version (vol. LXIV, no. 4, p. 1935), but it was not read from Wiley directly.

## Claim 5: Zubiaga 2018 (JASIST), Twitter dataset persistence

### Takeaway
VERIFIED, from the arXiv version marked "Accepted for publication in JASIST". 81.4% of tweets were still available on recollection, and "up to 30% of the tweets can disappear within four years".

### Cited Findings
- "119,752,714 tweets (81.4% of the whole) were still available." — [arXiv 1709.09186v2](https://arxiv.org/pdf/1709.09186v2)
- "showing that up to 30% of the tweets can disappear within four years." — [arXiv 1709.09186v2, Discussion](https://arxiv.org/pdf/1709.09186v2)
- "The ratio of tweets and unique users available in the recollected dataset can drop below 70% within four years." — [arXiv 1709.09186v2](https://arxiv.org/pdf/1709.09186v2)
- Scope: 30 datasets, more than 147 million tweets, collected 2012–2016 — [arXiv abstract](https://arxiv.org/abs/1709.09186)
- Other elements fared better: hashtags were 86.8% available and URLs 89.8% — [arXiv 1709.09186v2](https://arxiv.org/pdf/1709.09186v2)

### Gaps
- The published JASIST version of record (Wiley) was not opened. The figures come from the accepted-manuscript arXiv v2.

## Claim 6: Gaffney & Matias 2018 (PLOS ONE), missing data in the Baumgartner Reddit corpus

### Takeaway
VERIFIED. 0.043% of comments and 0.65% of submissions are missing across the whole dataset. The paper also reports 36 million missing comments and 28 million missing submissions among "unknown unknowns" in a later period. The gaps are uneven across subreddits.

### Cited Findings
- "Across the entire Baumgartner dataset, only 0.043% and 0.65% of comments and submissions, respectively, are missing." — [PLOS ONE 10.1371/journal.pone.0200162](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0200162)
- Unknown unknowns "now include 36 million missing comments and 28 million missing submissions." — [PLOS ONE](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0200162)
- Risk ranking: "strong risks to research that considers user histories or network analysis, moderate risks to research that compares counts of participation" — [PLOS ONE abstract](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0200162)
- Uneven gaps: "studies on some subreddits could lead towards very biased results due to higher than random amounts of missing data." — [PLOS ONE](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0200162)

### Gaps
- The page was read through a fetch tool that renders the article. The exact period that the 36M/28M "unknown unknowns" figure refers to was reported as after February 2016 but was not pinned to a verbatim sentence. Re-check that sentence before citing the period.

## Claim 7: Kapoor & Narayanan 2023, leakage category for features not legitimately available

### Takeaway
VERIFIED, from the arXiv version. The category is **[L2] "Model uses features that are not legitimate."** It is defined as features that "should not be legitimately available for use in the modeling exercise". The worked example is a feature unavailable "at prediction time". Note that look-ahead in time series is a separate category, [L3.1] "Temporal leakage". The paper lists "[L2] Illegitimate features" as a column in its survey table.

### Cited Findings
- "[L2] Model uses features that are not legitimate. If the model has access to features that should not be legitimately available for use in the modeling exercise" — [arXiv 2207.07048](https://arxiv.org/pdf/2207.07048)
- Example: "the model would not have access to this information when predicting the health outcome for a new patient." — [arXiv 2207.07048](https://arxiv.org/pdf/2207.07048)
- No subcategories, because legitimacy "requires domain knowledge and can be highly problem specific." — [arXiv 2207.07048](https://arxiv.org/pdf/2207.07048)
- The temporal category is separate: "[L3.1] Temporal leakage." The test set should not contain data "from a date before the training set" — [arXiv 2207.07048](https://arxiv.org/pdf/2207.07048)
- The model-info-sheet requirement under L2: researchers must "argue why the feature is legitimate to be used for the modeling task at hand" — [arXiv 2207.07048](https://arxiv.org/pdf/2207.07048)

### Inferences
- Engagement measured after the decision time fits L2 (an illegitimate feature, not available at prediction time) better than L3.1. As defined there, L3.1 is about the train/test split ordering, not about a feature's observation time.

### Gaps
- The Patterns (Cell Press, 2023) version of record was not opened. The quotes are from the arXiv PDF, and the wording may differ slightly in the published version.
