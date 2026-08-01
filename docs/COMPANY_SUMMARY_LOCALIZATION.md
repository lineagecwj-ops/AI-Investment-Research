# Company Summary Localization

## Scope

Research page company summary localization is presentation-only.

The service does not overwrite `Stock.company_summary`, does not change Yahoo Finance mapping, and does not modify SQLite schema or cached raw company summary values.

## Source Audit

The MVP uses official public Taiwan data when a Taiwan stock has enough fields to build a short Chinese introduction.

Sources:

- TWSE listed company profile: `https://openapi.twse.com.tw/v1/opendata/t187ap03_L`
- TPEx OTC company profile: `https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O`
- MOEA company registration business items: `https://data.gcis.nat.gov.tw/od/data/api/236EE382-4942-41A9-BD03-CA0709025E7C`

Fields used:

- Company code
- Company name
- Industry
- Business accounting number
- Registered business item description

## Display Behavior

The Research page shows:

- A short primary company introduction.
- A `查看完整公司介紹` expander when full content is available.
- A short source note explaining the official-data-first rule.

For Taiwan stocks, the localized summary is assembled from official company profile fields and registered business items. This is an official business-item summary, not full machine translation of Yahoo `longBusinessSummary`.

For non-Taiwan stocks, or Taiwan stocks without usable official business-item content, the page falls back to Yahoo Finance English company summary. If no summary exists, the page shows a friendly `N/A` message.

## Cache

Localized Taiwan summaries use a lightweight runtime JSON cache:

- `data/taiwan_company_summaries.json`
- TTL: 7 days
- Git ignored

If official sources are unavailable but a stale cache exists, the stale cache can be used for presentation. If no localized summary exists, the app falls back to Yahoo Finance English text.

## Known Limitations

- The MVP does not use AI, LLM, translation API, Google Translate, news, or web scraping.
- Official company registration business items are not the same as a polished business description.
- The service does not build a large company profile database.
- Coverage depends on official profile fields containing a usable business accounting number.
