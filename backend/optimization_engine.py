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

    # 🔹 Restrições de matérias-primas (limites individuais)
    for mp, (min_val, max_val) in restricoes.items():
        if mp in x:
            if min_val is not None:
                model += x[mp] >= min_val, f"{mp}_min"
            if max_val is not None:
                model += x[mp] <= max_val, f"{mp}_max"

    # 🔹 Restrições nutricionais/metas
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

    resultado = {mp: round(x[mp].value(), 4) for mp in x}

    # 🔹 Cálculo seguro do custo total
    try:
        custo_total = sum(
            materias_primas.loc[CUSTO_ROW_NAME, mp] * v / 100
            for mp, v in resultado.items()
        )
    except Exception:
        custo_total = None

    return {
        "status": status,
        "custo_total": round(custo_total, 4) if custo_total is not None else None,
        "inclusoes": resultado,
    }
