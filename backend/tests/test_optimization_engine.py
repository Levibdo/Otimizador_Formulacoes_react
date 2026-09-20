import pandas as pd
import pytest

from optimization_engine import otimizar_formula


@pytest.fixture
def materias_primas():
    return pd.DataFrame(
        {
            "MP barata": {"Custo": 10.0, "Proteína": 10.0},
            "MP proteica": {"Custo": 20.0, "Proteína": 30.0},
        }
    )


def test_minimiza_custo_respeitando_meta_nutricional(materias_primas):
    resultado = otimizar_formula(
        materias_primas,
        restricoes={},
        metas={"Proteína": (20.0, None)},
    )

    assert resultado["status"] == "Optimal"
    assert resultado["custo_total"] == pytest.approx(15.0)
    assert resultado["inclusoes"] == {
        "MP barata": pytest.approx(50.0),
        "MP proteica": pytest.approx(50.0),
    }
    assert resultado["conferencia_nutricional"]["Proteína"] == pytest.approx(20.0)
    assert resultado["resultado_bruto"]["inclusoes"]["MP barata"] == pytest.approx(50.0)


def test_aplica_limites_de_materia_prima(materias_primas):
    resultado = otimizar_formula(
        materias_primas,
        restricoes={"MP barata": (None, 25.0)},
        metas={},
    )

    assert resultado["status"] == "Optimal"
    assert resultado["inclusoes"]["MP barata"] == pytest.approx(25.0)
    assert resultado["inclusoes"]["MP proteica"] == pytest.approx(75.0)
    assert resultado["custo_total"] == pytest.approx(17.5)


def test_aceita_solucao_no_limite_exato_de_custo(materias_primas):
    resultado = otimizar_formula(
        materias_primas,
        restricoes={},
        metas={"Proteína": (20.0, None)},
        custo_max=15.0,
    )

    assert resultado["status"] == "Optimal"
    assert resultado["custo_total"] == pytest.approx(15.0)


def test_retorna_resultado_estruturado_quando_custo_maximo_e_inviavel(
    materias_primas,
):
    resultado = otimizar_formula(
        materias_primas,
        restricoes={},
        metas={"Proteína": (20.0, None)},
        custo_max=14.99,
    )

    assert resultado == {
        "status": "Infeasible",
        "custo_total": None,
        "inclusoes": {},
        "custos_individuais": {},
        "conferencia_nutricional": {},
    }


def test_rejeita_custo_maximo_negativo(materias_primas):
    with pytest.raises(ValueError, match="não pode ser negativo"):
        otimizar_formula(
            materias_primas,
            restricoes={},
            metas={},
            custo_max=-1,
        )


def test_aplica_limite_agregado_de_componente_em_varias_mps(materias_primas):
    resultado = otimizar_formula(
        materias_primas,
        restricoes={},
        metas={},
        restricoes_agregadas={"COMP": ({"MP barata": 20, "MP proteica": 0}, None, 10)},
    )
    assert resultado["status"] == "Optimal"
    assert resultado["inclusoes"]["MP barata"] == pytest.approx(50)
