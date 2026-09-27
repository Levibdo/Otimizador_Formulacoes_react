import io
import re
import unicodedata
import zipfile
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill


VERSAO_CONTRATO = "1.0"
VERSAO_TEMPLATE_PADRAO = "1.1"
VERSOES_SUPORTADAS = ("1.0", "1.1")
ABAS_V1_0 = {
    "LEIA_ME": ("CHAVE", "VALOR"),
    "MATERIAS_PRIMAS": ("ACAO", "CODIGO", "NOME", "ATIVA"),
    "NUTRIENTES": ("ACAO", "CODIGO", "NOME", "UNIDADE"),
    "COMPOSICAO_NUTRICIONAL": (
        "ACAO",
        "MATERIA_PRIMA_CODIGO",
        "NUTRIENTE_CODIGO",
        "VALOR",
    ),
    "PRECOS_MP": (
        "ACAO",
        "MATERIA_PRIMA_CODIGO",
        "PRECO_KG",
        "VIGENCIA_INICIO",
        "VIGENCIA_FIM",
    ),
}
ABAS_REGULATORIAS = {
    "CATEGORIAS_PRODUTO": ("ACAO", "CODIGO", "NOME", "DESCRICAO"),
    "COMPONENTES_REGULATORIOS": ("ACAO", "CODIGO", "NOME", "DESCRICAO"),
    "COMPOSICAO_COMPONENTES_MP": (
        "ACAO", "MATERIA_PRIMA_CODIGO", "COMPONENTE_CODIGO", "DATA_REFERENCIA",
        "SITUACAO", "CONCENTRACAO", "FONTE", "OBSERVACAO",
    ),
    "REGRAS_REGULATORIAS_MP": (
        "ACAO", "CATEGORIA_CODIGO", "MATERIA_PRIMA_CODIGO", "TRATAMENTO",
        "MINIMO", "MAXIMO", "JUSTIFICATIVA", "REFERENCIA_NORMATIVA",
        "VIGENCIA_INICIO", "VIGENCIA_FIM",
    ),
    "REGRAS_REGULATORIAS_COMPONENTE": (
        "ACAO", "CATEGORIA_CODIGO", "COMPONENTE_CODIGO", "TRATAMENTO",
        "MINIMO", "MAXIMO", "JUSTIFICATIVA", "REFERENCIA_NORMATIVA",
        "VIGENCIA_INICIO", "VIGENCIA_FIM",
    ),
}
ABAS_V1_1 = {**ABAS_V1_0, **ABAS_REGULATORIAS}
ABAS_POR_VERSAO = {"1.0": ABAS_V1_0, "1.1": ABAS_V1_1}
# Compatibilidade: a pré-validação PostgreSQL será ampliada somente no Bloco 2.
ABAS = ABAS_V1_0
ACOES = {"CRIAR", "ATUALIZAR", "DESATIVAR"}
ACOES_POR_ABA = {
    "MATERIAS_PRIMAS": {"CRIAR", "ATUALIZAR", "DESATIVAR"},
    "NUTRIENTES": {"CRIAR", "ATUALIZAR"},
    "COMPOSICAO_NUTRICIONAL": {"CRIAR", "ATUALIZAR"},
    "PRECOS_MP": {"CRIAR"},
    "CATEGORIAS_PRODUTO": ACOES,
    "COMPONENTES_REGULATORIOS": ACOES,
    "COMPOSICAO_COMPONENTES_MP": {"CRIAR", "DESATIVAR"},
    "REGRAS_REGULATORIAS_MP": ACOES,
    "REGRAS_REGULATORIAS_COMPONENTE": ACOES,
}
PADRAO_CODIGO = re.compile(r"^[A-Z][A-Z0-9_]{0,29}$")
PADRAO_CODIGO_REGULATORIO = re.compile(r"^[A-Z][A-Z0-9_]{0,49}$")
PADRAO_DATA_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SITUACOES_COMPONENTE = {"INFORMADO", "AUSENTE_CONFIRMADO", "DESCONHECIDO"}
TRATAMENTOS = {"PERMITIDA", "PROIBIDA", "OBRIGATORIA", "LIMITADA"}

MAX_ARQUIVO_BYTES = 5 * 1024 * 1024
MAX_DESCOMPRIMIDO_BYTES = 30 * 1024 * 1024
MAX_ENTRADAS_ZIP = 200
MAX_RAZAO_COMPRESSAO = 100
MAX_ABAS_POR_VERSAO = {versao: len(abas) for versao, abas in ABAS_POR_VERSAO.items()}
MAX_ABAS_SUPORTADO = max(MAX_ABAS_POR_VERSAO.values())
MAX_ABAS = 5  # usado exclusivamente pelo parser legado v1.0
MAX_LINHAS_POR_ABA = 5_000
MAX_COLUNAS_POR_ABA = 12
MAX_CELULAS_TOTAL = 100_000


def _token(valor) -> str:
    texto = "".join(
        caractere
        for caractere in unicodedata.normalize("NFD", str(valor or "").strip())
        if unicodedata.category(caractere) != "Mn"
    )
    return re.sub(r"[^A-Z0-9]+", "_", texto.upper()).strip("_")


def _vazio(valor) -> bool:
    return valor is None or (isinstance(valor, str) and not valor.strip())


def _texto(valor):
    return None if _vazio(valor) else str(valor).strip()


def _diagnostico(severidade, aba, mensagem, linha=None, coluna=None, codigo=None):
    return {
        "severidade": severidade,
        "aba": aba,
        "linha": linha,
        "coluna": coluna,
        "codigo": codigo,
        "mensagem": mensagem,
    }


def _numero(valor, aba, linha, coluna, diagnosticos, obrigatorio=True):
    if _vazio(valor):
        if obrigatorio:
            diagnosticos.append(_diagnostico("ERRO", aba, "Valor obrigatório ausente.", linha, coluna))
        return None
    if isinstance(valor, bool):
        diagnosticos.append(_diagnostico("ERRO", aba, "Valor numérico inválido.", linha, coluna))
        return None
    try:
        numero = Decimal(str(valor).strip())
    except (InvalidOperation, ValueError):
        diagnosticos.append(_diagnostico("ERRO", aba, "Valor numérico inválido.", linha, coluna))
        return None
    if not numero.is_finite():
        diagnosticos.append(_diagnostico("ERRO", aba, "Valor numérico deve ser finito.", linha, coluna))
        return None
    if numero < 0:
        diagnosticos.append(_diagnostico("ERRO", aba, "Valor negativo não permitido.", linha, coluna))
        return None
    return format(numero, "f")


def _booleano(valor, aba, linha, coluna, diagnosticos, obrigatorio=False):
    if _vazio(valor):
        if obrigatorio:
            diagnosticos.append(_diagnostico("ERRO", aba, "Valor booleano obrigatório ausente.", linha, coluna))
        return None
    if not isinstance(valor, str):
        diagnosticos.append(
            _diagnostico("ERRO", aba, "Booleano inválido; use o texto SIM ou NÃO.", linha, coluna)
        )
        return None
    normalizado = _token(valor)
    if normalizado == "SIM":
        return True
    if normalizado == "NAO":
        return False
    diagnosticos.append(
        _diagnostico("ERRO", aba, "Booleano inválido; use o texto SIM ou NÃO.", linha, coluna)
    )
    return None


def _data(valor, aba, linha, coluna, diagnosticos, obrigatorio=False):
    if _vazio(valor):
        if obrigatorio:
            diagnosticos.append(_diagnostico("ERRO", aba, "Data obrigatória ausente.", linha, coluna))
        return None
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    try:
        return date.fromisoformat(str(valor).strip()).isoformat()
    except ValueError:
        diagnosticos.append(
            _diagnostico("ERRO", aba, "Data inválida; use AAAA-MM-DD.", linha, coluna)
        )
        return None


def _validar_codigo(valor, aba, linha, coluna, diagnosticos):
    if _vazio(valor):
        diagnosticos.append(_diagnostico("ERRO", aba, "Código obrigatório ausente.", linha, coluna))
        return None
    if not isinstance(valor, str):
        diagnosticos.append(
            _diagnostico(
                "ERRO",
                aba,
                "Código deve ser informado como texto para preservar seu conteúdo.",
                linha,
                coluna,
            )
        )
        return None
    codigo = valor.strip().upper()
    if not PADRAO_CODIGO.fullmatch(codigo):
        diagnosticos.append(
            _diagnostico(
                "ERRO",
                aba,
                "Código inválido; use letra inicial, letras maiúsculas, números e sublinhado, com até 30 caracteres.",
                linha,
                coluna,
                codigo,
            )
        )
        return codigo
    return codigo


def _validar_acao(valor, aba, linha, diagnosticos):
    acao = _token(valor)
    if not acao:
        diagnosticos.append(_diagnostico("ERRO", aba, "Ação obrigatória ausente; nenhuma ação é inferida.", linha, "ACAO"))
        return None
    if acao not in ACOES:
        diagnosticos.append(
            _diagnostico("ERRO", aba, "Ação inválida; use CRIAR, ATUALIZAR ou DESATIVAR.", linha, "ACAO")
        )
    elif acao not in ACOES_POR_ABA[aba]:
        permitidas = ", ".join(sorted(ACOES_POR_ABA[aba]))
        diagnosticos.append(
            _diagnostico(
                "ERRO",
                aba,
                f"Ação {acao} não é suportada com segurança nesta aba; use {permitidas}.",
                linha,
                "ACAO",
            )
        )
    return acao


def _inspecionar_zip(conteudo: bytes, diagnosticos) -> bool:
    if len(conteudo) > MAX_ARQUIVO_BYTES:
        diagnosticos.append(_diagnostico("ERRO", None, "Arquivo excede o limite de 5 MiB."))
        return False
    arquivo = io.BytesIO(conteudo)
    if not zipfile.is_zipfile(arquivo):
        diagnosticos.append(_diagnostico("ERRO", None, "Conteúdo inválido ou arquivo XLSX corrompido."))
        return False
    try:
        with zipfile.ZipFile(arquivo) as pacote:
            entradas = pacote.infolist()
            nomes_entradas = [item.filename.replace("\\", "/") for item in entradas]
            if len(nomes_entradas) != len(set(nomes_entradas)):
                diagnosticos.append(_diagnostico("ERRO", None, "Arquivo XLSX possui entradas internas duplicadas."))
                return False
            if len(entradas) > MAX_ENTRADAS_ZIP:
                diagnosticos.append(_diagnostico("ERRO", None, "Arquivo XLSX possui entradas internas em excesso."))
                return False
            total = sum(item.file_size for item in entradas)
            if total > MAX_DESCOMPRIMIDO_BYTES:
                diagnosticos.append(_diagnostico("ERRO", None, "Conteúdo descomprimido excede o limite de 30 MiB."))
                return False
            for item in entradas:
                nome = item.filename.replace("\\", "/")
                if item.flag_bits & 1:
                    diagnosticos.append(_diagnostico("ERRO", None, "Arquivos XLSX criptografados não são aceitos."))
                    return False
                partes = nome.split("/")
                if nome.startswith("/") or ".." in partes or re.match(r"^[A-Za-z]:", nome):
                    diagnosticos.append(_diagnostico("ERRO", None, "Estrutura interna inválida no arquivo XLSX."))
                    return False
                if "vbaproject" in nome.lower():
                    diagnosticos.append(_diagnostico("ERRO", None, "Macros não são permitidas no template cadastral."))
                    return False
                if item.file_size and item.file_size / max(item.compress_size, 1) > MAX_RAZAO_COMPRESSAO:
                    diagnosticos.append(_diagnostico("ERRO", None, "Arquivo XLSX apresenta taxa de compressão insegura."))
                    return False
    except (OSError, zipfile.BadZipFile):
        diagnosticos.append(_diagnostico("ERRO", None, "Não foi possível inspecionar o arquivo XLSX."))
        return False
    return True


def _mapear_cabecalho(ws, aba, diagnosticos):
    valores = [celula.value for celula in ws[1]] if ws.max_row else []
    normalizados = [_token(valor) for valor in valores]
    while normalizados and not normalizados[-1]:
        normalizados.pop()
    repetidos = sorted({item for item in normalizados if item and normalizados.count(item) > 1})
    for item in repetidos:
        diagnosticos.append(_diagnostico("ERRO", aba, "Cabeçalho repetido.", 1, item))
    esperados = set(ABAS[aba])
    presentes = {item for item in normalizados if item}
    for item in sorted(esperados - presentes):
        diagnosticos.append(_diagnostico("ERRO", aba, "Cabeçalho obrigatório ausente.", 1, item))
    for item in sorted(presentes - esperados):
        diagnosticos.append(_diagnostico("ERRO", aba, "Cabeçalho desconhecido.", 1, item))
    if repetidos or esperados != presentes:
        return None
    return {nome: normalizados.index(nome) + 1 for nome in ABAS[aba]}


def _linhas(ws, mapa):
    for numero in range(2, ws.max_row + 1):
        valores = {coluna: ws.cell(numero, indice).value for coluna, indice in mapa.items()}
        if any(not _vazio(valor) for valor in valores.values()):
            yield numero, valores


def _exigir_texto(valor, aba, linha, coluna, diagnosticos, obrigatorio):
    texto = _texto(valor)
    if obrigatorio and texto is None:
        diagnosticos.append(_diagnostico("ERRO", aba, "Valor obrigatório ausente.", linha, coluna))
    return texto


def _parsear_catalogo(ws, aba, mapa, diagnosticos):
    dados, chaves = [], set()
    for linha, valores in _linhas(ws, mapa):
        acao = _validar_acao(valores["ACAO"], aba, linha, diagnosticos)
        codigo = _validar_codigo(valores["CODIGO"], aba, linha, "CODIGO", diagnosticos)
        if codigo in chaves:
            diagnosticos.append(_diagnostico("ERRO", aba, "Código duplicado nesta aba.", linha, "CODIGO", codigo))
        elif codigo:
            chaves.add(codigo)
        criar = acao == "CRIAR"
        nome = _exigir_texto(valores["NOME"], aba, linha, "NOME", diagnosticos, criar)
        item = {"linha": linha, "acao": acao, "codigo": codigo, "nome": nome}
        if aba == "MATERIAS_PRIMAS":
            item["ativa"] = _booleano(valores["ATIVA"], aba, linha, "ATIVA", diagnosticos)
            if acao == "ATUALIZAR" and nome is None and item["ativa"] is None:
                diagnosticos.append(_diagnostico("ERRO", aba, "ATUALIZAR exige ao menos um campo preenchido.", linha, "ACAO", codigo))
        else:
            item["unidade"] = _exigir_texto(valores["UNIDADE"], aba, linha, "UNIDADE", diagnosticos, criar)
            if acao == "ATUALIZAR" and nome is None and item["unidade"] is None:
                diagnosticos.append(_diagnostico("ERRO", aba, "ATUALIZAR exige ao menos um campo preenchido.", linha, "ACAO", codigo))
        dados.append(item)
    return dados


def _parsear_composicoes(ws, mapa, diagnosticos):
    aba, dados, chaves = "COMPOSICAO_NUTRICIONAL", [], set()
    for linha, valores in _linhas(ws, mapa):
        acao = _validar_acao(valores["ACAO"], aba, linha, diagnosticos)
        mp = _validar_codigo(valores["MATERIA_PRIMA_CODIGO"], aba, linha, "MATERIA_PRIMA_CODIGO", diagnosticos)
        nutriente = _validar_codigo(valores["NUTRIENTE_CODIGO"], aba, linha, "NUTRIENTE_CODIGO", diagnosticos)
        chave = (mp, nutriente)
        if None not in chave and chave in chaves:
            diagnosticos.append(_diagnostico("ERRO", aba, "Composição duplicada nesta aba.", linha, "NUTRIENTE_CODIGO", f"{mp}/{nutriente}"))
        else:
            chaves.add(chave)
        valor = _numero(valores["VALOR"], aba, linha, "VALOR", diagnosticos, acao in {"CRIAR", "ATUALIZAR"})
        dados.append({"linha": linha, "acao": acao, "materia_prima_codigo": mp, "nutriente_codigo": nutriente, "valor": valor})
    return dados


def _parsear_precos(ws, mapa, diagnosticos):
    aba, dados, chaves = "PRECOS_MP", [], set()
    for linha, valores in _linhas(ws, mapa):
        acao = _validar_acao(valores["ACAO"], aba, linha, diagnosticos)
        mp = _validar_codigo(valores["MATERIA_PRIMA_CODIGO"], aba, linha, "MATERIA_PRIMA_CODIGO", diagnosticos)
        preco = _numero(valores["PRECO_KG"], aba, linha, "PRECO_KG", diagnosticos)
        inicio = _data(valores["VIGENCIA_INICIO"], aba, linha, "VIGENCIA_INICIO", diagnosticos, True)
        fim = _data(valores["VIGENCIA_FIM"], aba, linha, "VIGENCIA_FIM", diagnosticos)
        chave = (mp, inicio)
        if None not in chave and chave in chaves:
            diagnosticos.append(_diagnostico("ERRO", aba, "Preço duplicado para a MP e vigência inicial.", linha, "VIGENCIA_INICIO", mp))
        else:
            chaves.add(chave)
        if inicio and fim and fim < inicio:
            diagnosticos.append(_diagnostico("ERRO", aba, "Vigência final anterior à inicial.", linha, "VIGENCIA_FIM", mp))
        dados.append({"linha": linha, "acao": acao, "materia_prima_codigo": mp, "preco_kg": preco, "vigencia_inicio": inicio, "vigencia_fim": fim})
    return dados


def _validar_referencias(dados, diagnosticos):
    mps = {item["codigo"]: item for item in dados["MATERIAS_PRIMAS"] if item["codigo"]}
    nutrientes = {item["codigo"]: item for item in dados["NUTRIENTES"] if item["codigo"]}
    for aba in ("COMPOSICAO_NUTRICIONAL", "PRECOS_MP"):
        for item in dados[aba]:
            indice = item["linha"]
            codigo = item["materia_prima_codigo"]
            if codigo and codigo not in mps:
                diagnosticos.append(_diagnostico("AVISO", aba, "Referência de matéria-prima não declarada no arquivo; deverá existir no banco na pré-validação.", indice, "MATERIA_PRIMA_CODIGO", codigo))
            elif codigo and mps[codigo]["acao"] == "DESATIVAR":
                diagnosticos.append(_diagnostico("ERRO", aba, "Referência aponta para matéria-prima desativada no mesmo lote.", indice, "MATERIA_PRIMA_CODIGO", codigo))
    for item in dados["COMPOSICAO_NUTRICIONAL"]:
        indice = item["linha"]
        codigo = item["nutriente_codigo"]
        if codigo and codigo not in nutrientes:
            diagnosticos.append(_diagnostico("AVISO", "COMPOSICAO_NUTRICIONAL", "Referência de nutriente não declarada no arquivo; deverá existir no banco na pré-validação.", indice, "NUTRIENTE_CODIGO", codigo))
        elif codigo and nutrientes[codigo]["acao"] == "DESATIVAR":
            diagnosticos.append(_diagnostico("ERRO", "COMPOSICAO_NUTRICIONAL", "Referência aponta para nutriente desativado no mesmo lote.", indice, "NUTRIENTE_CODIGO", codigo))


def parsear_planilha_cadastral(conteudo: bytes, nome_arquivo: str) -> dict:
    diagnosticos = []
    dados = {aba: [] for aba in ABAS if aba != "LEIA_ME"}
    if not nome_arquivo.lower().endswith(".xlsx"):
        diagnosticos.append(_diagnostico("ERRO", None, "Formato não suportado; use somente .xlsx."))
        return {"versao": None, "valido": False, "dados": dados, "diagnosticos": diagnosticos}
    if not conteudo:
        diagnosticos.append(_diagnostico("ERRO", None, "Arquivo vazio."))
        return {"versao": None, "valido": False, "dados": dados, "diagnosticos": diagnosticos}
    if not _inspecionar_zip(conteudo, diagnosticos):
        return {"versao": None, "valido": False, "dados": dados, "diagnosticos": diagnosticos}
    try:
        workbook = load_workbook(
            io.BytesIO(conteudo),
            read_only=True,
            data_only=False,
            keep_links=False,
        )
    except Exception:
        diagnosticos.append(_diagnostico("ERRO", None, "Não foi possível abrir o conteúdo XLSX."))
        return {"versao": None, "valido": False, "dados": dados, "diagnosticos": diagnosticos}

    nomes = workbook.sheetnames
    if len(nomes) > MAX_ABAS:
        diagnosticos.append(_diagnostico("ERRO", None, "Quantidade de abas excede o limite de 5."))
    for aba in sorted(set(ABAS) - set(nomes)):
        diagnosticos.append(_diagnostico("ERRO", aba, "Aba obrigatória ausente."))
    for aba in sorted(set(nomes) - set(ABAS)):
        diagnosticos.append(_diagnostico("ERRO", aba, "Aba desconhecida."))

    total_celulas = 0
    mapas = {}
    for aba in nomes:
        ws = workbook[aba]
        total_celulas += ws.max_row * ws.max_column
        if total_celulas > MAX_CELULAS_TOTAL:
            diagnosticos.append(_diagnostico("ERRO", None, "Workbook excede o limite de 100.000 células."))
            continue
        if ws.max_row > MAX_LINHAS_POR_ABA:
            diagnosticos.append(_diagnostico("ERRO", aba, "Aba excede o limite de 5.000 linhas."))
            continue
        if ws.max_column > MAX_COLUNAS_POR_ABA:
            diagnosticos.append(_diagnostico("ERRO", aba, "Aba excede o limite de 12 colunas."))
            continue
        for row in ws.iter_rows():
            for cell in row:
                if cell.data_type == "f":
                    diagnosticos.append(_diagnostico("ERRO", aba, "Fórmulas não são permitidas.", cell.row, cell.column_letter))
        if aba in ABAS:
            mapas[aba] = _mapear_cabecalho(ws, aba, diagnosticos)
    versao = None
    if "LEIA_ME" in mapas and mapas["LEIA_ME"]:
        chaves = {}
        for linha, valores in _linhas(workbook["LEIA_ME"], mapas["LEIA_ME"]):
            chave = _token(valores["CHAVE"])
            if not chave:
                diagnosticos.append(_diagnostico("ERRO", "LEIA_ME", "Chave obrigatória ausente.", linha, "CHAVE"))
                continue
            if chave in chaves:
                diagnosticos.append(_diagnostico("ERRO", "LEIA_ME", "Chave duplicada.", linha, "CHAVE", chave))
            chaves[chave] = _texto(valores["VALOR"])
        versao = chaves.get("VERSAO_TEMPLATE")
        if versao != VERSAO_CONTRATO:
            diagnosticos.append(_diagnostico("ERRO", "LEIA_ME", "Versão do template ausente ou incompatível; esperado 1.0.", None, "VALOR", "VERSAO_TEMPLATE"))

    if mapas.get("MATERIAS_PRIMAS"):
        dados["MATERIAS_PRIMAS"] = _parsear_catalogo(workbook["MATERIAS_PRIMAS"], "MATERIAS_PRIMAS", mapas["MATERIAS_PRIMAS"], diagnosticos)
    if mapas.get("NUTRIENTES"):
        dados["NUTRIENTES"] = _parsear_catalogo(workbook["NUTRIENTES"], "NUTRIENTES", mapas["NUTRIENTES"], diagnosticos)
    if mapas.get("COMPOSICAO_NUTRICIONAL"):
        dados["COMPOSICAO_NUTRICIONAL"] = _parsear_composicoes(workbook["COMPOSICAO_NUTRICIONAL"], mapas["COMPOSICAO_NUTRICIONAL"], diagnosticos)
    if mapas.get("PRECOS_MP"):
        dados["PRECOS_MP"] = _parsear_precos(workbook["PRECOS_MP"], mapas["PRECOS_MP"], diagnosticos)
    _validar_referencias(dados, diagnosticos)
    valido = not any(item["severidade"] == "ERRO" for item in diagnosticos)
    return {"versao": versao, "valido": valido, "dados": dados, "diagnosticos": diagnosticos}


def gerar_template_cadastral() -> bytes:
    workbook = Workbook()
    workbook.remove(workbook.active)
    exemplos = {
        "LEIA_ME": [
            ("VERSAO_TEMPLATE", VERSAO_CONTRATO),
            ("ESCOPO", "Dados exclusivamente fictícios para demonstrar o contrato cadastral."),
            ("ACOES", "CRIAR, ATUALIZAR ou DESATIVAR; nenhuma ação é inferida."),
            ("IDENTIFICACAO", "Use somente códigos estáveis; códigos não podem ser alterados."),
        ],
        "MATERIAS_PRIMAS": [("CRIAR", "FICT_MP_AVEIA", "Aveia fictícia", "SIM")],
        "NUTRIENTES": [("CRIAR", "FICT_NUT_PROTEINA", "Proteína fictícia", "g/100 g")],
        "COMPOSICAO_NUTRICIONAL": [("CRIAR", "FICT_MP_AVEIA", "FICT_NUT_PROTEINA", 12.5)],
        "PRECOS_MP": [("CRIAR", "FICT_MP_AVEIA", 10.25, date(2026, 1, 1), None)],
    }
    for aba, colunas in ABAS.items():
        ws = workbook.create_sheet(aba)
        ws.append(colunas)
        for linha in exemplos[aba]:
            ws.append(linha)
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="1F4E78")
        ws.freeze_panes = "A2"
        for coluna in ws.columns:
            largura = min(max(len(str(cell.value or "")) for cell in coluna) + 2, 60)
            ws.column_dimensions[coluna[0].column_letter].width = largura
    saida = io.BytesIO()
    workbook.save(saida)
    return saida.getvalue()


# Dispatcher versionado do contrato cadastral (v1.0/v1.1).
_parsear_planilha_v1_0 = parsear_planilha_cadastral
_gerar_template_v1_0 = gerar_template_cadastral


def _mapear_cabecalho_versionado(ws, aba, colunas, diagnosticos):
    valores = [celula.value for celula in ws[1]] if ws.max_row else []
    normalizados = [_token(valor) for valor in valores]
    while normalizados and not normalizados[-1]:
        normalizados.pop()
    repetidos = sorted({item for item in normalizados if item and normalizados.count(item) > 1})
    for item in repetidos:
        diagnosticos.append(_diagnostico("ERRO", aba, "Cabeçalho repetido.", 1, item))
    esperados, presentes = set(colunas), {item for item in normalizados if item}
    for item in sorted(esperados - presentes):
        diagnosticos.append(_diagnostico("ERRO", aba, "Cabeçalho obrigatório ausente.", 1, item))
    for item in sorted(presentes - esperados):
        diagnosticos.append(_diagnostico("ERRO", aba, "Cabeçalho desconhecido.", 1, item))
    if repetidos or esperados != presentes:
        return None
    return {nome: normalizados.index(nome) + 1 for nome in colunas}


def _inspecionar_seguranca_adicional(conteudo, diagnosticos):
    try:
        with zipfile.ZipFile(io.BytesIO(conteudo)) as pacote:
            nomes = [item.filename.replace("\\", "/") for item in pacote.infolist()]
            if any(nome.lower().startswith("xl/externallinks/") for nome in nomes):
                diagnosticos.append(_diagnostico("ERRO", None, "Links externos não são permitidos no template cadastral."))
                return False
            for nome in nomes:
                if not nome.lower().endswith(".rels"):
                    continue
                try:
                    relacionamentos = ElementTree.fromstring(pacote.read(nome))
                except ElementTree.ParseError:
                    diagnosticos.append(_diagnostico("ERRO", None, "Relacionamento XLSX inválido."))
                    return False
                for relacao in relacionamentos.iter():
                    atributos = {chave.rsplit("}", 1)[-1].lower(): valor for chave, valor in relacao.attrib.items()}
                    if atributos.get("targetmode", "").lower() == "external":
                        diagnosticos.append(_diagnostico("ERRO", None, "Links externos não são permitidos no template cadastral."))
                        return False
            try:
                raiz = ElementTree.fromstring(pacote.read("xl/workbook.xml"))
            except (KeyError, ElementTree.ParseError):
                diagnosticos.append(_diagnostico("ERRO", None, "Estrutura do workbook XLSX inválida."))
                return False
            abas = [item.attrib.get("name", "") for item in raiz.iter() if item.tag.endswith("}sheet")]
            if len(abas) != len(set(abas)):
                diagnosticos.append(_diagnostico("ERRO", None, "Nomes de abas duplicados não são permitidos."))
                return False
            if any(not nome or len(nome) > 31 or re.search(r"[\x00-\x1f\[\]:*?/\\]", nome) for nome in abas):
                diagnosticos.append(_diagnostico("ERRO", None, "Nome de aba estruturalmente inválido."))
                return False
    except (OSError, zipfile.BadZipFile, RuntimeError):
        diagnosticos.append(_diagnostico("ERRO", None, "Não foi possível inspecionar o arquivo XLSX."))
        return False
    return True


def _inspecionar_workbook_versionado(workbook, diagnosticos):
    nomes = workbook.sheetnames
    if len(nomes) > MAX_ABAS_SUPORTADO:
        diagnosticos.append(_diagnostico("ERRO", None, f"Workbook excede o limite absoluto de {MAX_ABAS_SUPORTADO} abas."))
    total = 0
    for aba in nomes:
        ws = workbook[aba]
        if ws.sheet_state != "visible":
            diagnosticos.append(_diagnostico("ERRO", aba, "Abas ocultas ou muito ocultas não são permitidas."))
        total += ws.max_row * ws.max_column
        if ws.max_row > MAX_LINHAS_POR_ABA:
            diagnosticos.append(_diagnostico("ERRO", aba, "Aba excede o limite de 5.000 linhas."))
        if ws.max_column > MAX_COLUNAS_POR_ABA:
            diagnosticos.append(_diagnostico("ERRO", aba, "Aba excede o limite de 12 colunas."))
        for row in ws.iter_rows():
            for cell in row:
                if cell.data_type == "f":
                    diagnosticos.append(_diagnostico("ERRO", aba, "Fórmulas não são permitidas.", cell.row, cell.column_letter))
    if total > MAX_CELULAS_TOTAL:
        diagnosticos.append(_diagnostico("ERRO", None, "Workbook excede o limite de 100.000 células."))


def _versao_declarada(workbook, diagnosticos):
    if "LEIA_ME" not in workbook.sheetnames:
        diagnosticos.append(_diagnostico("ERRO", "LEIA_ME", "Aba obrigatória ausente."))
        return None
    mapa = _mapear_cabecalho_versionado(workbook["LEIA_ME"], "LEIA_ME", ABAS_V1_0["LEIA_ME"], diagnosticos)
    if not mapa:
        return None
    chaves = {}
    for linha, valores in _linhas(workbook["LEIA_ME"], mapa):
        chave = _token(valores["CHAVE"])
        if not chave:
            diagnosticos.append(_diagnostico("ERRO", "LEIA_ME", "Chave obrigatória ausente.", linha, "CHAVE"))
            continue
        if chave in chaves:
            diagnosticos.append(_diagnostico("ERRO", "LEIA_ME", "Chave duplicada.", linha, "CHAVE", chave))
        valor = valores["VALOR"]
        if chave == "VERSAO_TEMPLATE" and (not isinstance(valor, str) or workbook["LEIA_ME"].cell(linha, mapa["VALOR"]).data_type == "f"):
            diagnosticos.append(_diagnostico("ERRO", "LEIA_ME", "VERSAO_TEMPLATE deve ser texto literal.", linha, "VALOR", chave))
            chaves[chave] = None
        else:
            chaves[chave] = _texto(valor)
    versao = chaves.get("VERSAO_TEMPLATE")
    if versao is None:
        diagnosticos.append(_diagnostico("ERRO", "LEIA_ME", "VERSAO_TEMPLATE obrigatória ausente.", None, "VALOR", "VERSAO_TEMPLATE"))
    elif versao not in VERSOES_SUPORTADAS:
        diagnosticos.append(_diagnostico("ERRO", "LEIA_ME", "Versão do template desconhecida; versões aceitas: 1.0 e 1.1.", None, "VALOR", "VERSAO_TEMPLATE"))
    return versao


def _codigo_regulatorio(valor, aba, linha, coluna, diagnosticos):
    if _vazio(valor):
        diagnosticos.append(_diagnostico("ERRO", aba, "Código obrigatório ausente.", linha, coluna))
        return None
    if not isinstance(valor, str):
        diagnosticos.append(_diagnostico("ERRO", aba, "Código deve ser informado como texto para preservar seu conteúdo.", linha, coluna))
        return None
    codigo = valor.strip().upper()
    if not PADRAO_CODIGO_REGULATORIO.fullmatch(codigo):
        diagnosticos.append(_diagnostico("ERRO", aba, "Código regulatório inválido; use letra inicial, maiúsculas, números e sublinhado, com até 50 caracteres.", linha, coluna, codigo))
    return codigo


def _data_regulatoria(valor, aba, linha, coluna, diagnosticos, obrigatoria=False):
    if _vazio(valor):
        if obrigatoria:
            diagnosticos.append(_diagnostico("ERRO", aba, "Data obrigatória ausente.", linha, coluna))
        return None
    if not isinstance(valor, str) or not PADRAO_DATA_ISO.fullmatch(valor.strip()):
        diagnosticos.append(_diagnostico("ERRO", aba, "Data inválida; use texto no formato AAAA-MM-DD.", linha, coluna))
        return None
    try:
        return date.fromisoformat(valor.strip()).isoformat()
    except ValueError:
        diagnosticos.append(_diagnostico("ERRO", aba, "Data inválida; use AAAA-MM-DD.", linha, coluna))
        return None


def _percentual(valor, aba, linha, coluna, diagnosticos):
    numero = _numero(valor, aba, linha, coluna, diagnosticos, False)
    if numero is not None and Decimal(numero) > 100:
        diagnosticos.append(_diagnostico("ERRO", aba, "Percentual deve estar entre 0 e 100.", linha, coluna))
    return numero


def _catalogo_regulatorio(ws, aba, mapa, diagnosticos):
    dados, chaves = [], set()
    for linha, valores in _linhas(ws, mapa):
        acao = _validar_acao(valores["ACAO"], aba, linha, diagnosticos)
        codigo = _codigo_regulatorio(valores["CODIGO"], aba, linha, "CODIGO", diagnosticos)
        if codigo in chaves:
            diagnosticos.append(_diagnostico("ERRO", aba, "Código duplicado nesta aba.", linha, "CODIGO", codigo))
        elif codigo:
            chaves.add(codigo)
        nome, descricao = _texto(valores["NOME"]), _texto(valores["DESCRICAO"])
        if acao == "CRIAR" and nome is None:
            diagnosticos.append(_diagnostico("ERRO", aba, "Valor obrigatório ausente.", linha, "NOME"))
        if acao == "DESATIVAR" and (nome is not None or descricao is not None):
            diagnosticos.append(_diagnostico("ERRO", aba, "DESATIVAR aceita somente a chave natural.", linha, "ACAO", codigo))
        dados.append({"linha": linha, "acao": acao, "codigo": codigo, "nome": nome, "descricao": descricao})
    return dados


def _composicao_regulatoria(ws, mapa, diagnosticos):
    aba, dados, chaves = "COMPOSICAO_COMPONENTES_MP", [], set()
    for linha, valores in _linhas(ws, mapa):
        acao = _validar_acao(valores["ACAO"], aba, linha, diagnosticos)
        mp = _validar_codigo(valores["MATERIA_PRIMA_CODIGO"], aba, linha, "MATERIA_PRIMA_CODIGO", diagnosticos)
        componente = _codigo_regulatorio(valores["COMPONENTE_CODIGO"], aba, linha, "COMPONENTE_CODIGO", diagnosticos)
        referencia = _data_regulatoria(valores["DATA_REFERENCIA"], aba, linha, "DATA_REFERENCIA", diagnosticos, True)
        chave = (mp, componente, referencia)
        if None not in chave and chave in chaves:
            diagnosticos.append(_diagnostico("ERRO", aba, "Composição regulatória duplicada nesta aba.", linha, "DATA_REFERENCIA", f"{mp}/{componente}"))
        else:
            chaves.add(chave)
        situacao = _token(valores["SITUACAO"]) if not _vazio(valores["SITUACAO"]) else None
        concentracao = _percentual(valores["CONCENTRACAO"], aba, linha, "CONCENTRACAO", diagnosticos)
        fonte, observacao = _texto(valores["FONTE"]), _texto(valores["OBSERVACAO"])
        if acao == "CRIAR":
            if situacao not in SITUACOES_COMPONENTE:
                diagnosticos.append(_diagnostico("ERRO", aba, "Situação inválida; use INFORMADO, AUSENTE_CONFIRMADO ou DESCONHECIDO.", linha, "SITUACAO"))
            elif situacao == "INFORMADO" and concentracao is None:
                diagnosticos.append(_diagnostico("ERRO", aba, "INFORMADO exige concentração entre 0 e 100.", linha, "CONCENTRACAO"))
            elif situacao == "AUSENTE_CONFIRMADO" and concentracao != "0":
                diagnosticos.append(_diagnostico("ERRO", aba, "AUSENTE_CONFIRMADO exige concentração exatamente zero.", linha, "CONCENTRACAO"))
            elif situacao == "DESCONHECIDO" and concentracao is not None:
                diagnosticos.append(_diagnostico("ERRO", aba, "DESCONHECIDO exige concentração vazia.", linha, "CONCENTRACAO"))
        elif acao == "DESATIVAR" and any((situacao, concentracao, fonte, observacao)):
            diagnosticos.append(_diagnostico("ERRO", aba, "DESATIVAR aceita somente a chave natural.", linha, "ACAO"))
        dados.append({"linha": linha, "acao": acao, "materia_prima_codigo": mp, "componente_codigo": componente,
                      "data_referencia": referencia, "situacao": situacao, "concentracao": concentracao,
                      "fonte": fonte, "observacao": observacao})
    return dados


def _regras_regulatorias(ws, aba, mapa, diagnosticos):
    dados, chaves = [], set()
    mp_alvo = aba == "REGRAS_REGULATORIAS_MP"
    alvo_coluna = "MATERIA_PRIMA_CODIGO" if mp_alvo else "COMPONENTE_CODIGO"
    for linha, valores in _linhas(ws, mapa):
        acao = _validar_acao(valores["ACAO"], aba, linha, diagnosticos)
        categoria = _codigo_regulatorio(valores["CATEGORIA_CODIGO"], aba, linha, "CATEGORIA_CODIGO", diagnosticos)
        alvo = (_validar_codigo if mp_alvo else _codigo_regulatorio)(valores[alvo_coluna], aba, linha, alvo_coluna, diagnosticos)
        inicio = _data_regulatoria(valores["VIGENCIA_INICIO"], aba, linha, "VIGENCIA_INICIO", diagnosticos)
        fim = _data_regulatoria(valores["VIGENCIA_FIM"], aba, linha, "VIGENCIA_FIM", diagnosticos)
        chave = (categoria, alvo, inicio, fim)
        if None not in chave[:2] and chave in chaves:
            diagnosticos.append(_diagnostico("ERRO", aba, "Regra duplicada nesta aba para a mesma chave natural.", linha, alvo_coluna, f"{categoria}/{alvo}"))
        else:
            chaves.add(chave)
        tratamento = _token(valores["TRATAMENTO"]) if not _vazio(valores["TRATAMENTO"]) else None
        minimo, maximo = (_percentual(valores[c], aba, linha, c, diagnosticos) for c in ("MINIMO", "MAXIMO"))
        justificativa, referencia = _texto(valores["JUSTIFICATIVA"]), _texto(valores["REFERENCIA_NORMATIVA"])
        if inicio and fim and fim < inicio:
            diagnosticos.append(_diagnostico("ERRO", aba, "Vigência final anterior à inicial.", linha, "VIGENCIA_FIM"))
        if acao in {"CRIAR", "ATUALIZAR"}:
            if tratamento not in TRATAMENTOS:
                diagnosticos.append(_diagnostico("ERRO", aba, "Tratamento inválido; use PERMITIDA, PROIBIDA, OBRIGATORIA ou LIMITADA.", linha, "TRATAMENTO"))
            if justificativa is None:
                diagnosticos.append(_diagnostico("ERRO", aba, "Justificativa obrigatória ausente.", linha, "JUSTIFICATIVA"))
            if minimo is not None and maximo is not None and Decimal(minimo) > Decimal(maximo):
                diagnosticos.append(_diagnostico("ERRO", aba, "O mínimo não pode superar o máximo.", linha, "MINIMO"))
            if tratamento == "LIMITADA" and minimo is None and maximo is None:
                diagnosticos.append(_diagnostico("ERRO", aba, "LIMITADA exige mínimo ou máximo.", linha, "TRATAMENTO"))
            if tratamento == "OBRIGATORIA" and (minimo is None or Decimal(minimo) <= 0):
                diagnosticos.append(_diagnostico("ERRO", aba, "OBRIGATORIA exige mínimo maior que zero.", linha, "MINIMO"))
            if tratamento == "PROIBIDA":
                if minimo not in (None, "0") or maximo not in (None, "0"):
                    diagnosticos.append(_diagnostico("ERRO", aba, "PROIBIDA exige mínimo vazio ou zero e máximo zero.", linha, "TRATAMENTO"))
                if maximo is None:
                    maximo = "0"
        elif acao == "DESATIVAR" and any((tratamento, minimo, maximo, justificativa, referencia)):
            diagnosticos.append(_diagnostico("ERRO", aba, "DESATIVAR aceita somente a chave natural.", linha, "ACAO"))
        item = {"linha": linha, "acao": acao, "categoria_codigo": categoria,
                "tipo_alvo": "MATERIA_PRIMA" if mp_alvo else "COMPONENTE",
                "materia_prima_codigo": alvo if mp_alvo else None,
                "componente_codigo": None if mp_alvo else alvo,
                "tratamento": tratamento, "minimo": minimo, "maximo": maximo,
                "justificativa": justificativa, "referencia_normativa": referencia,
                "vigencia_inicio": inicio, "vigencia_fim": fim}
        if acao in {"CRIAR", "ATUALIZAR"}:
            item["unidade"] = "%"
            item["base"] = "MASSA_MASSA"
        dados.append(item)
    return dados


def parsear_planilha_cadastral(conteudo: bytes, nome_arquivo: str) -> dict:
    if not nome_arquivo.lower().endswith(".xlsx") or not conteudo:
        return _parsear_planilha_v1_0(conteudo, nome_arquivo)
    diagnosticos = []
    if not _inspecionar_zip(conteudo, diagnosticos) or not _inspecionar_seguranca_adicional(conteudo, diagnosticos):
        return {"versao": None, "valido": False, "dados": {a: [] for a in ABAS_V1_0 if a != "LEIA_ME"}, "diagnosticos": diagnosticos}
    try:
        workbook = load_workbook(io.BytesIO(conteudo), read_only=True, data_only=False, keep_links=False)
    except Exception:
        diagnosticos.append(_diagnostico("ERRO", None, "Não foi possível abrir o conteúdo XLSX."))
        return {"versao": None, "valido": False, "dados": {}, "diagnosticos": diagnosticos}
    _inspecionar_workbook_versionado(workbook, diagnosticos)
    versao = _versao_declarada(workbook, diagnosticos)
    if versao == "1.0":
        resultado = _parsear_planilha_v1_0(conteudo, nome_arquivo)
        resultado["diagnosticos"] = diagnosticos + [d for d in resultado["diagnosticos"] if d not in diagnosticos]
        resultado["valido"] = not any(d["severidade"] == "ERRO" for d in resultado["diagnosticos"])
        return resultado
    schema = ABAS_POR_VERSAO.get(versao)
    if schema is None:
        return {"versao": versao, "valido": False, "dados": {}, "diagnosticos": diagnosticos}
    nomes = workbook.sheetnames
    if len(nomes) != MAX_ABAS_POR_VERSAO[versao]:
        diagnosticos.append(_diagnostico("ERRO", None, f"Contrato {versao} exige exatamente {MAX_ABAS_POR_VERSAO[versao]} abas."))
    for aba in sorted(set(schema) - set(nomes)):
        diagnosticos.append(_diagnostico("ERRO", aba, "Aba obrigatória ausente."))
    for aba in sorted(set(nomes) - set(schema)):
        diagnosticos.append(_diagnostico("ERRO", aba, f"Aba desconhecida ou incompatível com o contrato {versao}."))
    if set(nomes) == set(schema) and nomes != list(schema):
        diagnosticos.append(_diagnostico("ERRO", None, f"Ordem das abas incompatível com o contrato {versao}."))
    mapas = {}
    for aba in nomes:
        if aba in schema and aba != "LEIA_ME":
            mapas[aba] = _mapear_cabecalho_versionado(workbook[aba], aba, schema[aba], diagnosticos)
    dados = {aba: [] for aba in schema if aba != "LEIA_ME"}
    for aba in ("MATERIAS_PRIMAS", "NUTRIENTES"):
        if mapas.get(aba): dados[aba] = _parsear_catalogo(workbook[aba], aba, mapas[aba], diagnosticos)
    if mapas.get("COMPOSICAO_NUTRICIONAL"): dados["COMPOSICAO_NUTRICIONAL"] = _parsear_composicoes(workbook["COMPOSICAO_NUTRICIONAL"], mapas["COMPOSICAO_NUTRICIONAL"], diagnosticos)
    if mapas.get("PRECOS_MP"): dados["PRECOS_MP"] = _parsear_precos(workbook["PRECOS_MP"], mapas["PRECOS_MP"], diagnosticos)
    for aba in ("CATEGORIAS_PRODUTO", "COMPONENTES_REGULATORIOS"):
        if mapas.get(aba): dados[aba] = _catalogo_regulatorio(workbook[aba], aba, mapas[aba], diagnosticos)
    if mapas.get("COMPOSICAO_COMPONENTES_MP"): dados["COMPOSICAO_COMPONENTES_MP"] = _composicao_regulatoria(workbook["COMPOSICAO_COMPONENTES_MP"], mapas["COMPOSICAO_COMPONENTES_MP"], diagnosticos)
    for aba in ("REGRAS_REGULATORIAS_MP", "REGRAS_REGULATORIAS_COMPONENTE"):
        if mapas.get(aba): dados[aba] = _regras_regulatorias(workbook[aba], aba, mapas[aba], diagnosticos)
    _validar_referencias(dados, diagnosticos)
    return {"versao": versao, "valido": not any(d["severidade"] == "ERRO" for d in diagnosticos), "dados": dados, "diagnosticos": diagnosticos}


def gerar_template_cadastral(versao=VERSAO_TEMPLATE_PADRAO) -> bytes:
    if versao == "1.0":
        return _gerar_template_v1_0()
    if versao != "1.1":
        raise ValueError("Versão de template não suportada.")
    workbook = Workbook()
    workbook.remove(workbook.active)
    exemplos = {
        "LEIA_ME": [("VERSAO_TEMPLATE", "1.1"),
            ("ESCOPO", "Dados fictícios; este contrato estrutural não aplica cadastros."),
            ("ACOES", "CRIAR, ATUALIZAR ou DESATIVAR; SEM_ALTERACAO é resultado calculado."),
            ("DATAS", "Use texto ISO AAAA-MM-DD nas abas regulatórias; vazio significa extremo aberto."),
            ("DECIMAIS", "Use decimal exato; vazio não é zero e não há conversão por float."),
            ("CONCENTRACAO", "DESCONHECIDO exige vazio; AUSENTE_CONFIRMADO exige zero explícito."),
            ("SEGURANCA", "Máximo 5 MiB, 5.000 linhas/aba, 12 colunas e 100.000 células; sem fórmulas, macros ou links externos.")],
        "MATERIAS_PRIMAS": [("CRIAR", "FICT_MP_AVEIA", "Aveia fictícia", "SIM")],
        "NUTRIENTES": [("CRIAR", "FICT_NUT_PROTEINA", "Proteína fictícia", "g/100 g")],
        "COMPOSICAO_NUTRICIONAL": [("CRIAR", "FICT_MP_AVEIA", "FICT_NUT_PROTEINA", "12.500000")],
        "PRECOS_MP": [("CRIAR", "FICT_MP_AVEIA", "10.250000", "2026-01-01", None)],
        "CATEGORIAS_PRODUTO": [("CRIAR", "FICT_CATEGORIA", "Categoria fictícia", "Sem alegação normativa")],
        "COMPONENTES_REGULATORIOS": [("CRIAR", "FICT_COMPONENTE", "Componente fictício", "Exemplo agregado")],
        "COMPOSICAO_COMPONENTES_MP": [("CRIAR", "FICT_MP_AVEIA", "FICT_COMPONENTE", "2026-01-01", "INFORMADO", "12.500000", "Ficha fictícia", None)],
        "REGRAS_REGULATORIAS_MP": [("CRIAR", "FICT_CATEGORIA", "FICT_MP_AVEIA", "LIMITADA", None, "40.000000", "Exemplo fictício", None, None, None)],
        "REGRAS_REGULATORIAS_COMPONENTE": [("CRIAR", "FICT_CATEGORIA", "FICT_COMPONENTE", "PROIBIDA", None, None, "Exemplo fictício", None, "2026-01-01", None)],
    }
    for aba, colunas in ABAS_V1_1.items():
        ws = workbook.create_sheet(aba)
        ws.append(colunas)
        for linha in exemplos[aba]: ws.append(linha)
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="1F4E78")
        ws.freeze_panes = "A2"
        for coluna in ws.columns:
            ws.column_dimensions[coluna[0].column_letter].width = min(max(len(str(c.value or "")) for c in coluna) + 2, 60)
    saida = io.BytesIO()
    workbook.save(saida)
    return saida.getvalue()
