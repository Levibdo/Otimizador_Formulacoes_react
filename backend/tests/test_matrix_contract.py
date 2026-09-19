import pytest

from matrix_contract import matriz_para_dataframe


def test_converte_contrato_canonico_em_dataframe_do_motor():
    matriz = {
        "Maltodextrina": {"Custo": 8.0, "Proteína": 0.0},
        "Proteína de soja": {"Custo": 25.0, "Proteína": 88.0},
    }

    resultado = matriz_para_dataframe(matriz)

    assert list(resultado.columns) == ["Maltodextrina", "Proteína de soja"]
    assert list(resultado.index) == ["Custo", "Proteína"]
    assert resultado.loc["Proteína", "Proteína de soja"] == pytest.approx(88.0)


def test_mantem_compatibilidade_com_formato_transposto_antigo():
    matriz_antiga = {
        "Custo": {"Maltodextrina": 8.0, "Proteína de soja": 25.0},
        "Proteína": {"Maltodextrina": 0.0, "Proteína de soja": 88.0},
    }

    resultado = matriz_para_dataframe(matriz_antiga)

    assert list(resultado.columns) == ["Maltodextrina", "Proteína de soja"]
    assert resultado.loc["Custo", "Maltodextrina"] == pytest.approx(8.0)


@pytest.mark.parametrize(
    "matriz, mensagem",
    [
        ({}, "vazia ou é inválida"),
        ({"MP sem custo": {"Proteína": 10.0}}, "deve informar o custo"),
        ({"MP": {"Custo": "inválido"}}, "devem ser numéricos"),
    ],
)
def test_rejeita_matriz_invalida(matriz, mensagem):
    with pytest.raises(ValueError, match=mensagem):
        matriz_para_dataframe(matriz)


def test_dataframe_resultante_pode_ser_otimizado():
    from optimization_engine import otimizar_formula

    dataframe = matriz_para_dataframe(
        {
            "MP barata": {"Custo": 10.0, "Proteína": 10.0},
            "MP proteica": {"Custo": 20.0, "Proteína": 30.0},
        }
    )

    resultado = otimizar_formula(
        dataframe,
        restricoes={},
        metas={"Proteína": (20.0, None)},
    )

    assert resultado["status"] == "Optimal"
    assert resultado["custo_total"] == pytest.approx(15.0)
