"""Reading a question: which words matter, and whether it is about the future.

Two parts of the calendar's RAG integration need to understand a question, so
the understanding lives here once.

  rag_documents  decides what to send to the shared RAG server. A question about
                 what is due, or what is next, should only be answered from what
                 is still ahead. Otherwise the server's word matching can pick a
                 record from last month, because it has no idea about dates.

  rag_client     decides how much to trust the answer. The label used to count
                 how many sources were cited, which is almost always one and so
                 almost always "low", whether or not the answer was right. It now
                 measures how much of the question the cited record covers.

Everything here is plain word handling: no model, no network, and the same
result every time, so it can be tested exactly.
"""
import re

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
    "have", "how", "i", "in", "is", "it", "its", "my", "of", "on", "or",
    "that", "the", "to", "was", "were", "what", "when", "where", "which",
    "who", "will", "with", "do", "does", "did", "me", "you", "your", "am",
    "any", "all", "there", "this", "these", "those", "about", "can", "could",
    "would", "should", "tell", "show", "give", "list", "please",
}

# Words that shape a question without naming the thing asked about, so they are
# not expected to appear in the record that answers it. "When is my next lecture"
# is about a lecture; "when" and "next" are how it is asked.
QUESTION_WORDS = {
    "next", "first", "last", "soonest", "earliest", "upcoming", "soon",
    "coming", "tomorrow", "today", "tonight", "now", "many", "much",
}

# Words that mean the student wants something still ahead of them.
FORWARD = {
    "when", "next", "upcoming", "soon", "soonest", "due", "deadline",
    "deadlines", "tomorrow", "tonight", "today", "coming", "earliest", "first",
}

# Words that mean they are asking about the past. These win over FORWARD:
# "when was my last quiz" has "when" in it but is not about the future.
PAST = {
    "last", "previous", "past", "was", "were", "did", "already", "ago",
    "yesterday", "earlier", "before", "submitted", "completed", "finished",
    "missed", "overdue", "history",
}

# Words that mean they want the single nearest match, not a list.
NEAREST = {"next", "first", "soonest", "earliest"}


def tokens(text):
    return re.findall(r"[a-z0-9]+", str(text).lower())


def stem(word):
    """Fold a plural onto its singular, so "lectures" matches "lecture"."""
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def word_stems(text):
    """Every word in a text, folded. Used for the record being matched against."""
    return {stem(t) for t in tokens(text)}


def question_terms(question):
    """The words of a question that describe what it is asking about.

    Returns [(stem, original word)] in the order asked, so the original can be
    shown to the student while the stem is used for matching.
    """
    seen, terms = set(), []
    for word in tokens(question):
        if word in STOPWORDS or word in QUESTION_WORDS or len(word) < 2:
            continue
        s = stem(word)
        if s not in seen:
            seen.add(s)
            terms.append((s, word))
    return terms


def wants_upcoming(question):
    """True if the question is about something still ahead."""
    words = set(tokens(question))
    if words & PAST:
        return False
    return bool(words & FORWARD)


def wants_nearest(question):
    """True if the question wants the single soonest match."""
    words = set(tokens(question))
    if words & PAST:
        return False
    return bool(words & NEAREST)


def coverage(question, texts):
    """How much of the question the given records cover.

    Returns {"matched": [...], "missing": [...], "total": n}. The words are the
    student's own, as they typed them. total is 0 when the question has no
    specific words to match, in which case there is nothing to measure.
    """
    terms = question_terms(question)
    haystack = set()
    for text in texts:
        haystack |= word_stems(text)

    matched = [original for s, original in terms if s in haystack]
    missing = [original for s, original in terms if s not in haystack]
    return {"matched": matched, "missing": missing, "total": len(terms)}


def level(cov):
    """Map coverage onto the categories the interface shows.

    high    the record covers at least three quarters of what was asked
    medium  it covers at least half
    low     it covers less than half, or the question had nothing to match
    """
    if not cov["total"]:
        return "low"

    ratio = len(cov["matched"]) / cov["total"]
    if ratio >= 0.75:
        return "high"
    if ratio >= 0.5:
        return "medium"
    return "low"


def basis(cov, record_count=1):
    """One sentence saying why the level is what it is."""
    noun = "record covers" if record_count == 1 else "records cover"

    if not cov["total"]:
        return "The question has no specific words to match against the records."

    sentence = (f"The cited {noun} {len(cov['matched'])} of {cov['total']} "
                f"words in your question")

    if cov["matched"]:
        sentence += f" ({', '.join(cov['matched'])})"
    if cov["missing"]:
        sentence += f"; not found: {', '.join(cov['missing'])}"

    return sentence + "."
