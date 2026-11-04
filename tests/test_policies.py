import pytest

from emporio.policies import PolicyIndex, load_sections
from tests.conftest import DATA_DIR

POLICIES_PDF = DATA_DIR / "store_policies.pdf"


@pytest.fixture(scope="module")
def sections():
    return load_sections(POLICIES_PDF)


@pytest.fixture(scope="module")
def index(sections):
    return PolicyIndex.build(sections)


def test_one_chunk_per_numbered_section_with_content(sections):
    assert [s.id for s in sections] == [
        "1", "1.1", "1.2", "2", "3", "3.1", "4", "4.1", "4.2", "4.3", "4.4",
        "5.1", "5.2", "5.3", "6.1", "6.2", "7", "7.1", "7.2", "7.3",
        "8.1", "8.2", "8.3", "9", "10",
    ]


def test_subsection_carries_parent_title(sections):
    section = next(s for s in sections if s.id == "4.4")
    assert section.title == "Política de Trocas e Devoluções > Itens Não Elegíveis para Troca"
    assert "Boquilhas" in section.text


def test_page_headers_and_footers_are_removed(sections):
    assert not any("Página" in s.text or "Manual de Políticas e Procedimentos" in s.text for s in sections)


def test_section_spanning_two_pages_stays_whole(sections):
    section = next(s for s in sections if s.id == "5.2")
    assert "SEDEX" in section.text
    assert "seguro contra extravios" in section.text


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("Posso trocar a boquilha do meu saxofone?", {"4.4"}),
        ("A loja abre no domingo?", {"2"}),
        ("O desconto do PIX vale para produto em promoção?", {"6.2"}),
        ("Me arrependi da compra online, posso devolver?", {"4.1"}),
        ("Meu violão veio com defeito, o que eu faço?", {"4.2", "8.1"}),
        ("Quero trocar a cor da guitarra que comprei", {"4.3"}),
        ("Quanto custa o frete em Campo Grande?", {"5.1"}),
        ("Vocês entregam em Dourados? Quanto tempo demora?", {"5.2"}),
        ("Como eu rastreio meu pedido?", {"5.3"}),
        ("Posso parcelar em 12 vezes no cartão?", {"3", "3.1"}),
        ("Qual a garantia dos instrumentos?", {"8.1", "8.2"}),
        ("A garantia cobre se o instrumento cair no chão?", {"8.3"}),
        ("Vocês vendem cordas e amplificadores?", {"1", "7.1"}),
        ("Qual o endereço da loja?", {"1.2"}),
        ("Como vocês usam meus dados pessoais?", {"9"}),
        ("Quando é a Black Friday?", {"6.1"}),
    ],
)
def test_retrieval_hits_the_right_section_in_top_3(index, question, expected):
    found = {s.id for s in index.search(question, k=3)}
    assert found & expected
