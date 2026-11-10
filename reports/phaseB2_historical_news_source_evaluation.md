# Research Enhancement Track — Phase B2: Historical Financial-News Source Evaluation

**Type:** research and feasibility only. No sentiment analysis, no pipeline, no
dependency, no schema, no model, no dataset and no application change. B3 has not
started.
**Date of research:** 2026-10-12. All web sources were accessed on this date.
**Builds on:** `docs/RESEARCH_ENHANCEMENT_ARCHITECTURE.md` (B0),
`reports/phaseB1_financial_behaviour_inputs_report.md`,
`reports/phaseB1V_verification_report.md` (B1 accepted).

**Labels used** (as in the B0 document): **[VERIFIED]** confirmed from official
documentation, the repository, or a direct observation made in this phase;
**[UNVERIFIED]** not confirmed from a primary source; **[MISSING]** not available;
**[PROPOSED]** a recommendation awaiting your approval; **[FUTURE]** work for a
later, separately approved phase.

> **Superseded in part by Phase B2-F (2026-10-12):**
> `reports/phaseB2F_gdelt_acquisition_feasibility.md`. This report is kept as
> written; four points changed.
>
> 1. **Window dates.** The dates in sections 1–3 and 6 were mapped onto price
>    dates. `training/market/train.py` builds its windows over returns, so test
>    returns run 2024-01-16 → 2026-07-21. 2024-01-12 and 2026-07-20 are the
>    forecast origins, so the news window ending 2026-07-20 still holds.
> 2. **GDELT coverage.** GDELT does not cover the whole window: no GDELT 2.0
>    files exist from 2025-06-14 18:00 to 2025-07-02 02:00 UTC.
> 3. **BigQuery.** It does not strictly need billing: the sandbox needs only a
>    Google account and a Cloud project.
> 4. **Volume.** "About 1 TB" of raw English data is refined to ≈0.90 TB.

---

## 1. Executive summary

**Decision: CONDITIONALLY RECOMMENDED — the GDELT 2.0 Global Knowledge Graph
(GKG), for a market-level experiment.** Nothing is approved; this awaits your
decision.

GDELT is the only candidate that satisfies all four hard requirements with
primary-source evidence:

1. **Coverage:** its 15-minute files exist across the whole window the existing
   walk-forward design needs. The start (2022-01-03), first test day (2024-01-12),
   last test day (2026-07-20) and last market date (2026-09-11) were all checked
   directly.
2. **Leakage-safe timestamps:** a single UTC batch time per file marks when each
   record became available.
3. **Licence:** "unlimited and unrestricted use for any academic, commercial, or
   governmental use … without fee", with redistribution permitted given citation.
4. **Reproducibility:** immutable dated files with published MD5 checksums.

The conditions are real, though:

- **Market-level only.** GDELT is general global news. It supports US
  equity/Nasdaq, interest-rate/bond and gold-price sentiment at the market or
  asset-class level. It does **not** support ticker-level analysis of QQQ, AGG or
  GLD: in the samples, those tickers never appeared.
- **Volume.** The full raw English stream for the window is on the order of 1 TB
  compressed (the translated stream roughly doubles it). It must be streamed and
  filtered, or queried through Google BigQuery, which needs an account and has a
  cost that could not be verified.
- **Your decisions are needed** on scope, acquisition route and storage (section 11).

**Secondary, for instrument-level analysis:** Benzinga news has explicit immutable
`created` and mutable `updated` timestamps, ticker tags, full text and history from
2009 (Massive partner feed) or 2015 (Alpaca). It is reachable free through Alpaca
or at $99/month through Massive. It is **conditionally recommended only if the
provider confirms in writing** that an individual's academic, non-commercial
research may store the retrieved items for the project and publish aggregate
results. Both providers' terms restrict use to personal and non-commercial purposes
and prohibit redistribution, and neither addresses research or derived results.

**Not suitable:**

- **Coverage ends before the test period:** FNSPID (ends 2023), NIFTY (ends
  2020-09) and the other academic corpora found.
- **Only 3 months of history:** GDELT's DOC search API, and Tiingo on individual
  plans.
- **Finnhub:** 1 year of history on the free tier; its terms require deleting data
  when the subscription ends and forbid sharing "derived results" without written
  approval.
- **NewsAPI.org:** $449/month, general news, and a rolling 5-year window.
- **Unverified start date or terms:** Alpha Vantage.
- **Impractical at this scale:** Common Crawl News, given its size and the
  third-party copyright in full text.
- **Financial PhraseBank** is not a time series. It is a candidate validation
  corpus for B3's classifier, licensed CC BY-NC-SA 3.0.

---

## 2. Research questions and minimum requirements

The source must support RQ1/RQ2 from B0: does news sentiment add predictive
information beyond market features, on a chronological, leakage-safe evaluation?

| # | Requirement | Why |
| --- | --- | --- |
| R1 | Continuous coverage from **2021-12-01** (lookback for the first features) to **2026-07-20** (last test day), ideally to 2026-09-11 | The existing walk-forward trains from 2022-01-03 and tests 2024-01-12 → 2026-07-20 (section 3) |
| R2 | A first-availability timestamp with a known timezone, distinct from any update time | Only news available before the cutoff may be used |
| R3 | Historical records retrievable again, or storable as a frozen, auditable snapshot | The experiment must be reconstructable |
| R4 | A licence permitting academic research, local storage, retention of derived features, and publication of aggregate results without the source text | Results must be publishable |
| R5 | Plausible mapping to the five instruments, at least at market/asset-class level | Sentiment must relate to what is predicted |
| R6 | Feasible within an M.Tech budget and laptop, without changing existing pipelines | Project constraint |

---

## 3. Existing market-data coverage (verified from the repository)

Read from the development database (`market_data`, read-only) and
`training/market/common.py` on 2026-10-12. **[VERIFIED]**

| Item | Value |
| --- | --- |
| Instruments | `^IXIC`, `^NDX`, `QQQ`, `AGG`, `GLD` (`INSTRUMENTS` in `training/market/common.py`) |
| Source | yfinance 0.2.66, fetched from `DATA_START = "2022-01-01"` |
| Stored range (each instrument) | **2022-01-03 → 2026-09-11**, 1,177 trading days, no gap over 4 calendar days, no missing volume, last loaded 2026-09-13/14 |
| Walk-forward | expanding window, 504 initial training days, 5-day embargo, 63-day test windows, 10 windows, 1-day horizon |
| Calendar dates of the windows | first training window 2022-01-03 → 2024-01-04; **first test day 2024-01-12; last test day 2026-07-20**; 38 trailing days unused |

The market-data acquisition code was not changed and the database was only read.

---

## 4. Candidate comparison

Fifteen candidates were assessed: twelve historical-news sources, two academic
corpora that turned out too short, and one labelled validation corpus. The tables
are split by theme; the rows are the same in each table.

### 4.1 Identity, type, coverage and access

| # | Candidate | Official source | Type | Earliest | Latest | Historical access on available plan |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | **GDELT 2.0 GKG** (raw files) | gdeltproject.org; data.gdeltproject.org/gdeltv2/ | Open downloadable dataset (15-min files); BigQuery mirror | Feb 2015 [VERIFIED codebook/blog]; files at 2022-01-03 present [VERIFIED HEAD] | Live: batch 2026-10-12 17:15 UTC [VERIFIED] | **Yes, free, no account** [VERIFIED by download of samples] |
| 2 | GDELT DOC 2.0 API | blog.gdeltproject.org (DOC 2.0 API) | Search/timeline API | Contradictory: "back to January 1, 2017" vs "must be within the last 3 months" [VERIFIED quotes, conflicting] | Live | Rolling 3-month window per the parameter rules → **No** for 2022–2024 |
| 3 | **Benzinga via Massive** (`/benzinga/v2/news`) | massive.com/docs/rest/partners/benzinga/news | Commercial API (partner feed) | **2009-04-27** [VERIFIED docs] | Live | Paid: "Benzinga News (Individual)", **$99/month per dataset** [VERIFIED pricing] |
| 4 | Massive Stocks news (`/v2/reference/news`) | massive.com/docs/rest/stocks/news | Commercial API | **2016-06-22** on Starter+ [VERIFIED docs] | Live (updated hourly) | Basic (free): 2 years → reaches only ~2024-10 [VERIFIED]; **Starter $29/month** for full history [VERIFIED] |
| 5 | **Alpaca News API** (Benzinga) | docs.alpaca.markets (historical news data); alpaca.markets blog 2022-02-07 | Brokerage data API | **2015** [VERIFIED docs + blog] | Live | **Free** with an Alpaca account, 200 calls/min on the free plan [VERIFIED blog, 2022; current status UNVERIFIED — the blog warned pricing may change] |
| 6 | Benzinga direct (`/api/v2/news`) | docs.benzinga.com | Commercial API | Not published [UNVERIFIED] | Live | Contact sales; trial keys mentioned [VERIFIED FAQ]; price [UNVERIFIED] |
| 7 | Finnhub company/market news | finnhub.io (API specification) | Commercial API | Free tier: "1 year of historical news" [VERIFIED spec] | Live | Free: 1 year only → **No**; premium depth/price [UNVERIFIED — pricing page did not render] |
| 8 | Alpha Vantage `NEWS_SENTIMENT` | alphavantage.co/documentation | Commercial API | Not documented [UNVERIFIED] | Live | "This is a premium API function" [VERIFIED]; from $49.99/month [VERIFIED] |
| 9 | EODHD Financial News API | eodhd.com/financial-apis/stock-market-financial-news-api | Commercial API | Free plan: past year [VERIFIED]; paid depth not published [UNVERIFIED] | Live | Paid $19.99–$99.99/month [VERIFIED]; 2022 coverage [UNVERIFIED] |
| 10 | Tiingo News API | tiingo.com/documentation/news | Commercial API | "up to 15 years" for commercial clients on request [VERIFIED] | Live | Individual plans: "3 Months of queryable history" → **No** [VERIFIED] |
| 11 | NewsAPI.org | newsapi.org/pricing | Commercial API (general news) | Business/Advanced: "up to 5 years old" (rolling) [VERIFIED] | Live | Business $449/month [VERIFIED]; Developer plan 1 month, development only [VERIFIED] |
| 12 | Common Crawl CC-NEWS | commoncrawl.org (news dataset) | Open web-crawl archive (WARC) | Oct 2016 [VERIFIED blog] | Daily [VERIFIED] | Free on AWS S3 [VERIFIED]; very large [UNVERIFIED size] |
| 13 | FNSPID (Dong et al., KDD 2024) | huggingface.co/datasets/Zihan1004/FNSPID; GitHub Zdong104 | Academic corpus | 1999 [VERIFIED] | **2023** [VERIFIED] | Downloadable, 29.6 GB [VERIFIED]; **misses the entire test period** |
| 14 | NIFTY headlines (Saqur et al.) | huggingface.co/datasets/raeidsaqur/NIFTY | Academic corpus | 2010-01-06 [VERIFIED] | **2020-09-21** [VERIFIED] | Downloadable; misses the whole window |
| 15 | Financial PhraseBank (Malo et al. 2014) | huggingface.co/datasets/takala/financial_phrasebank | Labelled sentence corpus | n/a (no dates) | n/a | Downloadable; **not a time series** |

Also seen and rejected without a full row: a Hugging Face S&P 500 news set
(KrossKinetic) with only 4,589 CNBC articles across 2007–2024 (too sparse; MIT
label over third-party text). The `zhihangliu/alphavantage_financial_sentiment_news`
set was not evaluated further, because it appears to redistribute a commercial
API's content, which raises licensing doubts.

### 4.2 Timestamps, text and reproducibility

| # | Candidate | Publication timestamp | Timezone | Publication vs update distinguished | Headline / text | Reproducible retrieval |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | GDELT GKG | `V2.1DATE`: the 15-min batch time, "the same for all rows in a file" [VERIFIED codebook + 2 samples]; page-declared `PAGE_PRECISEPUBTIMESTAMP` on 46–60% of rows [VERIFIED samples] | UTC [VERIFIED: latest batch name matched UTC clock; inferred for history] | Batch time is first availability; no update concept; files append-only [inferred] | **Page title on 100% of rows** in the 2024 sample (median 66 chars) [VERIFIED]; URL; no article body [VERIFIED codebook] | **Yes**: immutable dated files with MD5 in `lastupdate.txt`/master list [VERIFIED format] |
| 2 | GDELT DOC API | Article "seen" date | Not stated [UNVERIFIED] | No | Titles + URLs, no text [VERIFIED] | No (search index, rolling window) |
| 3 | Benzinga via Massive | `published` ISO 8601 with `Z` [VERIFIED] | UTC [VERIFIED] | **Yes**: `published` and `last_updated` [VERIFIED] | Headline + **full body** [VERIFIED] | Provider-controlled; articles can change → snapshot needed |
| 4 | Massive Stocks news | `published_utc` RFC 3339 [VERIFIED] | UTC [VERIFIED] | No update field listed [VERIFIED absence] | Title + description, no body [VERIFIED] | Provider-controlled |
| 5 | Alpaca (Benzinga) | `created_at` RFC 3339 [VERIFIED] | Offset in RFC 3339 [VERIFIED format; zone not stated] | **Yes**: `created_at` and `updated_at` [VERIFIED] | Headline, summary, **full content** optional [VERIFIED] | Provider-controlled; snapshot needed |
| 6 | Benzinga direct | `created`: "This timestamp will not change" [VERIFIED] | RFC 2822 with offset; documented as "GMT-4 (EDT)" [VERIFIED] | **Yes**: `updated` "has the ability to change one or many times" [VERIFIED] | Headline/abstract/full [VERIFIED] | Provider-controlled |
| 7 | Finnhub | `datetime` Unix [VERIFIED] | UTC (Unix epoch) [VERIFIED] | No [VERIFIED absence] | Headline + summary [VERIFIED] | Data must be deleted when the subscription ends [VERIFIED ToS] → **not reproducible** |
| 8 | Alpha Vantage | `time_published` [UNVERIFIED format/zone] | [UNVERIFIED] | No [UNVERIFIED] | Title + summary + provider sentiment [VERIFIED summary] | Provider-controlled |
| 9 | EODHD | `date` ISO 8601 [VERIFIED] | [UNVERIFIED] | No [UNVERIFIED] | **Full content** + provider sentiment [VERIFIED] | Provider-controlled |
| 10 | Tiingo | `publishedDate` UTC and `crawlDate` UTC ("added to our database") [VERIFIED] | UTC [VERIFIED] | Crawl time = a genuine first-seen time [VERIFIED] | Title + description, no body [VERIFIED] | Provider-controlled |
| 11 | NewsAPI.org | `publishedAt` [UNVERIFIED here] | [UNVERIFIED] | No [UNVERIFIED] | Headline/description; content truncation [UNVERIFIED] | Rolling 5-year window shrinks the past over time |
| 12 | Common Crawl CC-NEWS | Crawl time in WARC; publication time only if parsed from HTML [UNVERIFIED reliability] | UTC (WARC) [inferred] | Crawl time = first-seen time | **Full HTML** | Yes (immutable WARC files) [inferred] |
| 13 | FNSPID | `Date` [VERIFIED column]; precision/zone [UNVERIFIED] | [UNVERIFIED] | No | Title + full article + summaries [VERIFIED columns] | Static file |
| 14 | NIFTY | Daily [VERIFIED] | n/a | No | Headlines [VERIFIED] | Static file |
| 15 | Financial PhraseBank | None [VERIFIED] | n/a | n/a | Labelled sentences | Static file |

### 4.3 Licensing, storage and pricing

| # | Candidate | Academic research permitted | Local storage | Derived scores retained / results published | Redistribution | Pricing / limits |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | GDELT | **Yes**: "unlimited and unrestricted use for any academic, commercial, or governmental use … without fee" [VERIFIED] | Yes (implied by unrestricted use) [VERIFIED] | Yes [VERIFIED] | "may redistribute, rehost, republish … must include a citation to the GDELT Project and a link" [VERIFIED] | Free [VERIFIED]; BigQuery route needs a Google Cloud account; cost [UNVERIFIED] |
| 2 | GDELT DOC API | Yes (GDELT terms) | — | — | With citation | Free |
| 3 | Benzinga via Massive | Not addressed; individual terms: "solely for your own personal, non-commercial, and non-business purposes" [VERIFIED] → **[UNVERIFIED] for an academic project** | Not addressed [VERIFIED absence] | Terms forbid "derivative works based on the Services or the technology" — scope for derived features unclear [VERIFIED quote, interpretation UNVERIFIED] | Prohibited [VERIFIED] | $99/month per dataset [VERIFIED] |
| 4 | Massive Stocks news | Same as #3 [VERIFIED] | Not addressed | Same as #3 | Prohibited | Free Basic (5 calls/min, 2 years); Starter $29/month [VERIFIED]; "Non-pros only" [VERIFIED] |
| 5 | Alpaca | "solely for your own personal and non-commercial purposes" [VERIFIED via official T&C search result]; research not addressed [UNVERIFIED] | Not addressed [UNVERIFIED] | Not addressed [UNVERIFIED] | "you cannot redistribute Alpaca API data" [VERIFIED] | Free (2022 statement) [VERIFIED blog; current UNVERIFIED]; requires an Alpaca account |
| 6 | Benzinga direct | Negotiated [UNVERIFIED] | Negotiated | Negotiated | Negotiated | Contact sales [VERIFIED] |
| 7 | Finnhub | "strictly for personal use unless explicitly stated otherwise" [VERIFIED] | "All data must be deleted should your subscription to that data ends" [VERIFIED] | **"not redistribute or share … derived results from the data … without written approval"** [VERIFIED] | Prohibited [VERIFIED] | Free tier; premium price [UNVERIFIED] |
| 8 | Alpha Vantage | Secondary summaries say personal, non-commercial unless agreed in writing [UNVERIFIED — official terms PDF could not be read] | [UNVERIFIED] | [UNVERIFIED] | [UNVERIFIED] | $49.99–$249.99/month [VERIFIED]; free tier 25 requests/day, but news is premium-only [VERIFIED] |
| 9 | EODHD | No academic exemption; "Universities & Academic Research licensing" sold separately [VERIFIED] | "permitted to store, manipulate, and analyze the data for private, non-commercial purposes" [VERIFIED] | Private analysis allowed; sharing prohibited [VERIFIED] | Prohibited [VERIFIED] | $19.99–$99.99/month; news costs 5 API calls per request [VERIFIED] |
| 10 | Tiingo | Individual plans: "Internal use … only for your own personal use" [VERIFIED] | Internal only | Internal only | Prohibited [VERIFIED] | Power $30/month individual; $50 commercial [VERIFIED]; history beyond 3 months needs a commercial agreement |
| 11 | NewsAPI.org | Developer plan: "development and testing … only" [VERIFIED]; research not addressed | Not addressed [VERIFIED absence] | Not addressed | No reproducing/republishing copyrighted material [VERIFIED] | $449/month for 5-year history [VERIFIED] |
| 12 | Common Crawl | Use for lawful research purposes [VERIFIED]; **no rights to underlying content** [VERIFIED] | Allowed by Common Crawl; publisher copyright applies to full text [VERIFIED] | Aggregates likely fine; raw text not redistributable [interpretation] | Must respect third-party rights [VERIFIED] | Free; storage/compute heavy |
| 13 | FNSPID | HF card: **CC BY-NC 4.0** [VERIFIED]; README (2025-07-24) "released all the right for commercial use and research use" [VERIFIED]; articles scraped from Nasdaq.com → publishers' copyright [VERIFIED README] → **[UNVERIFIED] overall** | — | — | — | Free |
| 14 | NIFTY | MIT [VERIFIED] | Yes | Yes | Yes | Free |
| 15 | Financial PhraseBank | CC BY-NC-SA 3.0 [VERIFIED] → non-commercial academic use permitted; share-alike on derivatives | Yes | Yes (non-commercial) | Share-alike | Free |

### 4.4 Relevance, limitations and verdict

| # | Candidate | Geography / asset coverage | Alignment with the five instruments | Main limitations | Verdict |
| --- | --- | --- | --- | --- | --- |
| 1 | **GDELT GKG** | Global news, 65 translated languages [VERIFIED]; finance themes present (`ECON_STOCKMARKET`, `ECON_INTEREST_RATES`, `ECON_CENTRALBANK`, `ECON_INFLATION`, `ECON_GOLDPRICE`) [VERIFIED samples] | Market-level: equity/Nasdaq yes; rates/bonds yes; gold yes (`ECON_GOLDPRICE`, title keywords). **Ticker-level: no** (QQQ/GLD/AGG absent from names and URLs in samples) [VERIFIED] | General news, noisy; lexicon tone, not finance-tuned; about 1 TB raw for the window; source mix changes over time; titles but no bodies | **CONDITIONALLY RECOMMENDED** (primary, market-level) |
| 2 | GDELT DOC API | Global | Market-level | 3-month rolling window; not an archive | NOT SUITABLE (historical) |
| 3 | **Benzinga via Massive** | US-focused financial news, tickers, channels [VERIFIED "tickers, categories"] | Ticker-level likely for stocks; **ETF (QQQ/GLD/AGG) tagging [UNVERIFIED]**; indices only via constituents | Licence ambiguity for academic use and derived features; retail-focused editorial selection; needs snapshotting | **CONDITIONALLY RECOMMENDED** (secondary, instrument-level), pending written licence confirmation |
| 4 | Massive Stocks news | Multi-publisher, ticker-tagged [VERIFIED] | Ticker-level for stocks; ETFs [UNVERIFIED] | No update timestamp; no body; provider "insights" sentiment of unknown computation date (look-ahead risk); same licence ambiguity; per-plan history statements differ | CONDITIONAL (lower than #3) |
| 5 | **Alpaca (Benzinga)** | Same content family as #3 | As #3 | Personal/non-commercial terms; free status dated 2022; account required | **CONDITIONALLY RECOMMENDED** (free route to #3's content), pending written confirmation |
| 6 | Benzinga direct | As #3 | As #3 | Unpublished price/depth; negotiation required | Not assessable without contacting the provider |
| 7 | Finnhub | North American companies only [VERIFIED] | Companies, not ETFs/indices [UNVERIFIED for ETFs] | 1-year free history; mandatory deletion; derived-results sharing needs approval | **NOT SUITABLE** |
| 8 | Alpha Vantage | Global, tickers + topics [VERIFIED] | Tickers + "financial markets" / "economy" topics | Start date unknown; premium; terms unread; provider sentiment of unknown provenance | **NOT SUITABLE** (unverified coverage and terms) |
| 9 | EODHD | Global stocks/ETFs [VERIFIED] | Ticker incl. ETFs (claimed) [UNVERIFIED for history] | Paid-plan depth unpublished; academic licence separate | UNVERIFIED (would need written confirmation of 2022 coverage and licence) |
| 10 | Tiingo | Financial news + blogs [VERIFIED] | Tickers + tags | 3-month history for individuals | **NOT SUITABLE** (without a commercial contract) |
| 11 | NewsAPI.org | General news | Keyword-only | Cost; not finance-specific; rolling window will soon drop early 2022 | **NOT SUITABLE** |
| 12 | Common Crawl CC-NEWS | Global web news | Keyword-only | Terabytes; HTML parsing; publisher copyright in stored text | NOT SUITABLE for this project's scale |
| 13 | FNSPID | 4,775 S&P 500 companies [VERIFIED] | Company-level | **Ends 2023**: no test-period coverage; licence conflict | **NOT SUITABLE** (for the existing evaluation window) |
| 14 | NIFTY | SPY-aligned headlines | Market-level | Ends 2020-09 | **NOT SUITABLE** |
| 15 | Financial PhraseBank | Finnish-company news sentences | n/a | No dates | Not a source; **candidate for B3 classifier validation** |

---

## 5. Evidence and official links

| Claim | Source (official unless stated) |
| --- | --- |
| GDELT terms: unlimited academic/commercial use, redistribution with citation | <https://www.gdeltproject.org/about.html> (Terms of Use) |
| GKG 2.1 fields: `V2.1DATE` batch time, record ID, URL identifier, tone definition | GKG Codebook V2.1, <http://data.gdeltproject.org/documentation/GDELT-Global_Knowledge_Graph_Codebook-V2.1.pdf> (text extracted locally with the standard library) |
| GDELT files exist at 2022-01-03, 2024-01-12, 2026-07-20, 2026-09-11; sizes 2.6–8.7 MB; translation stream exists | Direct HEAD requests to <https://data.gdeltproject.org/gdeltv2/> (2026-10-12) |
| GDELT batch names are UTC | `lastupdate.txt` batch `20261012171500` compared with the UTC clock `20261012171234` |
| GDELT DOC API window statements | <https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/> |
| GDELT partitioned BigQuery tables | <https://blog.gdeltproject.org/announcing-partitioned-gdelt-bigquery-tables/> |
| Benzinga via Massive: endpoint, history from 2009-04-27, `published`/`last_updated`, body | <https://massive.com/docs/rest/partners/benzinga/news> |
| Massive partner price $99/month per dataset | <https://massive.com/pricing> (partner data) |
| Massive Stocks news: `published_utc`, history from 2016-06-22 on Starter+, Basic 2 years | <https://massive.com/docs/rest/stocks/news> ; <https://massive.com/pricing> |
| Massive individual terms | <https://massive.com/legal/individuals-terms-of-service> |
| Alpaca news from Benzinga, back to 2015 | <https://docs.alpaca.markets/docs/historical-news-data> |
| Alpaca news fields and limits | <https://docs.alpaca.markets/reference/news-3> |
| Alpaca news free, 200 calls/min, full-length articles | <https://alpaca.markets/blog/introducing-news-api-for-real-time-fiancial-news/> (2022-02-07) |
| Alpaca: no redistribution; personal/non-commercial | <https://alpaca.markets/support/redistribute-alpaca-api> ; <https://files.alpaca.markets/disclosures/library/TermsAndConditions.pdf> (via official-domain search result) |
| Benzinga `created`/`updated` semantics, parameters | <https://docs.benzinga.com/api-reference/news-api/get-news-items.md> |
| Finnhub coverage, 1-year free history, fields | <https://finnhub.io/static/swagger.json> |
| Finnhub terms (personal use, deletion, derived results) | <https://finnhub.io/terms-of-service> |
| Alpha Vantage `NEWS_SENTIMENT` is premium; parameters | <https://www.alphavantage.co/documentation/> |
| Alpha Vantage prices | <https://www.alphavantage.co/premium/> |
| EODHD news API, plans, terms | <https://eodhd.com/financial-apis/stock-market-financial-news-api> ; <https://eodhd.com/pricing> ; <https://eodhd.com/financial-apis/terms-conditions> |
| Tiingo fields, history, internal use | <https://www.tiingo.com/documentation/news> ; <https://www.tiingo.com/about/pricing> |
| NewsAPI plans and terms | <https://newsapi.org/pricing> ; <https://newsapi.org/terms> |
| Common Crawl News and terms | <https://commoncrawl.org/blog/news-dataset-available> ; <https://commoncrawl.org/terms-of-use> |
| FNSPID | <https://huggingface.co/datasets/Zihan1004/FNSPID> ; <https://github.com/Zdong104/FNSPID_Financial_News_Dataset> ; arXiv 2402.06698 |
| NIFTY | <https://huggingface.co/datasets/raeidsaqur/NIFTY> |
| Financial PhraseBank | <https://huggingface.co/datasets/takala/financial_phrasebank> |

**Inaccessible or unreadable:**

- **Finnhub:** the pricing and documentation pages render client-side, so plan
  prices and premium history stay unverified. Coverage facts came from Finnhub's
  own API specification instead.
- **Alpha Vantage terms:** the PDF could not be parsed with available tools.
- **Google BigQuery pricing:** the page content was truncated.
- **Alpaca market-data page:** it did not mention news, so the current free status
  rests on the 2022 announcement.
- **Benzinga OpenAPI spec:** URL returned 404.

---

## 6. Historical coverage analysis

| Candidate | 2021-12 lookback | Training 2022-01 → 2024-01 | Test 2024-01-12 → 2026-07-20 | Tail to 2026-09-11 |
| --- | --- | --- | --- | --- |
| GDELT GKG | ✔ [VERIFIED files] | ✔ | ✔ | ✔ |
| Benzinga via Massive | ✔ [VERIFIED depth to 2009] | ✔ | ✔ | ✔ |
| Alpaca (Benzinga) | ✔ [VERIFIED depth to 2015] | ✔ | ✔ | ✔ |
| Massive Stocks news (Starter) | ✔ [VERIFIED depth to 2016] | ✔ | ✔ | ✔ |
| Massive Stocks news (free Basic) | ✘ (2 years ≈ from 2024-10) | ✘ | partial | ✔ |
| Finnhub (free) | ✘ (1 year) | ✘ | partial | ✔ |
| Tiingo (individual) | ✘ (3 months) | ✘ | ✘ | partial |
| NewsAPI Business | ✔ today (5-year window ≈ from 2021-10) — drops early 2022 by early 2027 | ✔ (temporarily) | ✔ | ✔ |
| Alpha Vantage, EODHD, Benzinga direct | [UNVERIFIED] | [UNVERIFIED] | [UNVERIFIED] | likely ✔ |
| FNSPID | ✔ | ✔ | **✘** | ✘ |
| NIFTY | ✘ | ✘ | ✘ | ✘ |

**Key point:** the existing walk-forward places every test window in 2024-2026.
Any source ending before 2024 cannot support the existing evaluation design,
however large it is.

---

## 7. Timestamp and leakage assessment

### 7.1 Required timestamp rules for any future experiment [PROPOSED]

1. **Decision cutoff.** Features for trading day *t* are built at the close of *t*:
   16:00 America/New_York, which is 21:00 UTC in winter and 20:00 UTC in summer.
   pandas/pytz (already installed) convert this correctly across daylight-saving
   changes [VERIFIED locally], so no new dependency is needed for it.
2. **Availability, not claimed publication.** Use each source's first-availability
   time:
   - GDELT: the batch time, treated as available at batch time + 15 minutes, to be
     conservative.
   - Benzinga: `created`/`published`.
   - Alpaca: `created_at`.
   - Massive Stocks: `published_utc`.
   - Tiingo: `crawlDate`.
   Never use `updated`/`last_updated`, and never use a page-declared timestamp
   alone.
3. **After-close news moves forward.** An item available after the cutoff of day
   *t* belongs to the next trading day's features. Weekend and holiday news
   accumulates into the next trading day. The 1,177 stored trading dates define the
   calendar, so no external holiday list is needed for that.
4. **Early closes.** On half-day sessions (13:00 ET) the cutoff must move earlier.
   `market_data` does not record session length, so an early-close list is
   **[MISSING]**. Until one is sourced, use a conservative fixed 13:00 ET cutoff
   on known half-days, or exclude them.
5. **Missing timestamps are dropped**, never inferred from file order or download
   time.
6. **Updated articles:** keep the first version and its first-availability time.
   Record updates separately, never as new information at the original time.
7. **Duplicates:** deduplicate by canonical URL and near-duplicate title, keeping
   the earliest availability. Within the two GDELT batches sampled there were 0
   duplicate URLs [VERIFIED]. Cross-batch and syndication duplicates were not
   measured [UNVERIFIED].
8. **Retrieval provenance.** Store retrieval time, query parameters, source version
   and file checksums. Freeze the snapshot and never re-query to fill gaps after
   the fact: re-querying an API later can return edited or deleted articles,
   which introduces look-ahead and survivorship bias.
9. **No retroactive sentiment.** Do not use provider-computed sentiment
   (Massive "insights", Alpha Vantage, EODHD) unless the provider documents that
   it was computed at publication time. A score computed later by a model trained
   on later data can carry future knowledge. The same applies to any modern LLM,
   including Gemini, scoring historical news. B3 must use a classifier whose
   training data predates the evaluation window, or GDELT's own lexicon tone.

### 7.2 What the GDELT sample showed about delay [VERIFIED, one batch]

For the 2024-01-12 21:00 UTC batch (the close of the first test day):

- **Coverage:** 1,261 of 2,108 rows carried a page-declared publication time.
- **Lag:** the batch trailed it by a median of **149 minutes**, with the 10th to
  90th percentile at **35 to 387 minutes**.
- **Old articles:** 2.9% were published more than 24 hours earlier, i.e.
  re-discovered old articles.
- **Impossible timestamps:** 28 rows (2.2%) claimed a publication time after the
  batch that captured them.

This is why the batch time, not the page timestamp, must be the availability
time. The delay makes GDELT features slightly stale, which errs on the safe side.

### 7.3 Per-source leakage verdict

| Source | Leakage-safe first-availability time? |
| --- | --- |
| GDELT | **Yes**: batch time, UTC, immutable files |
| Benzinga (Massive / Alpaca / direct) | **Yes**: documented immutable `created`/`published`, separate `updated` |
| Tiingo | Yes (`crawlDate`), but history unavailable to individuals |
| Massive Stocks news | Publication time only; no update tracking → snapshot needed |
| Finnhub, Alpha Vantage, EODHD, NewsAPI | Publication time only, zone or semantics partly unverified |
| FNSPID, NIFTY | Daily or unverified precision; coverage fails anyway |

---

## 8. Licensing, pricing and access limitations

- **Only GDELT** grants explicit, verified rights to academic use, storage,
  derived data and redistribution, with citation.
- **Commercial feeds' individual plans** (Massive, Alpaca, Finnhub, Tiingo, EODHD)
  all restrict use to personal or non-commercial purposes and prohibit
  redistribution. None explicitly addresses an M.Tech research project or the
  publication of aggregate results derived from the data.
- **Finnhub goes further.** Its terms require deleting data when the subscription
  ends and forbid sharing "derived results" without written approval. That is
  incompatible with a reproducible, publishable experiment unless Finnhub approves
  in writing.
- **Copyright.** Publicly accessible news text is not automatically free to store
  or redistribute. Common Crawl explicitly grants no rights to the underlying
  content. FNSPID's article text was scraped from Nasdaq.com, so its dataset
  licence cannot extend to the publishers' copyright.
- **GDELT titles.** The research plan should store GDELT titles locally only and
  publish aggregates, never the raw titles. GDELT's licence covers its datasets,
  but whether that extends to republishing publishers' headlines in bulk was not
  verified.
- **No accounts were created, no provider was contacted, no terms were accepted
  and no charge was incurred.**

---

## 9. Data quality and instrument mapping

**GDELT, from two 15-minute samples** (2022-01-03 14:30 UTC and 2024-01-12 21:00
UTC), raw files deleted after counting:

| Measure | 2022-01-03 14:30 | 2024-01-12 21:00 |
| --- | ---: | ---: |
| Rows (records) | 1,233 | 2,108 |
| Columns per row | 27 (all rows) | 27 (all rows) |
| Distinct `V2.1DATE` values | 1 | 1 |
| Duplicate URLs within the batch | 0 | 0 |
| Rows with any finance theme | 97 | 136 |
| Rows with `ECON_STOCKMARKET` | 65 | 53 |
| Organization mentions "Nasdaq" | 21 | 8 |
| Organization mentions "Federal Reserve" | 5 | 7 |
| QQQ / GLD / AGG / "Nasdaq-100" in names or URLs | 0 | 0 |
| Rows with page title | — | 2,108 (100%) |
| Titles mentioning gold / Nasdaq / bond-treasury-yield | — | 7 / 11 / 8 |
| Finance-row tone (min / mean / max) | −6.0 / −0.38 / 6.5 | −8.3 / −0.53 / 5.8 |

**Extrapolation [UNVERIFIED, from two batches].** At roughly 50–65
`ECON_STOCKMARKET` records per 15-minute batch, a trading day might hold several
thousand stock-market-themed records globally. That is enough volume for a daily
market-level series, but it needs US-relevance filtering (source domain or
location) and normalisation by total daily volume, because the monitored source
list changes over time (a selection-bias risk).

**Mapping assessment:**

| Instrument | GDELT (market-level) | Benzinga-family (ticker-level) |
| --- | --- | --- |
| `^IXIC`, `^NDX`, `QQQ` | `ECON_STOCKMARKET` + "Nasdaq" organizations/titles → one US-equity sentiment series (the three series are highly correlated) | QQQ-tagged items [UNVERIFIED]; constituent aggregation would need point-in-time Nasdaq-100 membership **[MISSING]** |
| `AGG` | `ECON_INTEREST_RATES`, `ECON_CENTRALBANK`, `ECON_INFLATION`, bond/treasury/yield titles → rates sentiment | AGG-tagged items / bond channels [UNVERIFIED] |
| `GLD` | `ECON_GOLDPRICE` theme + "gold" titles → gold sentiment | GLD-tagged items / commodities channel [UNVERIFIED] |

**Conclusion: market/asset-class-level analysis is supported by GDELT.
Instrument-specific analysis is supported by no verified source;** it would need the
Benzinga family plus licence confirmation and a tagging check. General news
volume is not the same as relevant sentiment: every filter must be defined and
fixed before any result is examined.

---

## 10. Ranked recommendation

1. **GDELT 2.0 GKG — CONDITIONALLY RECOMMENDED (primary, market-level).**
   Coverage, timestamps, reproducibility and licence are all verified.
   Conditions:
   - (a) you accept a market/asset-class-level scope;
   - (b) you approve an acquisition route: streaming the raw files (≈1 TB for the
     English stream over the window, filtered to a few GB on disk), or BigQuery
     (Google account, cost unverified);
   - (c) filters and aggregation are pre-registered;
   - (d) titles are stored locally only.
2. **Benzinga news via Alpaca (free) or Massive ($99/month) — CONDITIONALLY
   RECOMMENDED (secondary, instrument-level).** It has the best
   publication/update semantics and full text. It needs written confirmation from
   the provider that academic use, local storage for the project and publication
   of aggregate results are permitted, plus a sample check of ETF tagging. Both
   require you to create an account, which is your decision.
3. **Massive Stocks news (Starter $29/month) — CONDITIONAL, lower.** It has no
   update timestamp, no full text, and provider sentiment of uncertain provenance.
4. **EODHD — UNVERIFIED.** It would need written confirmation of 2022 coverage and
   an academic licence.
5. **NOT SUITABLE:** Finnhub, Alpha Vantage, Tiingo (individual), NewsAPI.org,
   Common Crawl CC-NEWS, GDELT DOC API, FNSPID, NIFTY, and the smaller academic
   sets found.
6. **Financial PhraseBank:** not a source. It is the leading candidate for
   **validating** the B3 sentiment classifier (CC BY-NC-SA 3.0, non-commercial
   academic use).

A combined design is possible later: GDELT for the market-level primary
experiment, with a Benzinga-family source as an instrument-level robustness check.
Starting with GDELT alone is the lower-risk path because it needs no account, no
payment and no licence negotiation.

---

## 11. Unresolved questions and approvals needed

**Your decisions:**

1. Approve GDELT as the primary source, **or** choose "no source yet".
2. Accept the **market-level scope**: one US-equity series for `^IXIC`/`^NDX`/`QQQ`,
   a rates series for `AGG` and a gold series for `GLD`. The alternative is to
   require instrument-level data, which means the commercial route.
3. Choose the acquisition route:
   - Raw-file streaming: free, about 1 TB downloaded over several days, filtered
     locally.
   - BigQuery: needs a Google Cloud account and billing, with the cost to be
     confirmed by you.
4. Decide whether to include the **translated** stream (doubles volume; adds
   non-US news).
5. Decide where the filtered data lives. It would be a new immutable raw location
   such as `datasets/raw/gdelt/`, never altering existing raw data, recorded in an
   ADR.
6. If instrument-level data is wanted: whether **you** will create an Alpaca or
   Massive account and request written licence confirmation.

**Facts still to confirm:**

- BigQuery cost for the needed columns and date range.
- Whether GDELT has missing 15-minute batches in the window. GDELT's master file
  list allows this to be measured before any bulk download.
- Cross-batch and syndication duplicate rates.
- An early-close (half-day) calendar source.
- Whether GDELT titles may be redistributed (not needed if only aggregates are
  published).
- Alpaca's current news pricing, ETF tagging coverage, and research and retention
  rights for Alpaca and Massive.

**Recommended ADR [PROPOSED — not created, no approval implied].** "ADR-043 —
Historical news source for the research track." It would record:

- the chosen source and scope;
- the availability-time rule;
- the storage location and immutability;
- the ban on retroactive provider or LLM sentiment;
- the licence basis, including the citation requirement.

It should be written only after you decide items 1–5.

---

## 12. Exact next steps for a future phase [FUTURE]

None of these is authorised yet.

1. **Gap and size audit (cheap, no bulk download).** Fetch GDELT's master file
   list once. Count missing 15-minute batches and total bytes for 2021-12-01 →
   2026-09-11, separately for the English and translation streams.
2. **Pre-registration.** Freeze the theme, organization and title filters per
   instrument group, the US-relevance filter, the cutoff rule (section 7.1) and the
   aggregation (daily, by trading date), before any data is examined against
   returns.
3. **Acquisition** (only after the ADR). Stream each file, keep only the filtered
   rows' URL, batch time, source, themes, tone and title, plus file checksums.
   Write to the approved immutable location and log the retrieval provenance.
   Deduplicate.
4. **Coverage report.** Daily item counts per series, gaps, and source-mix drift.
   Decide the minimum daily item count below which a day's sentiment is "no news"
   rather than neutral.
5. **Then B3,** if approved: a sentiment method (GDELT tone vs a pre-2022 financial
   classifier on titles, validated on Financial PhraseBank), with dependency
   approval for any new library.

---

## Verification of this phase

- **Files created:** this report. **Files modified:**
  `docs/RESEARCH_ENHANCEMENT_ARCHITECTURE.md` (a short B2 findings note) and
  `docs/MEMORY.md` (track status line).
- **Unchanged:** application code, APIs, schema, migrations, UI, dependencies
  (`pyproject.toml`, lockfiles, `package.json`), datasets, model artifacts, demo
  data and database records. The database was only read (`market_data`).
- **Downloads:** two distinct GDELT 15-minute files were sampled in a scratch
  directory outside the repository: 2022-01-03 14:30 (4.8 MB) and 2024-01-12
  21:00 (8.7 MB; fetched three times for separate counts). They were read with
  the Python standard library and `requests`, then deleted. Only counts were
  kept, no article titles. Every other check was a header-only request or a
  documentation page.
- **No tests were run;** no code changed.
- **No source is approved.** GDELT is conditionally recommended and awaits your
  decision.
