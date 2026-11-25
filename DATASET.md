# Dataset: RTI Mate

Helps citizens write effective RTI applications and appeals, with the right authority, fees, time limits and Information Commission decisions cited.

- **Start target:** Act + rules + guides + 200 decisions
- **Full target:** + 1,000+ CIC decisions (8,000+ pages)
- **Collected by:** `scripts/fetch.py` as `examate-student-bot` (https://github.com/yuvaraj07g-cmyk/prince28-law02-rti-mate): robots.txt respected, at most 4 requests at once, 0.5 s between requests to one site.

## Where the documents come from

- https://cic.gov.in/
- https://rtionline.gov.in/
- https://rti.gov.in/

## Terms I follow

Public law and decisions. Cite section or decision number.

- Every answer links to the original document.
- No personal data is collected.

<!-- generated:start -->
## Sources (generated 2026-11-24 05:59 UTC by scripts/dataset_report.py)

| Source | Licence / terms | Files | MB | Pages* | How | Fetched | Example URL |
|---|---|---|---|---|---|---|---|
| dopt | Official Government of India material; subject to applicable reuse terms | 10 | 8.2 | 311 | http+manual | 2026-11-23 | https://rti.dopt.gov.in/rtiact.html#RTI_Act_2005.pdf |
| kerala-rti | Government publication; applicable reuse terms | 1 | 0.2 | 20 | http | 2026-11-23 | https://rti.img.kerala.gov.in/rti/pdf/rtiact-malayalam.pdf |
| rti-mate-github | GitHub repository content; subject to repository licence | 3 | 0.0 | 2 | git @ 5d86fd0e1e | 2026-11-24 | https://github.com/yuvaraj07g-cmyk/prince28-law02-rti-mate/blob/HEAD/docs/CAPACITY.md |
| rtionline | Official Government of India material; subject to applicable reuse terms | 1 | 1.7 | 29 | manual | 2026-11-23 | https://rtionline.gov.in/#RTI_Online_User_Manual.pdf |
| tamil-nadu-rti | Official Government of Tamil Nadu material; applicable reuse terms | 1 | 1.2 | 37 | http | 2026-11-23 | http://www.tn.gov.in/rti/proactive/guidebook_rtiact.pdf |

**Total:** 16 files, 11.4 MB, 399 pages. Not downloaded: 0 blocked by robots.txt, 0 failed.

*Pages = PDF pages, plus one page per 3,000 characters of text or HTML.

## Files (first 16 of 16)

The complete list, with a sha256 fingerprint of every file, is `data/manifest.jsonl`.

| # | Title / file | Source | Pages | Fetched | URL |
|---|---|---|---|---|---|
| 1 | RTI_Act_2005 | dopt | 23 | 2026-11-23 | https://rti.dopt.gov.in/rtiact.html#RTI_Act_2005.pdf |
| 2 | RTI_Act_2005_Amended | dopt | 25 | 2026-11-23 | https://rti.dopt.gov.in/rtiact.html#RTI_Act_2005_Amended.pdf |
| 3 | RTI Act 2005 amended (English) | dopt | 25 | 2026-11-23 | https://rti.dopt.gov.in/Writereaddata/RTI%20Act%2C%202005%20%28Amended%29-English%20Version.PDF |
| 4 | Right to Information Act 2005 (Gujarati) | dopt | 77 | 2026-11-23 | https://rti.dopt.gov.in/Writereaddata/rti-act-2005-gujarati.pdf |
| 5 | Right to Information Act 2005 (English) | dopt | 23 | 2026-11-23 | https://rti.dopt.gov.in/Writereaddata/RTI-Act.pdf |
| 6 | Right to Information Act 2005 (Hindi) | dopt | 27 | 2026-11-23 | https://rti.dopt.gov.in/Writereaddata/RTI-ActinHindi.pdf |
| 7 | Right to Information Rules 2019 | dopt | 7 | 2026-11-23 | https://documents.doptcirculars.nic.in/D2/D02rti/RTI_Rules_2019.pdf |
| 8 | Right to Information Act 2005 (Assamese) | dopt | 43 | 2026-11-23 | https://rti.dopt.gov.in/Writereaddata/rtiact_assamese.pdf |
| 9 | Right to Information Act 2005 (Kannada) | dopt | 30 | 2026-11-23 | https://rti.dopt.gov.in/Writereaddata/rtiact-kannada.pdf |
| 10 | Right to Information Act 2005 (Marathi) | dopt | 31 | 2026-11-23 | https://rti.dopt.gov.in/Writereaddata/rtiactmarathi.pdf |
| 11 | Right to Information Act 2005 (Malayalam) | kerala-rti | 20 | 2026-11-23 | https://rti.img.kerala.gov.in/rti/pdf/rtiact-malayalam.pdf |
| 12 | docs/CAPACITY.md | rti-mate-github | 1 | 2026-11-24 | https://github.com/yuvaraj07g-cmyk/prince28-law02-rti-mate/blob/HEAD/docs/CAPACITY.md |
| 13 | docs/QUESTIONS.md | rti-mate-github | 1 | 2026-11-24 | https://github.com/yuvaraj07g-cmyk/prince28-law02-rti-mate/blob/HEAD/docs/QUESTIONS.md |
| 14 | docs/REQUIREMENTS.md | rti-mate-github |  | 2026-11-24 | https://github.com/yuvaraj07g-cmyk/prince28-law02-rti-mate/blob/HEAD/docs/REQUIREMENTS.md |
| 15 | RTI_Online_User_Manual | rtionline | 29 | 2026-11-23 | https://rtionline.gov.in/#RTI_Online_User_Manual.pdf |
| 16 | RTI Act guidebook (Tamil Nadu) | tamil-nadu-rti | 37 | 2026-11-23 | http://www.tn.gov.in/rti/proactive/guidebook_rtiact.pdf |
<!-- generated:end -->

## Known gaps

- The start target is not met: the current 13 manifest records contain **0 CIC decisions**, versus
  the target of 200. The [CIC decision page](https://cic.gov.in/decision) leads to a legacy search
  form that requires a CAPTCHA; no direct bulk source was identified. Collect decisions from stable
  official links without automating the CAPTCHA, and check source terms before adding them.
- The corpus is weighted toward RTI Act translations. It has one Tamil Nadu guidebook, but no
  substantial set of practical guides or Tamil Nadu rules yet.
- Reuse terms for the DOPT, Kerala and Tamil Nadu documents have not been independently confirmed
  for full-text display. Cite original sources and use only necessary excerpts until verified.
