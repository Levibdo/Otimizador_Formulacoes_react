import pandas as pd


CUSTO_ROW_NAME = "Custo"
METADADOS_DOCUMENTO = {"_id", "usuario_id", "nome"}


def documentos_para_matriz(documentos):
    """Converte documentos de MPs para o contrato MP -> atributos."""
    matriz = {}

    for documento in documentos:
        nome = documento.get("nome")
        if not nome:
            raise ValueError("Toda matéria-prima deve possuir um nome.")

        matriz[nome] = {
            chave: valor
            for chave, valor in documento.items()
            if chave not in METADADOS_DOCUMENTO
        }

    return matriz


def matriz_para_dataframe(matriz):
    """Converte o contrato JSON em DataFrame aceito pelo motor.

    O formato canônico possui matérias-primas nas chaves externas. O formato
    transposto usado anteriormente pelo MongoDB continua aceito durante a
    transição.
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
