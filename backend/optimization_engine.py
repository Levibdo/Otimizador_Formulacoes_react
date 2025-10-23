import pandas as pd
from pulp import LpProblem, LpVariable, LpMinimize, lpSum, LpStatus

CUSTO_ROW_NAME = "Custo"


def otimizar_formula(materias_primas, restricoes, metas):
    model = LpProblem("Otimizador_de_Formulacoes", LpMinimize)

    # Variáveis de decisão (% inclusão)
    x = {
        mp: LpVariable(mp, 0, 100)
        for mp in materias_primas.columns
        if mp != CUSTO_ROW_NAME
    }

    # Função objetivo: minimizar custo
    model += lpSum(
        [materias_primas.loc[CUSTO_ROW_NAME, mp] * x[mp] / 100 for mp in x]
    ), "Custo_Total"

    # Restrição: soma das inclusões = 100%
    model += lpSum([x[mp] for mp in x]) == 100, "Total_100"

    # Restrições de matérias-primas
    for mp, (min_val, max_val) in restricoes.items():
        if mp in x:
            if min_val is not None:
                model += x[mp] >= min_val, f"{mp}_min"
            if max_val is not None:
                model += x[mp] <= max_val, f"{mp}_max"

    # Restrições nutricionais/metas
    for nutr, (min_val, max_val) in metas.items():
        if nutr in materias_primas.index:
            expr = lpSum(
                [materias_primas.loc[nutr, mp] * x[mp] / 100 for mp in x]
            )
            if min_val is not None:
                model += expr >= min_val, f"{nutr}_min"
            if max_val is not None:
                model += expr <= max_val, f"{nutr}_max"

    # Resolver modelo
    model.solve()
    status = LpStatus[model.status]

    # Inclusões finais
    resultado = {mp: round(x[mp].value(), 4) for mp in x}

    # Cálculo do custo total e individual
    custos = {}
    custo_total = 0
    for mp, v in resultado.items():
        c = materias_primas.loc[CUSTO_ROW_NAME, mp] * v / 100
        custos[mp] = round(c, 4)
        custo_total += c

    # 🔹 Calcular composição nutricional da fórmula
    conferencia_nutricional = {}
    for nutriente in materias_primas.index:
        if nutriente == CUSTO_ROW_NAME:
            continue
        valor = sum(materias_primas.loc[nutriente, mp] * resultado[mp] / 100 for mp in resultado)
        conferencia_nutricional[nutriente] = round(valor, 4)

    return {
        "status": status,
        "custo_total": round(custo_total, 4),
        "inclusoes": resultado,
        "custos_individuais": custos,
        "conferencia_nutricional": conferencia_nutricional,
    }
