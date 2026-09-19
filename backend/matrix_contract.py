import pandas as pd


CUSTO_ROW_NAME = "Custo"


def matriz_para_dataframe(matriz):
    """Converte o contrato JSON em DataFrame aceito pelo motor.

    O formato canônico possui matérias-primas nas chaves externas. O formato
    transposto também é aceito para facilitar integrações e importações.
    """
    if not isinstance(matriz, dict) or not matriz:
        raise ValueError("A matriz de matérias-primas está vazia ou é inválida.")

    dataframe = pd.DataFrame(matriz)

    if CUSTO_ROW_NAME in dataframe.index:
        resultado = dataframe
    elif CUSTO_ROW_NAME in dataframe.columns:
        resultado = dataframe.T
    else:
        raise ValueError("A matriz deve informar o custo de cada matéria-prima.")

    resultado = resultado.apply(pd.to_numeric, errors="coerce")
    if resultado.loc[CUSTO_ROW_NAME].isna().any():
        raise ValueError("Todos os custos das matérias-primas devem ser numéricos.")

    return resultado.fillna(0.0)
