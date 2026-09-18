import asyncio

import pytest

from main import optimize


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


def test_endpoint_rejeita_matriz_sem_custos():
    request = RequestFalso(
        {
            "matriz": {"MP": {"Proteína": 10.0}},
            "metas": {},
            "restricoes": {},
        }
    )

    resultado = asyncio.run(optimize(request))

    assert "erro" in resultado
    assert "deve informar o custo" in resultado["erro"]
