import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding
from pypdf import PdfReader

from emporio.store import normalize

EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache" / "fastembed"
HEADING = re.compile(r"^(\d{1,2}(?:\.\d)?)\.? (\S.*)$")
PAGE_NOISE = re.compile(r"^\s*(Página \d+|Empório da Música Manual de Políticas e Procedimentos)\s*$")
DENSE_WEIGHT = 0.5
STEM_LENGTH = 5
STOPWORDS = set(
    "a o as os de da do das dos e em no na nos nas um uma uns umas para por com que se ou ao aos "
    "meu minha meus minhas seu sua voces voce eu qual quais como quando onde posso pode e".split()
)


@dataclass(frozen=True)
class Section:
    id: str
    title: str
    text: str


def load_sections(pdf_path: Path) -> list[Section]:
    lines = [
        line
        for page in PdfReader(pdf_path).pages
        for line in page.extract_text(extraction_mode="layout").splitlines()
        if not PAGE_NOISE.match(line)
    ]
    sections: list[Section] = []
    titles: dict[str, str] = {}
    current: tuple[str, str] | None = None
    body: list[str] = []
    for line in lines:
        heading = HEADING.match(line)
        if heading:
            if current:
                sections.append(_section(*current, body))
            number, title = heading.groups()
            titles[number] = title.strip()
            parent = titles.get(number.split(".")[0]) if "." in number else None
            current = (number, f"{parent} > {title.strip()}" if parent else title.strip())
            body = []
        elif current:
            body.append(line)
    if current:
        sections.append(_section(*current, body))
    return [s for s in sections if s.text]


def _section(number: str, title: str, body: list[str]) -> Section:
    text = "\n".join(re.sub(r"\s+", " ", line).strip() for line in body if line.strip())
    return Section(id=number, title=title, text=text)


def tokenize(text: str) -> list[str]:
    words = re.findall(r"\w+", normalize(text))
    return [w[:STEM_LENGTH] for w in words if w not in STOPWORDS]


class LexicalIndex:
    def __init__(self, documents: list[str], k1: float = 1.5, b: float = 0.75):
        self.docs = [Counter(tokenize(d)) for d in documents]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.average = sum(self.lengths) / len(self.lengths)
        frequency = Counter(term for doc in self.docs for term in doc)
        self.idf = {t: math.log(1 + (len(self.docs) - n + 0.5) / (n + 0.5)) for t, n in frequency.items()}
        self.k1, self.b = k1, b

    def scores(self, query: str) -> np.ndarray:
        terms = tokenize(query)
        return np.array([
            sum(
                self.idf.get(t, 0) * doc[t] * (self.k1 + 1)
                / (doc[t] + self.k1 * (1 - self.b + self.b * length / self.average))
                for t in terms
            )
            for doc, length in zip(self.docs, self.lengths)
        ])


class PolicyIndex:
    def __init__(self, sections: list[Section], embedder: TextEmbedding, vectors: np.ndarray):
        self.sections = sections
        self.embedder = embedder
        self.vectors = vectors
        self.lexical = LexicalIndex([_document(s) for s in sections])

    @classmethod
    def build(cls, sections: list[Section]) -> "PolicyIndex":
        embedder = TextEmbedding(EMBEDDING_MODEL, cache_dir=str(CACHE_DIR))
        vectors = _unit(np.array(list(embedder.embed([_document(s) for s in sections]))))
        return cls(sections, embedder, vectors)

    def search(self, question: str, k: int = 3) -> list[Section]:
        query = _unit(np.array(list(self.embedder.embed([question]))))[0]
        fused = DENSE_WEIGHT * _rescale(self.vectors @ query) + (1 - DENSE_WEIGHT) * _rescale(
            self.lexical.scores(question)
        )
        return [self.sections[i] for i in np.argsort(fused)[::-1][:k]]


def _document(section: Section) -> str:
    return f"{section.title}\n{section.text}"


def _rescale(scores: np.ndarray) -> np.ndarray:
    spread = scores.max() - scores.min()
    return (scores - scores.min()) / spread if spread else np.zeros_like(scores)


def _unit(vectors: np.ndarray) -> np.ndarray:
    return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
