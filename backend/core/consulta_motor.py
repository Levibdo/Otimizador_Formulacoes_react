import pandas as pd

CUSTO_ROW_NAME = "Custo"

def calcular_nutrientes_e_custo(materias_primas, formulacao_input):
    inclusao = pd.Series(formulacao_input) / 100.0
    mps_validas = [mp for mp in inclusao.index if mp in materias_primas.columns]
    inclusao = inclusao.loc[mps_validas]

    if inclusao.sum() == 0:
        return pd.DataFrame(), 0.0

    matriz_nutrientes = materias_primas.drop(index=[CUSTO_ROW_NAME], errors='ignore')
    composicao_por_mp = matriz_nutrientes.mul(inclusao, axis=1)
    composicao_total = composicao_por_mp.sum(axis=1)

    df_nutricional = pd.DataFrame({
        'Nutriente': composicao_total.index,
        'Valor Obtido': composicao_total.values
    })

    custos_unitarios = materias_primas.loc[CUSTO_ROW_NAME, inclusao.index]
    custo_total = (inclusao * custos_unitarios).sum()

    return df_nutricional, custo_total
