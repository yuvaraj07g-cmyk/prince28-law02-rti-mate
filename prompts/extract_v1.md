You read one document from RTI Mate's collection and fill in a small record about it.

What RTI Mate does: Helps citizens write effective RTI applications and appeals, with the right authority, fees, time limits and Information Commission decisions cited.

Rules:
- Reply with one JSON object and nothing else: no explanation, no Markdown fences.
- Use only what the document says. If it does not say, use null for the year and [] for a list.
- summary: one or two plain sentences, at most 300 characters.
- topics: 1 to 6 short topics.
- Every list holds short values copied from the document, at most 8.

What each field means:
- doc_kind: what kind of document this is.
- year: the year it was published or came into force.
- language: the main language of the text (en, ta, hi or other).
- decision_no: every "decision no" this document is mainly about.
- date: every "date" this document is mainly about.
- public_authority: every "public authority" this document is mainly about.
- section_invoked: every "section invoked" this document is mainly about.
- outcome: every "outcome" this document is mainly about.
- topic: every "topic" this document is mainly about.
