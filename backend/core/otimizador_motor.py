from pulp import LpProblem, LpVariable, LpMinimize, lpSum, PulpSolverError
import pandas as pd

CUSTO_ROW_NAME = "Custo"

def otimizar_formula(materias_primas, metas, limites_mp):
    try:
        problema = LpProblem("Otimizacao_de_Formulacao", LpMinimize)
        mps = materias_primas.columns
        x = {mp: LpVariable(mp, 0, 100) for mp in mps}

        # Função objetivo: minimizar custo
        problema += lpSum([materias_primas.loc[CUSTO_ROW_NAME, mp] * x[mp] for mp in mps])

        # Soma das MPs = 100%
        problema += lpSum([x[mp] for mp in mps]) == 100

        # Restrições nutricionais
        for nutriente, valor in metas.items():
            if nutriente in materias_primas.index:
                problema += lpSum([materias_primas.loc[nutriente, mp] * x[mp] / 100 for mp in mps]) >= valor

        # Limites individuais de MPs
        for mp, (min_, max_) in limites_mp.items():
            if mp in x:
                problema += x[mp] >= min_
                problema += x[mp] <= max_

        problema.solve()

        resultado = {mp: round(x[mp].value(), 3) for mp in mps}
        custo_total = sum(resultado[mp] * materias_primas.loc[CUSTO_ROW_NAME, mp] / 100 for mp in mps)
        return {"status": "Ótimo", "custo_total": round(custo_total, 4), "formula": resultado}

    except PulpSolverError:
        return None
