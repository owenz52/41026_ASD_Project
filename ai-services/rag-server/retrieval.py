"""Retrieval for the shared RAG server.

Uses BM25 over the indexed passages. BM25 is implemented here in plain Python
rather than pulled from a library, and no embedding model is downloaded,
because the server has to start quickly inside a container on a marker's
machine with no guarantee of network access. For a corpus of this size —
hundreds of short passages, not millions of documents — lexical ranking is
accurate enough and is fully deterministic, which also makes it testable.

A passage is a small unit of text with a source label. The source is what
becomes a citation, so every answer can be traced to the record it came from.
"""
import math
import re
from collections import Counter

# Words too common to carry meaning; kept short deliberately, since dropping
# too much hurts short questions like "when is my exam".
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
    "have", "how", "i", "in", "is", "it", "its", "my", "of", "on", "or",
    "that", "the", "to", "was", "what", "when", "where", "which", "who",
    "will", "with", "do", "does", "me", "you", "your",
}

K1 = 1.5     # term-frequency saturation
B = 0.75     # length normalisation

# Below this score the top passage is treated as not relevant enough to
# answer from. Tuned so that an unrelated question returns nothing rather
# than the least-bad passage.
RELEVANCE_FLOOR = 1.0


def tokenize(text):
    words = re.findall(r"[a-z0-9]+", str(text).lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 1]


class Index:
    """A searchable index over passages.

    Each passage is {"source": str, "text": str, "metadata": {...}}.
    """

    def __init__(self):
        self.passages = []
        self._tokens = []
        self._freqs = []
        self._doc_freq = Counter()
        self._avg_len = 0.0

    def __len__(self):
        return len(self.passages)

    def add(self, source, text, metadata=None, weight=1.0):
        text = (text or "").strip()
        if not text:
            return

        tokens = tokenize(text)
        if not tokens:
            return

        self.passages.append({
            "source": source,
            "text": text,
            "metadata": metadata or {},
            "weight": weight,
        })
        self._tokens.append(tokens)
        self._freqs.append(Counter(tokens))
        for term in set(tokens):
            self._doc_freq[term] += 1

    def finalise(self):
        if self._tokens:
            self._avg_len = sum(len(t) for t in self._tokens) / len(self._tokens)

    def _idf(self, term):
        n = len(self.passages)
        df = self._doc_freq.get(term, 0)
        if df == 0:
            return 0.0
        # BM25 IDF, floored at zero so a term in every passage cannot
        # contribute negatively.
        return max(math.log(1 + (n - df + 0.5) / (df + 0.5)), 0.0)

    def search(self, question, top_k=4):
        """The best-matching passages, highest score first.

        Returns [] when nothing clears the relevance floor, which is how the
        server decides it has insufficient context.
        """
        query = tokenize(question)
        if not query or not self.passages:
            return []

        scored = []
        for i, freqs in enumerate(self._freqs):
            length = len(self._tokens[i])
            score = 0.0

            for term in query:
                tf = freqs.get(term, 0)
                if tf == 0:
                    continue
                denominator = tf + K1 * (1 - B + B * length / (self._avg_len or 1))
                score += self._idf(term) * (tf * (K1 + 1)) / denominator

            if score > 0:
                # A student's own records outrank general documentation. Asking
                # "when is my exam" should return the exam entry, not a page
                # describing what the exam feature does.
                scored.append((score * self.passages[i]["weight"], i))

        if not scored:
            return []

        scored.sort(reverse=True)
        if scored[0][0] < RELEVANCE_FLOOR:
            return []

        results = []
        for score, i in scored[:top_k]:
            passage = dict(self.passages[i])
            passage["score"] = round(score, 3)
            results.append(passage)
        return results


def confidence_from(results):
    """Map retrieval quality onto the four agreed categories.

    Based on the top score and how much corroborating context was found, so a
    single weak match is reported as low rather than presented confidently.
    """
    if not results:
        return "insufficient"

    top = results[0]["score"]
    if top >= 6.0 and len(results) >= 2:
        return "high"
    if top >= 3.0:
        return "medium"
    return "low"
