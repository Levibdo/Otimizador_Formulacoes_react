import asyncio
import logging

import pytest

from main import consultar, optimize


class RequestFalso:
    def __init__(self, payload):
        self.payload = payload

    async def json(self):
        return self.payload


def test_endpoint_otimiza_matriz_no_contrato_canonico():
    request = RequestFalso(
        {
            "matriz": {
                "MP barata": {"Custo": 10.0, "Proteína": 10.0},
                "MP proteica": {"Custo": 20.0, "Proteína": 30.0},
            },
            "metas": {"Proteína": [20.0, None]},
            "restricoes": {},
            "custo_max": 15.0,
        }
    )

    resultado = asyncio.run(optimize(request))

    assert resultado["status"] == "Optimal"
    assert resultado["custo_total"] == pytest.approx(15.0)
    assert resultado["inclusoes"]["MP barata"] == pytest.approx(50.0)


def test_endpoint_legado_nao_expoe_detalhe_interno(caplog):
    request = RequestFalso(
        {
            "matriz": {"MP": {"Proteína": 10.0}},
            "metas": {},
            "restricoes": {},
        }
    )

    with caplog.at_level(logging.ERROR):
        resultado = asyncio.run(optimize(request))

    assert resultado == {"erro": "Não foi possível executar a otimização."}
    assert "custo" not in resultado["erro"].lower()
    assert "deve informar o custo" in caplog.text.lower()


def test_consulta_legada_nao_expoe_detalhe_interno(caplog):
    request = RequestFalso({"formulacao": {}, "matriz": {}})

    with caplog.at_level(logging.ERROR):
        resultado = asyncio.run(consultar(request))

    assert resultado == {"erro": "Não foi possível consultar a formulação."}
    assert "nenhuma matéria-prima" not in resultado["erro"].lower()
    assert "matriz de matérias-primas está vazia" in caplog.text.lower()
