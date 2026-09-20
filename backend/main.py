import os
import sys
import unicodedata

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from matrix_contract import matriz_para_dataframe
from optimization_engine import CUSTO_ROW_NAME, otimizar_formula
from routers import (
    apresentacoes_router,
    cenarios_router,
    materias_primas_router,
    projetos_router,
    regulatorio_router,
    otimizacoes_router,
)


sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

app = FastAPI(
    title="Otimizador de Formulações API",
    description="API PostgreSQL para formulações, projetos, custos e cenários.",
)
app.include_router(materias_primas_router)
app.include_router(projetos_router)
app.include_router(apresentacoes_router)
app.include_router(cenarios_router)
app.include_router(regulatorio_router)
app.include_router(otimizacoes_router)

origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost,http://127.0.0.1,http://localhost:5173,http://127.0.0.1:5173",
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def normalizar_nome(nome):
    sem_acentos = "".join(
        caractere
        for caractere in unicodedata.normalize("NFD", str(nome))
        if unicodedata.category(caractere) != "Mn"
    )
    return sem_acentos.strip().lower().replace("_", " ")


@app.get("/")
def root():
    return {
        "message": "API do Otimizador de Formulações rodando com sucesso!",
        "fonte_dados": "PostgreSQL",
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/optimize")
async def optimize(request: Request):
    try:
        body = await request.json()
        matriz = matriz_para_dataframe(body.get("matriz"))
        return otimizar_formula(
            matriz,
            restricoes=body.get("restricoes", {}),
            metas=body.get("metas", {}),
            custo_max=body.get("custo_max"),
        )
    except Exception as exc:
        return {"erro": str(exc)}


@app.post("/consulta")
async def consultar(request: Request):
    try:
        body = await request.json()
        formulacao = body.get("formulacao", body)
        matriz = matriz_para_dataframe(body.get("matriz"))
        colunas_normalizadas = {
            normalizar_nome(coluna): coluna for coluna in matriz.columns
        }
        proporcoes_validas = {}

        for materia_prima, valor in formulacao.items():
            try:
                valor_numerico = float(valor)
                nome_canonico = colunas_normalizadas.get(
                    normalizar_nome(materia_prima)
                )
                if valor_numerico > 0 and nome_canonico:
                    proporcoes_validas[nome_canonico] = valor_numerico
            except (TypeError, ValueError):
                continue

        if not proporcoes_validas:
            raise ValueError("Nenhuma matéria-prima válida foi informada.")

        proporcoes = pd.Series(proporcoes_validas, dtype=float)
        proporcoes = proporcoes / proporcoes.sum()
        matriz_filtrada = matriz[proporcoes.index]
        nutrientes = matriz_filtrada.drop(
            index=CUSTO_ROW_NAME, errors="ignore"
        ).dot(proporcoes)
        custo_por_mp = matriz_filtrada.loc[CUSTO_ROW_NAME] * proporcoes

        return {
            "status": "OK",
            "nutrientes": [
                {"Nutriente": nome, "Valor Obtido": valor}
                for nome, valor in nutrientes.items()
            ],
            "custos": [
                {"Matéria-Prima": nome, "Custo": custo}
                for nome, custo in custo_por_mp.items()
            ],
            "custo_total": custo_por_mp.sum(),
        }
    except Exception as exc:
        return {"erro": str(exc)}
