# Reddit archive timing and engagement-count semantics (as of November 2026)

## (a) What do Reddit archive datasets record about WHEN engagement was measured?

### Takeaway
Pushshift records `created_utc` (posting time) and `retrieved_on` (crawl time), and `score` is a snapshot taken at or near the crawl. Pushshift's own paper does not document ingestion delay or later score updates. Arctic Shift (post-2023) does document a second retrieval about 36 hours later that overwrites score and num_comments (from the 2023-11 dumps). So engagement counts in archives are not "values visible at posting time" and their staleness differs by source and period.

### Cited Findings
- Pushshift `retrieved_on` is defined as the "UNIX timestamp referring to the time we crawled the submission" and likewise for comments. `score` is "upvotes minus downvotes", with the note that "Reddit fuzzes the real score to prevent spam bots". `edited` is either an edit timestamp or false. (Quoted from the arXiv preprint; the ICWSM proceedings wording was not checked.) — [Baumgartner et al. 2020, arXiv 2001.08435](https://ar5iv.labs.arxiv.org/html/2001.08435)
- The paper says the dataset is "updated in real-time" and covers June 2005 to April 2019 (651,778,198 submissions; 5,601,331,385 comments; 2,888,885 subreddits). It does not address ingestion delay, later score updates, or deleted content. — [same](https://ar5iv.labs.arxiv.org/html/2001.08435)
- A 2019 r/pushshift FAQ says users can estimate the delay by subtracting `created_utc` from `retrieved_on` and reported about 1 second at that time. It warns that scores and edits "may not reflect what is displayed by reddit". Summarized by a search tool, so exact wording is unverified. — [r/pushshift FAQ, Apr 2019](https://reddit.birdcat.cafe/r/pushshift/comments/bcxguf/new_to_pushshift_read_this_faq/ekubgju/?context=3)
- Reagle: "Pushshift records `score` and `num_comments` at ingest, but updates `num_comments` as it ingests arriving comments", so he treats num_comments as a better popularity proxy. His 2018 sample shows a longest ingest delay of about 21 hours for posts that were deleted by ingest time. A search-tool summary of the same page said 19 hours, so treat the maximum as roughly 19 to 21 hours. — [Reagle 2020](https://reagle.org/joseph/2020/reddit-deletions.html)
- Arctic Shift: "All data is retrieved through the official reddit API". Private and quarantined subreddits are excluded. From the 2023-11 dumps, content was fetched a second time after 36 hours and merged. `score`, `num_comments`, `ups`, `downs` and `upvote_ratio` are updated to the second-fetch values. `retrieved_on` exists from 2023-04 onward, and the second fetch time is in `_meta.retrieved_2nd_on`. — [Arctic Shift file_content_explanations.md](https://github.com/ArthurHeitmann/arctic_shift/blob/master/file_content_explanations.md)
- Arctic Shift flags `_meta.was_deleted_later`, `_meta.was_initially_deleted`, `_meta.removal_type`, `_meta.is_edited` and `_meta.note = "initially_unavailable"`. — [same](https://github.com/ArthurHeitmann/arctic_shift/blob/master/file_content_explanations.md)
- Third-party scraper docs claim recent posts (under 36 hours) in Arctic Shift may have slightly outdated score and num_comments. Latency claims conflict (about 34 seconds vs about 48 hours), and both are third-party. — [search result summary of Apify actors, unverified](https://apify.com/automation-lab/reddit-historical-archive-scraper.md)
- A 2024 to 2025 study using Pushshift-style collection through March 2023 states that "vote counts and other metadata change over time, and these changes are not reflected in this dataset." It says collection delays "were sometimes only a few minutes", so content deleted in that gap can be missed. — [Navigating the Post-API Dilemma, arXiv 2401.15479](https://arxiv.org/html/2401.15479v3)
- Pushshift lost Reddit Data API access on 2023-05-01 and ingestion stopped that day. It returned 2023-06-20 for approved moderators only, with no research access. — [r/modnews May 2023](https://lr.sudovanilla.org/r/modnews/comments/134tjpe/reddit_data_api_update_changes_to_pushshift_access/jiifvfu); [r/pushshift Jun 2023](https://reddit.rtrace.io/r/pushshift/comments/14ei799/pushshift_live_again_and_how_moderators_can)

### Inferences
- For pre-2023 Pushshift data, `score` is most plausibly a near-posting-time snapshot (seconds to hours after creation), so it is a weak proxy for final engagement. This rests on the 2019 FAQ and Reagle's observations and is not stated in the ICWSM paper.
- For Arctic Shift data from late 2023, score is a roughly 36-hour value, so it contains information not available at posting time. This is look-ahead for any signal formed within a day of posting.
- Pushshift-era data and Arctic Shift-era data therefore have different engagement timing, so a study spanning both has a structural break around 2023.

### Gaps
- No primary source found for Pushshift's `retrieved_on - created_utc` distribution across years (only anecdotes of about 1 second in 2019 and up to about 21 hours in Reagle's sample).
- Pushshift's 2023 to 2026 status was not verified beyond a third-party 2026 blog saying it is still moderator-only.
- Arctic Shift behaviour before 2023-11 (second fetch) and the exact `retrieved_on` for pre-2023-04 records were not found.
- The Pushshift architecture documentation (e.g. whether scores were ever re-crawled) was not accessible; the arXiv PDF fetch returned binary.

## (b) How do scores and comment counts evolve, and what about deletions, removals and edits?

### Takeaway
Direct measurements of the fraction of final score reached at 1h or 24h were not found. Related evidence says most activity happens in the first few hours, and that early voting causally shifts final scores. Deletion is substantial in advice subreddits, and archive snapshots at ingest are biased towards pre-deletion content. No finance-subreddit removal rate (e.g. r/wallstreetbets) was found.

### Cited Findings
- Randomized experiment on Reddit: delays of 0 to 60 minutes before applying a rating. Positive early treatments raised final ratings by 11.02% on average. For comments the effect faded at about 1 hour. For posts the effect was still present at 1 hour. Most posts have median final score of 2 or less and most comments get no votes. Final scores were measured 4 days after collection. — [Rating Effects on Social News Posts and Comments, arXiv 1606.06140](https://ar5iv.labs.arxiv.org/html/1606.06140)
- The same paper says Reddit's up/down totals were fuzzed but the net score was certified accurate during the study. In July 2014 Reddit removed vote totals and replaced them with a "semi-accurate points system". — [same](https://ar5iv.labs.arxiv.org/html/1606.06140)
- Reported finding from Weninger et al.: the vast majority of thread activity occurs within the first 4 hours. This comes via a search summary and the primary paper was not opened. — [search summary](https://dejanmarketing.com/wp-content/uploads/2013/10/reddit-paper.pdf)
- Randal Olson (blog, not peer-reviewed) argues the first hours are decisive for reaching the front page. — [Olson 2014](https://www.randalolson.com/2014/03/21/the-window-of-virality-on-reddit/)
- Van Mieghem (2011) models story score as a random walk, fit to about 1.7 million stories. — [IEEE TMM 2011](https://www.nas.ewi.tudelft.nl/people/Piet/papers/IEEE_TMM_redditscore2011.pdf)
- December 2016: Reddit streamlined anti-manipulation rules. New posts showed higher scores afterwards, older posts were recalculated over about a week, comment scores were largely unaffected, and "slight fuzzing" remains. This is a score-level regime change in the middle of many datasets. — [TechCrunch 2016-12-06](https://techcrunch.com/2016/12/06/reddit-overhauls-upvote-algorithm-to-thwart-cheaters-and-show-the-sites-true-scale/amp/)
- Deletion: in r/AmItheAsshole, 6.6% of Apr to Jun 2018 posts were already deleted at Pushshift ingest. 41.0% of an Apr to Jun 2018 sample (n=500) had been deleted by later check. Weekly deletion averaged 22.4% in a Mar to Aug 2020 sample (n=8,500). r/relationship_advice 50.6% and r/Advice 42.4 to 43.6% (n=500 each, 2020 to 2021). — [Reagle 2020](https://reagle.org/joseph/2020/reddit-deletions.html)
- Gaffney and Matias (PLOS ONE 2018): deleted content is included in the Baumgartner corpus and the missing items are not deletions. About 0.043% of comments and 0.65% of submissions missing as of Feb 2016, about 1% missing per month in later months, 78 subreddits with at least 20% of comments missing and 1,755 with at least 20% of submissions missing, gaps clustered around SOPA/PIPA and blackout periods. Their risk ranking: strong for user histories and networks, moderate for participation counts, lesser for ML without representativeness claims. — [Gaffney and Matias 2018](https://ar5iv.arxiv.org/html/1803.05046)
- Post-API study: datasets may lack posts "deleted, edited, or removed by the moderation team or by the user" and spam-filtered items. — [arXiv 2401.15479](https://arxiv.org/html/2401.15479v3)

### Inferences
- Because Pushshift usually ingested within seconds to hours, it likely retains many posts later deleted or removed, which a later re-crawl (Arctic Shift second pass, or the live API) would not. Early snapshot gives survivorship-free content but scores that are low-biased relative to final.
- A re-crawled score (36 hours or more) sits after most early activity (given the first-4-hours finding), so it is nearer to final. Using it as a signal feature for a decision made at posting time is look-ahead.
- Deletion rates for advice subreddits are a loose upper bound; trading subreddits are not measured.

### Gaps
- No study found reporting fraction of final score at 1h, 24h for posts (explicitly searched; only qualitative first-hours results).
- No removal or deletion rate for r/wallstreetbets or other finance subreddits found. Only a Feb 2021 admin post on WSB removal volume (mirror, no rate).
- Reddit comment score hiding window (subreddit setting) was not sourced.
- Edit-rate statistics were not found; only field definitions for `edited`.
- Pushshift ICWSM paper's treatment of staleness: nothing found in it.

## (c) Reddit API rules relevant to time-series snapshots (2026)

### Takeaway
Reddit's primary 2023 announcement gives 100 queries per minute per OAuth client id (10 without OAuth), and free use only for non-commercial purposes. Current-2026 details come from third-party blogs and are unverified.

### Cited Findings
- 100 QPM per OAuth client id, 10 QPM without OAuth; research expected to be exclusively academic and non-commercial, with no redistribution of data or derivatives (per search summary of the 2023 post). — [r/modnews 2023-05-31](https://lr.vern.cc/r/modnews/comments/13wshdp/api_update_continued_access_to_our_api_for/)
- Paid pricing quoted at 24 cents per 1,000 requests (2023 figure); one study estimated 240 USD per 1 million posts. — [arXiv 2401.15479](https://arxiv.org/html/2401.15479v3)
- Third-party 2026 guides claim a free non-commercial tier and commercial pricing around 12,000 USD per month for 50 million calls, plus unauthenticated calls blocked since 2026-05-30. These are single-source claims and unverified. — [Techloy 2026](https://www.techloy.com/reddit-api-pricing-in-2026-complete-guide-for-developers-and-businesses/)

### Inferences
- Snapshotting posts at fixed horizons (e.g. 1h, 24h) is feasible at 100 QPM if the tracked set is small, since each `/api/info` call can look up up to 100 fullnames. That batch size is from general knowledge and was not verified here.
- CLAUDE.md rule 10 (official APIs first, no commercial use) fits the non-commercial terms.

### Gaps
- Reddit's own current Data API Terms and the Data API wiki returned HTTP 403; I could not read the 2026 text directly.
- Whether self-service registration is still open in 2026 is unconfirmed (one blog claims it is closed).
- Data-retention and deletion-compliance obligations were not checked.
