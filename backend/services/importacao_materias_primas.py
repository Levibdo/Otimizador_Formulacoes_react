import io
import re
import unicodedata
from datetime import date

import pandas as pd

from schemas import ComposicaoCreate, MateriaPrimaCreate, PrecoCreate


class PlanilhaImportacaoError(ValueError):
    pass


def _slug(valor: str) -> str:
    normalizado = "".join(
        caractere
        for caractere in unicodedata.normalize("NFD", str(valor))
        if unicodedata.category(caractere) != "Mn"
    )
    return re.sub(r"[^A-Z0-9]+", "_", normalizado.upper()).strip("_")


def _codigo_unico(prefixo: str, nome: str, usados: set[str]) -> str:
    base = f"{prefixo}_{_slug(nome)}"[:30].rstrip("_") or prefixo
    codigo = base
    contador = 2
    while codigo in usados:
        sufixo = f"_{contador}"
        codigo = f"{base[:30 - len(sufixo)]}{sufixo}"
        contador += 1
    usados.add(codigo)
    return codigo


def _nome_e_unidade(rotulo: str, unidade_padrao: str) -> tuple[str, str]:
    texto = str(rotulo).strip().replace("_nutriente", "")
    if re.search(r",?\s*g\s*/\s*100\s*g\s*$", texto, flags=re.IGNORECASE):
        nome = re.sub(
            r",?\s*g\s*/\s*100\s*g\s*$",
            "",
            texto,
            flags=re.IGNORECASE,
        ).strip()
        return nome, "g/100 g"
    if "(kcal)" in texto.lower():
        return re.sub(r"\s*\(kcal\)\s*", "", texto, flags=re.IGNORECASE), "kcal/100 g"
    return texto, unidade_padrao


def _ler_arquivo(conteudo: bytes, nome_arquivo: str, header=None) -> pd.DataFrame:
    nome = nome_arquivo.lower()
    if nome.endswith(".xlsx"):
        return pd.read_excel(io.BytesIO(conteudo), header=header)
    if nome.endswith(".csv"):
        return pd.read_csv(
            io.BytesIO(conteudo),
            header=header,
            sep=None,
            engine="python",
            encoding="utf-8-sig",
        )
    raise PlanilhaImportacaoError("Formato não suportado. Use .xlsx ou .csv.")


def _numero(valor, contexto: str) -> float:
    convertido = pd.to_numeric(valor, errors="coerce")
    if pd.isna(convertido):
        raise PlanilhaImportacaoError(f"Valor numérico inválido em {contexto}.")
    if float(convertido) < 0:
        raise PlanilhaImportacaoError(f"Valor negativo não permitido em {contexto}.")
    return float(convertido)


def _parsear_transposta(
    dataframe: pd.DataFrame,
    vigencia_inicio: date,
    unidade_padrao: str,
) -> list[MateriaPrimaCreate]:
    nomes_mp = [str(valor).strip() for valor in dataframe.iloc[0, 1:].tolist()]
    custos = dataframe.iloc[1, 1:].tolist()
    linhas_nutrientes = dataframe.iloc[2:, :]
    codigos_mp = set()
    codigos_nutrientes = {}
    codigos_nutrientes_usados = set()
    resultado = []

    if not nomes_mp or any(not nome or nome.lower() == "nan" for nome in nomes_mp):
        raise PlanilhaImportacaoError("A primeira linha deve informar o nome de todas as MPs.")
    if len(set(nomes_mp)) != len(nomes_mp):
        raise PlanilhaImportacaoError("A planilha contém nomes de MPs duplicados.")

    for indice_mp, nome_mp in enumerate(nomes_mp, start=1):
        composicao = []
        for _, linha in linhas_nutrientes.iterrows():
            rotulo = linha.iloc[0]
            if pd.isna(rotulo):
                continue
            nome_nutriente, unidade = _nome_e_unidade(rotulo, unidade_padrao)
            chave = _slug(nome_nutriente)
            if chave not in codigos_nutrientes:
                codigos_nutrientes[chave] = _codigo_unico(
                    "NUT", nome_nutriente, codigos_nutrientes_usados
                )
            codigo_nutriente = codigos_nutrientes[chave]
            composicao.append(
                ComposicaoCreate(
                    nutriente_codigo=codigo_nutriente,
                    nutriente_nome=nome_nutriente,
                    unidade=unidade,
                    valor=_numero(linha.iloc[indice_mp], f"{nome_mp} / {nome_nutriente}"),
                )
            )

        resultado.append(
            MateriaPrimaCreate(
                codigo=_codigo_unico("MP", nome_mp, codigos_mp),
                nome=nome_mp,
                composicao=composicao,
                preco_inicial=PrecoCreate(
                    preco_kg=_numero(custos[indice_mp - 1], f"custo de {nome_mp}"),
                    vigencia_inicio=vigencia_inicio,
                ),
            )
        )
    return resultado


def _encontrar_coluna(colunas, candidatos):
    normalizadas = {_slug(coluna): coluna for coluna in colunas}
    for candidato in candidatos:
        if candidato in normalizadas:
            return normalizadas[candidato]
    return None


def _parsear_vertical(
    dataframe: pd.DataFrame,
    vigencia_inicio: date,
    unidade_padrao: str,
) -> list[MateriaPrimaCreate]:
    coluna_nome = _encontrar_coluna(
        dataframe.columns, {"NOME", "MATERIA_PRIMA", "MATERIA PRIMA"}
    )
    coluna_codigo = _encontrar_coluna(dataframe.columns, {"CODIGO", "CODIGO_MP"})
    coluna_custo = _encontrar_coluna(dataframe.columns, {"CUSTO", "PRECO", "PRECO_KG"})
    if coluna_nome is None or coluna_custo is None:
        raise PlanilhaImportacaoError(
            "O formato vertical deve possuir as colunas Nome e Custo."
        )

    colunas_reservadas = {coluna_nome, coluna_codigo, coluna_custo}
    colunas_nutrientes = [
        coluna for coluna in dataframe.columns if coluna not in colunas_reservadas
    ]
    codigos_mp = set()
    codigos_nutrientes_usados = set()
    codigos_nutrientes = {
        coluna: _codigo_unico(
            "NUT",
            _nome_e_unidade(coluna, unidade_padrao)[0],
            codigos_nutrientes_usados,
        )
        for coluna in colunas_nutrientes
    }
    resultado = []

    for indice, linha in dataframe.iterrows():
        nome_mp = str(linha[coluna_nome]).strip()
        if not nome_mp or nome_mp.lower() == "nan":
            raise PlanilhaImportacaoError(f"Nome de MP ausente na linha {indice + 2}.")
        codigo_informado = (
            str(linha[coluna_codigo]).strip()
            if coluna_codigo is not None and pd.notna(linha[coluna_codigo])
            else None
        )
        if codigo_informado:
            codigo = codigo_informado[:30]
            if codigo in codigos_mp:
                raise PlanilhaImportacaoError(f"Código de MP duplicado: {codigo}.")
            codigos_mp.add(codigo)
        else:
            codigo = _codigo_unico("MP", nome_mp, codigos_mp)

        composicao = []
        for coluna in colunas_nutrientes:
            nome_nutriente, unidade = _nome_e_unidade(coluna, unidade_padrao)
            composicao.append(
                ComposicaoCreate(
                    nutriente_codigo=codigos_nutrientes[coluna],
                    nutriente_nome=nome_nutriente,
                    unidade=unidade,
                    valor=_numero(linha[coluna], f"linha {indice + 2} / {nome_nutriente}"),
                )
            )

        resultado.append(
            MateriaPrimaCreate(
                codigo=codigo,
                nome=nome_mp,
                composicao=composicao,
                preco_inicial=PrecoCreate(
                    preco_kg=_numero(linha[coluna_custo], f"custo de {nome_mp}"),
                    vigencia_inicio=vigencia_inicio,
                ),
            )
        )
    return resultado


def parsear_planilha(
    conteudo: bytes,
    nome_arquivo: str,
    vigencia_inicio: date,
    unidade_padrao: str = "não informada",
) -> list[MateriaPrimaCreate]:
    if not unidade_padrao.strip():
        raise PlanilhaImportacaoError("A unidade padrão não pode ser vazia.")
    dataframe_bruto = _ler_arquivo(conteudo, nome_arquivo, header=None)
    if dataframe_bruto.empty:
        raise PlanilhaImportacaoError("A planilha está vazia.")

    segunda_linha = (
        str(dataframe_bruto.iat[1, 0]).strip().lower()
        if dataframe_bruto.shape[0] > 1
        else ""
    )
    if segunda_linha == "custo":
        return _parsear_transposta(
            dataframe_bruto,
            vigencia_inicio,
            unidade_padrao,
        )

    dataframe_vertical = _ler_arquivo(conteudo, nome_arquivo, header=0)
    return _parsear_vertical(dataframe_vertical, vigencia_inicio, unidade_padrao)
