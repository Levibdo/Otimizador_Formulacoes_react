import pytest
from pydantic import ValidationError

from schemas.regulatorio import CategoriaCreate, CategoriaUpdate, ComponenteCreate, ComposicaoCreate, RegraCreate


def regra(**changes):
    return dict(categoria_id=1, tipo_alvo='MATERIA_PRIMA', materia_prima_id=1,
                tratamento='PERMITIDA', justificativa='Regra manual de teste') | changes


@pytest.mark.parametrize('changes', [
    {'componente_id': 2}, {'materia_prima_id': None}, {'tipo_alvo': 'COMPONENTE'},
    {'minimo': -1}, {'maximo': 101}, {'minimo': 20, 'maximo': 10},
    {'tratamento': 'OBRIGATORIA'}, {'tratamento': 'OBRIGATORIA', 'minimo': 0},
    {'tratamento': 'PROIBIDA', 'maximo': 1}, {'tratamento': 'PROIBIDA', 'minimo': 1},
    {'tratamento': 'LIMITADA'}, {'base': 'PORCAO'}, {'unidade': 'mg'},
    {'vigencia_inicio': '2026-02-01', 'vigencia_fim': '2026-01-01'},
    {'justificativa': '   '}, {'maximo': 'NaN'}, {'minimo': '0.0000001'},
])
def test_schema_rejeita_regra_invalida(changes):
    with pytest.raises(ValidationError):
        RegraCreate(**regra(**changes))


def test_schema_normaliza_proibida_e_aceita_componente():
    assert RegraCreate(**regra(tratamento='PROIBIDA')).maximo == 0
    componente = RegraCreate(**regra(tipo_alvo='COMPONENTE', materia_prima_id=None,
                                      componente_id=3, tratamento='OBRIGATORIA', minimo=1))
    assert componente.minimo == 1


@pytest.mark.parametrize('situacao,concentracao', [
    ('INFORMADO', None), ('AUSENTE_CONFIRMADO', None), ('AUSENTE_CONFIRMADO', 1),
    ('DESCONHECIDO', 0), ('INFORMADO', -1), ('INFORMADO', 101),
])
def test_schema_rejeita_concentracao_incoerente(situacao, concentracao):
    with pytest.raises(ValidationError):
        ComposicaoCreate(componente_id=1, data_referencia='2026-01-01',
                         situacao=situacao, concentracao=concentracao)


@pytest.mark.parametrize('codigo', ['', 'espaço', 'A B', '123', 'a'])
def test_codigo_estavel_tem_formato_controlado(codigo):
    with pytest.raises(ValidationError):
        CategoriaCreate(codigo=codigo, nome='Categoria')


def test_edicao_nao_admite_codigo_e_base_do_componente_e_fixa():
    with pytest.raises(ValidationError):
        CategoriaUpdate(codigo='OUTRO')
    with pytest.raises(ValidationError):
        CategoriaUpdate(ativa=None)
    with pytest.raises(ValidationError):
        ComponenteCreate(codigo='S', nome='S', base='VOLUME')
