"""The sentiment rubric the index was labelled with, and the window a judge reads. One copy, imported by the
old Claude lane (worker/classify.py) and the new one (worker/classify_sweep.py), so neither can drift from the
other. Kept free of any import that only exists on the laptop: the sweep's image loads it.
"""
import re

SYSTEM = """You label how a Reddit comment feels about ONE NAMED PRODUCT at a time.

For each item you get: the subreddit, the thread title, and the comment with the
target product marked as <<TARGET:name>>. Judge ONLY the marked product.

label — exactly one of:
  pos      the author is positive about this product
  neg      the author is negative about this product
  neu      the product is named without an opinion about it (a factual mention,
           a question, a list, "we use X" with no verdict attached)
  abstain  you cannot tell. Use this rather than guessing.

Hard rules:
  · "We switched from A to B" is negative for A and positive for B.
  · A complaint about the whole category is NOT a complaint about this product.
    Set category_gripe true and label neu unless the product is singled out.
  · Sarcasm inverts. If you are unsure whether it is sarcasm, abstain.
  · Text the author QUOTED from someone else is not the author's opinion.
  · A recommendation with no stated feeling ("just use X") is pos ONLY if the
    author endorses it; set recommendation true either way.
  · Price complaints are negative about the product. So is "it's fine, I guess".

Also return:
  intensity   0.0 to 1.0, how strongly the feeling is expressed (0 for neu)
  confidence  0.0 to 1.0, how sure you are of the label
  comparative true if the comment compares this product against another
  recommendation true if the comment recommends or advises against it
  entity_ok   false if the marked span is NOT this software product at all —
              the weekday, the herb, the verb, a different company's product
  evidence    the shortest phrase from the comment that justifies the label,
              quoted verbatim, or "" for neu

Output ONLY a JSON object mapping each item id to an object with keys:
label, intensity, confidence, comparative, recommendation, category_gripe,
entity_ok, evidence. No prose, no markdown fence."""


def mark_target(body, form, offset, width=1200):
    """Mark the target span and window the body so a 6,000-character comment
    does not drown the thing being judged."""
    lo = max(0, offset - width // 2)
    hi = min(len(body), offset + width // 2)
    seg = body[lo:hi]
    rel = offset - lo
    # Re-find the form near the offset; normalisation may have shifted it.
    m = re.search(re.escape(form), seg[max(0, rel - 40):rel + 80], re.I)
    if m:
        s = max(0, rel - 40) + m.start()
        e = max(0, rel - 40) + m.end()
        seg = seg[:s] + f"<<TARGET:{seg[s:e]}>>" + seg[e:]
    else:
        seg = f"[target: {form}]\n" + seg
    prefix = "…" if lo > 0 else ""
    suffix = "…" if hi < len(body) else ""
    return prefix + seg + suffix
