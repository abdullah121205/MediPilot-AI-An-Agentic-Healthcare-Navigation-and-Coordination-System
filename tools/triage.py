"""Mini-RAG: keyword (TF-IDF style) retrieval over triage guidelines. No dependencies.

    from tools.triage_rag import retrieve_guidelines
    hits = retrieve_guidelines("chest pain spreading to my arm")
    # each hit has text + source so the triage agent can cite it
"""
import json, math, os, re
from collections import Counter
from pathlib import Path

def _guidelines_path():
    root = Path(__file__).resolve().parent.parent
    env = os.environ.get("AGENTX_DATA_DIR")
    for d in ([Path(env)] if env else []) + [root / "data"]:
        if (d / "triage_guidelines.json").exists():
            return d / "triage_guidelines.json"
    return root / "data" / "triage_guidelines.json"


GUIDELINES = json.loads(_guidelines_path().read_text(encoding="utf-8"))
STOP = set("a an the and or of to in on at is are was i my me with for it that this have has be been from as by".split())


def _tokens(text):
    return [w for w in re.findall(r"[a-z]+", text.lower()) if w not in STOP and len(w) > 2]


_DOCS = [_tokens(g["topic"] + " " + g["topic"] + " " + g["text"]) for g in GUIDELINES]  # topic counted double
_DF = Counter(w for doc in _DOCS for w in set(doc))
_N = len(_DOCS)


def retrieve_guidelines(query: str, top_k: int = 3):
    q = _tokens(query)
    scored = []
    for g, doc in zip(GUIDELINES, _DOCS):
        tf = Counter(doc)
        score = sum((1 + math.log(tf[w])) * math.log(1 + _N / _DF[w]) for w in q if w in tf) / math.sqrt(len(doc))
        if score > 0:
            scored.append((score, g))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [{"id": g["id"], "urgency": g["urgency"], "source": g["source"], "url": g["url"],
             "guideline": g["text"], "score": round(s, 3)} for s, g in scored[:top_k]]