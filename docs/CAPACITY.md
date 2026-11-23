# Capacity plan: RTI Mate

Full corpus target: + 1,000+ CIC decisions (8,000+ pages)

<!-- generated:start -->
## Measured on my start corpus (2026-11-23 16:14 UTC)

| What | Value |
|---|---|
| Files | 13 |
| Size on disk | 11.4 MB |
| Pages (PDF pages + 1 per 3,000 characters of text/HTML) | 397 |
| Characters of text | 687,668 |
| Estimated tokens (characters / 4) | 171,917 |
| Tokens per page | 433 |
| PDFs with almost no text (scanned? OCR is Day 7) | 1 |
| Files not measured (zip, xlsx, unreadable) | 0 |

## Estimate for the full corpus (target: 8,000 pages)

| What | How | Value |
|---|---|---|
| Scale factor | target / measured | x 20.2 |
| Tokens | measured tokens x scale | 3.46 M |
| Raw files | measured MB x scale | 229 MB |
| Chunks | tokens / 400 x 1.15 overlap | 9,960 |
| Embedding cost, one time | tokens x 1.15 x $0.15 per 1M | $0.60 = Rs 57 |
| Vector storage | chunks x 768 numbers x 4 bytes | 31 MB |
| Text in Postgres | characters x scale x 1.2 | 17 MB |

Assumptions: 4 characters per token, 400-token chunks, 768-dimension embeddings at $0.15 per 1M tokens, Rs 95 per US dollar.
<!-- generated:end -->

## What I conclude

1. Embedding the 8,000-page target is estimated at about **Rs 57 one time**, so cost is not a
   material blocker at this scale; the estimate depends on the token and price assumptions above.
2. The estimate is about **31 MB of vectors + 17 MB of text**, or roughly 48 MB before indexes and
   row overhead. Check the actual database plan quota before loading; that quota was not available
   when this report was written.
3. I am least certain about tokens per page: 433 is estimated from characters divided by four, and
   PDF extraction samples only five pages. Measure representative files with the actual tokenizer.
4. At 10x scale (about 80,000 pages), estimates become **34.6 M tokens, 99,600 chunks, Rs 570
   embedding cost, 310 MB vectors, 170 MB text and 2.3 GB raw files**. Re-measure representative
   files and confirm database/storage limits before scaling.
