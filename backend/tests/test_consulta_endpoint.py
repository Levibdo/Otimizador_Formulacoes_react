import asyncio

import pytest

from main import consultar


class RequestFalso:
    def __init__(self, payload):
        self.payload = payload

    async def json(self):
        return self.payload


def test_consulta_utiliza_matriz_relacional_enviada_pelo_frontend():
    request = RequestFalso(
        {
            "formulacao": {"MP A": 25, "MP B": 75},
            "matriz": {
                "MP A": {"Custo": 10.0, "Proteína": 10.0},
                "MP B": {"Custo": 20.0, "Proteína": 30.0},
            },
        }
    )

    resultado = asyncio.run(consultar(request))

    assert resultado["status"] == "OK"
    assert resultado["custo_total"] == pytest.approx(17.5)
    assert resultado["nutrientes"] == [
        {"Nutriente": "Proteína", "Valor Obtido": pytest.approx(25.0)}
    ]
