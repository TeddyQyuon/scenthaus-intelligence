# SCENTHAUS storefront refresh — 4 November 2026

## Research and design

Inspected the live homepage and collection in the cloud browser. Reviewed:

- https://www.sephora.sg/categories/fragrance — visible search, category entry points, filters and product metadata.
- https://www.jomalone.com/colognes — restrained colour, scent-family entry points and focused product presentation.
- https://diptyqueparis.com/en-eu/pages/fragrances — fragrance storytelling, family discovery and collection structure.

SCENTHAUS retains its own identity and existing hero/product photographs. Changes
use ivory, forest green, editorial type, four scent-family cards and a compact
collection navigation. No third-party logos, copy, offers or authenticity claims
were copied. Prices/stock remain simulated portfolio annotations.

## Behaviour

- Native search dialog traps focus, closes with Escape/backdrop/close, restores
  opener focus, searches names/houses/notes and navigates without a page reload.
- URL query parameters preserve collection search and filters on direct entry.
- Mobile filters collapse behind an accessible disclosure. Account remains
  reachable in mobile navigation; Escape closes navigation.
- Collection renders 24 products initially, then 24 more per click, with count
  and progress. Filtering resets the rendered limit.
- Product sizes expose selection state; mobile purchase controls stay accessible.
- Motion uses transform/opacity, one route observer, no animation package, and
  disables animation and transitions for reduced-motion preferences.

## Measurements

Measured locally on the same source catalogue; bytes are uncompressed unless
marked gzip. These are asset/build measurements, not field Core Web Vitals.

| Measurement | Before | After |
| --- | ---: | ---: |
| All original product image files | 24,118,515 bytes | Originals retained |
| All 320px responsive WebP images | — | 1,087,154 bytes (95.5% smaller) |
| All 640px responsive WebP images | — | 2,996,266 bytes (87.6% smaller) |
| Initial collection cards | 150 | 24 |
| Initial application JS | 388.52 kB / 125.90 kB gzip | 381.06 kB / 123.93 kB gzip |
| Stylesheet | 47.80 kB / 11.42 kB gzip | 62.14 kB / 14.35 kB gzip |
| HTML | 1.13 kB | 0.68 kB |

Search (3.00 kB) and checkout (13.02 kB) are separate on-demand JS chunks. Fonts
are local WOFF2 subsets with font-display:swap; no Google Fonts stylesheet or
font-host connection is required. Hero selects an 800px alternative on smaller
screens. All 150 catalogue photographs have both responsive alternatives.

## Checks completed before deployment

- `npm --prefix frontend run test:unit`: 22 passed (existing quick-add/checkout
  regressions plus seven new discovery tests).
- `npm --prefix frontend run build`: passed.
- `git diff --check`: passed.
- Live catalogue inspection: 150 products, 35 houses; all referenced responsive
  image paths resolve to generated files.
- Local cloud-browser visual check: desktop homepage and search dialog.
  Local session/catalogue requests require the backend; API flow verification
  is reserved for the hosted release.

## Release verification

Pending hosted build and browser verification. No live payment is required for
this visual and browsing update.
