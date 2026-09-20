import pytest
from pydantic import ValidationError

from schemas.otimizacao import OtimizacaoCreate
from schemas.projeto import VersaoFormulaCreate


def test_cliente_so_pode_enviar_escolhas_e_limites():
    dados = OtimizacaoCreate.model_validate({
        "materias_primas_ids": [1, 2],
        "limites_tecnicos": [{"materia_prima_id": 1, "minimo": 10, "maximo": 20}],
    })
    assert dados.limites_tecnicos[0].minimo == 10
    for campo in ("precos", "matriz", "composicoes", "regras"):
        with pytest.raises(ValidationError):
            OtimizacaoCreate.model_validate({campo: {}})


def test_versao_por_execucao_rejeita_resultado_fornecido_pelo_cliente():
    assert VersaoFormulaCreate(execucao_id=1).execucao_id == 1
    with pytest.raises(ValidationError, match="servidor obtém"):
        VersaoFormulaCreate(execucao_id=1, custo_total=1)
