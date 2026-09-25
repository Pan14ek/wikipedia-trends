# Methodology

## M03 Pageviews collection

M03 retrieves monthly article pageviews from Wikimedia Analytics' REST Pageviews
endpoint:

```text
https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/
{project}/all-access/user/{article}/monthly/{start}/{end}
```

`project` is an edition such as `uk.wikipedia`. Article titles are normalized
only by replacing spaces with underscores before percent encoding; literal
slashes and non-ASCII characters are percent encoded. The selected dimensions
are `all-access` and `user`: all access methods, but Wikimedia's standard
human-reader metric rather than bot traffic. The granularity is `monthly`.

The request start is the first day of the first requested month at `00`, and
the end is the last day of the final requested month at `00`, as required by
the endpoint. The client sends a User-Agent on every request, uses a 10-second
per-attempt timeout, and retries timeout, transport, 429, and 5xx responses up
to three total attempts with exponential backoff. A valid `Retry-After` header
on 429 takes precedence over the exponential delay.

An API response record becomes an observed `MonthlyPageview`. If a requested
month is absent, M03 emits an `UNKNOWN` observation rather than treating it as
zero. M03 does not calculate, normalize, cache, or otherwise analyze pageviews.

## M06 Year-over-year growth

M06 compares the 12 calendar months ending at the latest supplied month with
the 12 immediately preceding calendar months. When more than 24 observations
are supplied, older months are ignored; the latest two calendar-aligned years
are always used. The primary calculation is:

```text
YoY % = ((recent_12_total / previous_12_total) - 1) * 100
```

Each window requires at least 10 observed or inferred-zero months. If either
window has missing months, a result is calculated only if both windows have
known values in exactly the same calendar-month positions. This prevents a
partial 12-month total from being compared to a different partial period.
Unknown observations never become zero. A zero previous total is reported as
`zero_baseline` without a percentage; inadequate coverage is
`insufficient_data`; differently missing positions are
`non_comparable_periods`. The diagnostic mean-based percentage is equal to the
total-based percentage because the compared known-month positions are paired.

## M04 Article resolution

For `query.mode = article`, M04 first resolves the requested title in an
explicit source language. A source language is inferred only for a one-language
request; multi-language requests must provide `query.source_language` rather
than relying on title translation or guessing. MediaWiki's `redirects=1` lookup
returns the canonical title, page ID, canonical URL, Wikidata item, and language
links. A disambiguation page produces a structured
`requires_clarification` result and is never selected as an article.

The resolver maps the canonical source concept to each requested language using
the source Wikidata item's sitelinks, falling back to MediaWiki language links
when no Wikidata sitelink is available. Each returned article records its
canonical title, project, page ID, URL, Wikidata item, and resolution method.
Languages with no linked article are represented explicitly as missing; they do
not cause other requested editions to be discarded. M04 performs no topic
discovery, pageview collection, or title translation.

## M09 Normalized interest

M09 compares an article with the traffic of its own Wikimedia project using
monthly aggregate pageviews from the Analytics API. Both article and project
series use the `all-access` and `user` dimensions. For every aligned month:

```text
normalized interest = article views / project views * 1,000,000
```

The unit is article pageviews per 1,000,000 project pageviews. A normalized
value is available only when the article and project observations are both
known for the same calendar month and the project total is greater than zero.
Missing project totals are never interpolated; missing, non-overlapping, and
zero-denominator months are explicitly unknown and are excluded from the mean
and median period summary. Absolute article pageview metrics remain separate
and unchanged.

Normalization makes comparisons across language editions fairer with respect
to total Wikipedia traffic. It does not convert language-edition readership
into country-level market demand, and must not be interpreted that way.

## M08 Data quality and reliability checks

Every completed analysis has a quality report containing the same six explicit
checks: completeness, period sufficiency, article resolution, trend
consistency, spike sensitivity, and comparison validity. Each check is one of
`pass`, `warning`, `fail`, or `not_evaluated`; the report deliberately emits
no synthetic numeric confidence score.

Completeness is the number of observed or inferred-zero requested months
divided by requested months. It passes at 90% or higher, warns from 75%
inclusive to below 90%, and fails below 75%. Unknown observations never count
as available.

A requested period of 24 or more months is sufficient for calendar-aligned
YoY analysis. A 12–23-month period warns because absolute metrics remain valid
but the standard 24-month YoY comparison is unavailable. Fewer than 12 months
fails. Even in a 24-month request, insufficient or non-comparable aligned
observations fail the YoY-specific period check without converting otherwise
valid absolute metrics into synthetic values.

Canonical structured article resolution passes. A missing requested language
or an unresolved/ambiguous article fails that resolution check and identifies
the affected language where available. Trend consistency is a diagnostic, not
a judgment: it reports the proportion of positive changes among adjacent known
calendar-month observations.

## M10 Anomaly detection and spike sensitivity

M10 scores each known monthly value with the median absolute deviation (MAD):

```text
robust z = 0.6745 * (monthly views - median views) / MAD
```

Values whose absolute score is greater than 3.5 are anomalies. When MAD is
zero, the implementation uses Tukey IQR fences when the IQR is positive;
otherwise it reports an explicit statistical-method limitation rather than
dividing by zero or inventing anomalies. Unknown observations are excluded.

The spike-sensitivity quality check removes the largest anomalous monthly
contribution and recalculates YoY. It warns when the YoY direction changes or
the magnitude differs by more than the configurable 10-percentage-point
default. This is a diagnostic warning, not an automatic rejection. Comparison
validity remains `not_evaluated` until M13 multi-language comparison.

## M11 Bootstrap confidence intervals

M11 estimates a percentile bootstrap interval for calendar-aligned YoY growth.
It forms pairs only where both matching months in the latest previous and
recent 12-month windows have known values. Each of 2,000 deterministic
resamples (seed 42 by default) draws those paired month positions with
replacement, sums the previous and recent values separately, then calculates
YoY from the resampled totals. The reported 95% interval uses the 2.5th and
97.5th percentiles. Fewer than eight valid month pairs, or an all-zero
resampled baseline, produces an explicit `unavailable` result; individual
zero-baseline resamples are excluded because their YoY percentage is undefined.

This interval quantifies variability in the observed monthly series under the
chosen bootstrap procedure. It is not a confidence interval for total market
demand, willingness to pay, or causal product opportunity.

## M12 Topic mode

WT-M20 supersedes M12's independent per-language search and rank-plus-title
overlap selection. Topic mode requires one source language for multi-language
requests. MediaWiki search in that edition discovers up to five candidates;
search rank is stored and used only to break ties after semantic acceptance.
For each candidate the resolver records normalized title, Wikidata label,
aliases, and description evidence. Lexical normalization uses Unicode NFKC,
case folding, punctuation-to-space conversion, and Unicode-aware tokens.
English Wikidata fields are used only when a source-language field is absent,
and the fallback language is recorded.

A candidate passes when the normalized query exactly matches its canonical
title, Wikidata label, or alias, or when at least 0.80 of unique query tokens
occur in its semantic text and at least one occurs in its title, label, or
alias. Disambiguation and detectable list pages cannot be selected. Insufficient
evidence and materially ambiguous senses return structured clarification; the
resolver prefers false negatives to weak semantic matches.

Selected source concepts form the canonical set by Wikidata QID. Each requested
target edition is mapped through those QIDs' Wikidata sitelinks. A missing or
incorrect sitelink stays unresolved; target-language search is not used as an
approximate replacement. Candidate decisions, evidence fields, canonical QIDs,
and mapping status are retained in topic resolution output.

An explicit article override remains available. Overrides whose QID set differs
from the source concept set are proxies: their language-local metrics describe
the selected articles and their language is excluded from like-for-like topic
comparison. The report carries a proxy warning. The agent obtains user approval
before applying a proxy override.

For a topic bucket, views are summed only if every selected article is known:

```text
topic views = sum(all selected article views)
```

If any selected article is unknown or missing for a bucket, the aggregate is
unknown. A complete known aggregate is zero-inferred only when every component
is zero-inferred; otherwise it is observed. Topic totals are article pageviews,
not unique readers: readers may visit more than one selected page, so summed
views can include overlapping audiences.
Topic pageviews are not unique users, purchase intent, willingness to pay, or
country-level demand.

## M13 Multi-language comparison

M13 accepts two through twenty typed language inputs and preserves each
language's local completeness and resolution warnings. A missing language
equivalent is represented as unresolved with a reason; it does not become a
zero-valued series or silently disappear from the requested comparison.

For direct absolute metrics, M13 first intersects the calendar months supplied
by every resolved language, then retains only the months whose pageview value
is known in every language. The resulting effective period records the first
and last shared known months, while warnings state when requested windows
differ or shared months were excluded. A direct comparison is valid only when
all requested languages resolve, every language meets the 75% completeness
minimum, and at least 12 shared known months remain. The comparison-validity
quality check is `pass`, `warning`, or `fail` using those explicit conditions.

Normalized interest is compared only over the further shared subset where
every language has a known normalized value. Topic mode uses exactly one
project-wide pageview series per language edition as its denominator,
regardless of selected article count. Project provenance appears once per
project-period-granularity request. Normalized values remain pageviews per
1,000,000 pageviews for that language's own Wikipedia project; it is not a
country-level demand measure. No Python calculation ranks languages as a best
market or emits an opportunity score.

M13 charts show one labelled line per language with gaps for unknown months.
The caller supplies a subject-and-period title. Up to six languages render in
one chart with a required legend; seven through twenty use separate
per-language PNGs to avoid an unreadable shared legend. Final JSON-report
assembly and PDF reporting remain deferred to later milestones.

## M15 One-page PDF report

M15 presents an already validated M14 `AnalysisReport` in a single A4 PDF. It
does not fetch data, recalculate metrics, normalize values, or infer a
recommendation. The PDF uses the existing main PNG trend chart and copies the
report's supplied absolute and YoY metrics, quality findings, warnings,
methodology version, and generation date.

For every requested language, the document describes interest in that
language's Wikipedia edition. It does not equate pageviews with demand,
willingness to pay, country-level interest, or a product opportunity. Explicit
report warnings, non-passing quality findings, and invalid cross-language
comparison status appear in the reliability section. Detailed warnings remain
in `analysis.json` when the PDF's bounded one-page layout truncates text.

## M16 Local filesystem cache

M16 caches successful raw Pageviews API payloads and validated public
resolution results under `.cache/wikipedia` by default. The cache key is a
SHA-256 digest of canonical JSON request dimensions. Article keys include
project, article, start/end month, granularity, access, and agent; project keys
include the equivalent project-level dimensions. `WIKIPEDIA_TRENDS_CACHE_DIR`
optionally changes the cache root.

Historical pageview data ending before the latest two complete months is fresh
for 30 days. Data including either latest complete month is fresh for 24 hours.
Resolution metadata is fresh for seven days. Entries use an atomic temporary
file followed by replacement. Cache read/write errors, malformed JSON, invalid
payloads, and stale entries are ignored so a live request can refill the cache.
When collection uses the provenance-aware pageview API, its `retrieval` value
is `network` or `cache` and can be copied directly to M14 source metadata.

## M19 Flexible windows and criteria

Analysis periods use inclusive ISO calendar dates. Legacy `period.months`
remains valid and resolves relative to the run date as complete calendar
months, with 24 as the default. “Last month” is the preceding completed
calendar month. Explicit partial-month ranges use daily observations by default;
full calendar-month windows use monthly observations. Daily requests are capped
at yesterday, and monthly requests exclude the current partial month. The
schema-v2 report records the full requested period separately from the
available period; unavailable observations remain unknown and are not
extrapolated.

Growth thresholds compare the selected period with an explicit, equal-length
preceding baseline of the same granularity. A zero baseline has no defined
growth percentage. User thresholds are evaluated independently in Python and
reported as `met`, `not_met`, or `not_evaluable`; no composite score or
forecast is produced. Follow-up analyses should start from the previous report
`input`, which stores the relative window resolved to exact dates, and change
only the user's clarified fields.
