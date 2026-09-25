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
