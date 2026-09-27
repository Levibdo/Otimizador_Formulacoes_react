from datetime import date
from decimal import Decimal

from sqlalchemy import or_, select

from models import MateriaPrima
from models.regulatorio import (
    CategoriaProduto,
    ComponenteRegulatorio,
    ComposicaoComponenteMP,
    RegraRegulatoria,
)


ORDEM_REGULATORIA = (
    "CATEGORIAS_PRODUTO",
    "COMPONENTES_REGULATORIOS",
    "COMPOSICAO_COMPONENTES_MP",
    "REGRAS_REGULATORIAS_MP",
    "REGRAS_REGULATORIAS_COMPONENTE",
)


def _diag(lista, erros, codigo, aba, linha, mensagem, coluna=None, severidade="ERRO"):
    lista.append({
        "severidade": severidade, "aba": aba, "linha": linha, "coluna": coluna,
        "codigo": codigo, "mensagem": mensagem,
    })
    if severidade == "ERRO" and linha is not None:
        erros.add((aba, linha))


def _op(aba, item, resultado, campos=()):
    return {
        "aba": aba, "linha": item["linha"], "codigo": _codigo_operacao(aba, item),
        "acao": item["acao"], "resultado": resultado, "campos_alterados": list(campos),
    }


def _codigo_operacao(aba, item):
    if aba in {"CATEGORIAS_PRODUTO", "COMPONENTES_REGULATORIOS"}:
        return item["codigo"]
    if aba == "COMPOSICAO_COMPONENTES_MP":
        return f'{item["materia_prima_codigo"]}/{item["componente_codigo"]}/{item["data_referencia"]}'
    alvo = item["materia_prima_codigo"] or item["componente_codigo"]
    return f'{item["categoria_codigo"]}/{alvo}/{item["vigencia_inicio"] or ""}/{item["vigencia_fim"] or ""}'


def _data(valor):
    return date.fromisoformat(valor) if valor else None


def _decimal(valor):
    return Decimal(valor) if valor is not None else None


def _decimal_compativel_bd(valor):
    if valor is None or not valor.is_finite():
        return valor is None
    _, digitos, expoente = valor.as_tuple()
    casas = max(-expoente, 0)
    inteiros = max(len(digitos) + expoente, 0)
    return casas <= 6 and inteiros <= 12


def _sobrepoe(a_inicio, a_fim, b_inicio, b_fim):
    return (a_inicio or date.min) <= (b_fim or date.max) and (b_inicio or date.min) <= (a_fim or date.max)


def _consultar(db, dados):
    codigos_mp = {
        item.get("codigo") for item in dados["MATERIAS_PRIMAS"]
    } | {
        item.get("materia_prima_codigo")
        for aba in ("COMPOSICAO_COMPONENTES_MP", "REGRAS_REGULATORIAS_MP")
        for item in dados[aba]
    }
    codigos_categoria = {
        item.get("codigo") for item in dados["CATEGORIAS_PRODUTO"]
    } | {
        item.get("categoria_codigo")
        for aba in ("REGRAS_REGULATORIAS_MP", "REGRAS_REGULATORIAS_COMPONENTE")
        for item in dados[aba]
    }
    codigos_componente = {
        item.get("codigo") for item in dados["COMPONENTES_REGULATORIOS"]
    } | {
        item.get("componente_codigo")
        for aba in ("COMPOSICAO_COMPONENTES_MP", "REGRAS_REGULATORIAS_COMPONENTE")
        for item in dados[aba]
    }
    codigos_mp.discard(None); codigos_categoria.discard(None); codigos_componente.discard(None)
    with db.no_autoflush:
        mps = list(db.scalars(select(MateriaPrima).where(
            MateriaPrima.codigo.in_(codigos_mp)
        ).order_by(MateriaPrima.codigo, MateriaPrima.id)).all()) if codigos_mp else []
        categorias = list(db.scalars(select(CategoriaProduto).where(
            CategoriaProduto.codigo.in_(codigos_categoria)
        ).order_by(CategoriaProduto.codigo, CategoriaProduto.id)).all()) if codigos_categoria else []
        componentes = list(db.scalars(select(ComponenteRegulatorio).where(
            ComponenteRegulatorio.codigo.in_(codigos_componente)
        ).order_by(ComponenteRegulatorio.codigo, ComponenteRegulatorio.id)).all()) if codigos_componente else []
        mp_ids = [item.id for item in mps]
        componente_ids = [item.id for item in componentes]
        categoria_ids = [item.id for item in categorias]
        composicoes = list(db.scalars(select(ComposicaoComponenteMP).where(
            ComposicaoComponenteMP.materia_prima_id.in_(mp_ids),
            ComposicaoComponenteMP.componente_id.in_(componente_ids),
        ).order_by(
            ComposicaoComponenteMP.materia_prima_id,
            ComposicaoComponenteMP.componente_id,
            ComposicaoComponenteMP.data_referencia,
            ComposicaoComponenteMP.id,
        )).all()) if mp_ids and componente_ids else []
        filtros_regras = []
        if categoria_ids and mp_ids:
            filtros_regras.append((
                RegraRegulatoria.tipo_alvo == "MATERIA_PRIMA"
            ) & RegraRegulatoria.categoria_id.in_(categoria_ids) & RegraRegulatoria.materia_prima_id.in_(mp_ids))
        if categoria_ids and componente_ids:
            filtros_regras.append((
                RegraRegulatoria.tipo_alvo == "COMPONENTE"
            ) & RegraRegulatoria.categoria_id.in_(categoria_ids) & RegraRegulatoria.componente_id.in_(componente_ids))
        regras = list(db.scalars(select(RegraRegulatoria).where(
            or_(*filtros_regras)
        ).order_by(
            RegraRegulatoria.categoria_id, RegraRegulatoria.tipo_alvo,
            RegraRegulatoria.materia_prima_id, RegraRegulatoria.componente_id,
            RegraRegulatoria.vigencia_inicio, RegraRegulatoria.vigencia_fim,
            RegraRegulatoria.revisao, RegraRegulatoria.id,
        )).all()) if filtros_regras else []
    return mps, categorias, componentes, composicoes, regras


def _estado_mp(dados, existentes, erros):
    estado = {
        item.codigo: {"ativo": item.ativa, "valido": True, "banco": item}
        for item in existentes
    }
    for item in dados["MATERIAS_PRIMAS"]:
        if (item["linha"] and ("MATERIAS_PRIMAS", item["linha"]) in erros):
            estado[item["codigo"]] = {"ativo": False, "valido": False, "banco": estado.get(item["codigo"], {}).get("banco")}
            continue
        atual = estado.get(item["codigo"])
        if item["acao"] == "CRIAR" and not atual:
            estado[item["codigo"]] = {"ativo": item.get("ativa") is not False, "valido": True, "banco": None}
        elif atual and item["acao"] == "ATUALIZAR" and item.get("ativa") is not None:
            atual["ativo"] = item["ativa"]
        elif atual and item["acao"] == "DESATIVAR":
            atual["ativo"] = False
    return estado


def _catalogos(dados, banco, aba, ativo_campo, diagnosticos, erros, propostas):
    estado = {
        item.codigo: {
            "ativo": getattr(item, ativo_campo), "nome": item.nome,
            "descricao": item.descricao, "valido": True, "banco": item,
        }
        for item in banco
    }
    for item in dados[aba]:
        codigo, acao, linha = item["codigo"], item["acao"], item["linha"]
        atual = estado.get(codigo)
        if (aba, linha) in erros:
            if atual:
                atual["valido"] = False
            elif codigo:
                estado[codigo] = {"ativo": False, "valido": False, "banco": None}
            continue
        if item.get("nome") is not None and len(item["nome"]) > 200:
            _diag(diagnosticos, erros, "VALOR_EXCEDE_LIMITE", aba, linha,
                  "Nome excede o limite de 200 caracteres.", "NOME")
            if atual:
                atual["valido"] = False
            elif codigo:
                estado[codigo] = {"ativo": False, "valido": False, "banco": None}
            continue
        if acao == "CRIAR":
            if atual and not atual["ativo"]:
                _diag(diagnosticos, erros, "REATIVACAO_NAO_SUPORTADA", aba, linha,
                      f"{codigo}: registro inativo não pode ser reativado por CRIAR.", "CODIGO")
            elif atual:
                identico = item["nome"] == atual["nome"] and item["descricao"] == atual["descricao"]
                if identico:
                    propostas.append(_op(aba, item, "SEM_ALTERACAO"))
                else:
                    _diag(diagnosticos, erros, "CRIAR_CONFLITA_EXISTENTE", aba, linha,
                          f"{codigo}: cadastro ativo existente possui conteúdo diferente.", "CODIGO")
            else:
                estado[codigo] = {"ativo": True, "nome": item["nome"], "descricao": item["descricao"],
                                  "valido": True, "banco": None}
                propostas.append(_op(aba, item, "CRIAR", ("nome", "descricao")))
        elif acao == "ATUALIZAR":
            if not atual:
                _diag(diagnosticos, erros, "REGISTRO_NAO_ENCONTRADO", aba, linha,
                      f"{codigo}: cadastro não encontrado para atualização.", "CODIGO")
            elif not atual["ativo"]:
                _diag(diagnosticos, erros, "REGISTRO_INATIVO", aba, linha,
                      f"{codigo}: cadastro inativo não pode ser atualizado.", "CODIGO")
            else:
                novo_nome = item["nome"] if item["nome"] is not None else atual["nome"]
                nova_descricao = item["descricao"] if item["descricao"] is not None else atual["descricao"]
                campos = []
                if novo_nome != atual["nome"]: campos.append("nome")
                if nova_descricao != atual["descricao"]: campos.append("descricao")
                atual.update(nome=novo_nome, descricao=nova_descricao)
                propostas.append(_op(aba, item, "ATUALIZAR" if campos else "SEM_ALTERACAO", campos))
        elif acao == "DESATIVAR":
            if not atual:
                _diag(diagnosticos, erros, "REGISTRO_NAO_ENCONTRADO", aba, linha,
                      f"{codigo}: cadastro não encontrado para desativação.", "CODIGO")
            elif not atual["ativo"]:
                propostas.append(_op(aba, item, "SEM_ALTERACAO"))
            else:
                atual["ativo"] = False
                propostas.append(_op(aba, item, "DESATIVAR", (ativo_campo,)))
        if (aba, linha) in erros:
            if atual:
                atual["valido"] = False
            elif codigo:
                estado[codigo] = {"ativo": False, "valido": False, "banco": None}
    return estado


def _referencia(estado, codigo, aba, linha, coluna, diagnosticos, erros):
    item = estado.get(codigo)
    if not item:
        _diag(diagnosticos, erros, "REFERENCIA_INEXISTENTE", aba, linha,
              f"{codigo}: referência não encontrada no banco nem no lote.", coluna)
        return False
    if not item["valido"]:
        _diag(diagnosticos, erros, "DEPENDENCIA_INVALIDA", aba, linha,
              f"{codigo}: referência depende de uma linha inválida.", coluna)
        return False
    if not item["ativo"]:
        codigo_diag = "REFERENCIA_DESATIVADA_NO_LOTE" if item.get("desativada_lote") else "REFERENCIA_INATIVA"
        _diag(diagnosticos, erros, codigo_diag, aba, linha,
              f"{codigo}: referência está inativa no estado projetado.", coluna)
        return False
    return True


def validar_regulatorio(db, dados, diagnosticos, erros, propostas):
    mps, categorias, componentes, composicoes, regras = _consultar(db, dados)
    estado_mp = _estado_mp(dados, mps, erros)
    estado_categoria = _catalogos(
        dados, categorias, "CATEGORIAS_PRODUTO", "ativa", diagnosticos, erros, propostas
    )
    estado_componente = _catalogos(
        dados, componentes, "COMPONENTES_REGULATORIOS", "ativo", diagnosticos, erros, propostas
    )
    for aba, estado in (("MATERIAS_PRIMAS", estado_mp), ("CATEGORIAS_PRODUTO", estado_categoria),
                        ("COMPONENTES_REGULATORIOS", estado_componente)):
        for item in dados[aba]:
            if item["acao"] == "DESATIVAR" and (aba, item["linha"]) not in erros and item.get("codigo") in estado:
                estado[item["codigo"]]["desativada_lote"] = True

    mp_codigo = {item.id: item.codigo for item in mps}
    comp_codigo = {item.id: item.codigo for item in componentes}
    cat_codigo = {item.id: item.codigo for item in categorias}
    comp_banco = {
        (mp_codigo[item.materia_prima_id], comp_codigo[item.componente_id], item.data_referencia): item
        for item in composicoes
    }
    for item in dados["COMPOSICAO_COMPONENTES_MP"]:
        aba, linha = "COMPOSICAO_COMPONENTES_MP", item["linha"]
        concentracao = _decimal(item["concentracao"])
        if not _decimal_compativel_bd(concentracao):
            _diag(diagnosticos, erros, "VALOR_EXCEDE_PRECISAO", aba, linha,
                  "Concentração excede a precisão de 18 dígitos e 6 casas decimais.",
                  "CONCENTRACAO")
        if (aba, linha) in erros:
            continue
        chave = (item["materia_prima_codigo"], item["componente_codigo"], _data(item["data_referencia"]))
        refs = (True, True)
        if item["acao"] == "CRIAR":
            refs = (
                _referencia(estado_mp, chave[0], aba, linha, "MATERIA_PRIMA_CODIGO", diagnosticos, erros),
                _referencia(estado_componente, chave[1], aba, linha, "COMPONENTE_CODIGO", diagnosticos, erros),
            )
        existente = comp_banco.get(chave)
        if item["acao"] == "CRIAR":
            if existente and not existente.ativo:
                _diag(diagnosticos, erros, "REATIVACAO_NAO_SUPORTADA", aba, linha,
                      "Composição inativa não pode ser reativada.", "ACAO")
            elif existente:
                igual = (
                    existente.situacao == item["situacao"]
                    and existente.concentracao == concentracao
                    and existente.fonte == item["fonte"]
                    and existente.observacao == item["observacao"]
                )
                if igual:
                    propostas.append(_op(aba, item, "SEM_ALTERACAO"))
                else:
                    _diag(diagnosticos, erros, "ATUALIZACAO_IMUTAVEL", aba, linha,
                          "Composição existente é imutável e possui conteúdo diferente.", "ACAO")
            elif all(refs):
                propostas.append(_op(aba, item, "CRIAR", ("situacao", "concentracao", "fonte", "observacao")))
        else:
            if not existente:
                _diag(diagnosticos, erros, "REGISTRO_NAO_ENCONTRADO", aba, linha,
                      "Composição não encontrada para desativação.", "ACAO")
            elif not existente.ativo:
                propostas.append(_op(aba, item, "SEM_ALTERACAO"))
            else:
                propostas.append(_op(aba, item, "DESATIVAR", ("ativo",)))

    regras_banco = []
    for regra in regras:
        alvo = mp_codigo.get(regra.materia_prima_id) if regra.tipo_alvo == "MATERIA_PRIMA" else comp_codigo.get(regra.componente_id)
        regras_banco.append({
            "obj": regra, "categoria": cat_codigo[regra.categoria_id], "tipo": regra.tipo_alvo,
            "alvo": alvo, "inicio": regra.vigencia_inicio, "fim": regra.vigencia_fim,
            "ativa": regra.ativa,
        })

    linhas_regras = [
        (aba, item)
        for aba in ("REGRAS_REGULATORIAS_MP", "REGRAS_REGULATORIAS_COMPONENTE")
        for item in dados[aba]
    ]
    desativadas = set()
    for aba, item in linhas_regras:
        if item["acao"] != "DESATIVAR" or (aba, item["linha"]) in erros:
            continue
        tipo = item["tipo_alvo"]
        alvo = item["materia_prima_codigo"] or item["componente_codigo"]
        identidade = (item["categoria_codigo"], tipo, alvo, _data(item["vigencia_inicio"]), _data(item["vigencia_fim"]))
        ativas = [r for r in regras_banco if r["ativa"] and
                  (r["categoria"], r["tipo"], r["alvo"], r["inicio"], r["fim"]) == identidade]
        inativas = [r for r in regras_banco if not r["ativa"] and
                    (r["categoria"], r["tipo"], r["alvo"], r["inicio"], r["fim"]) == identidade]
        if len(ativas) == 1:
            desativadas.add(id(ativas[0]["obj"]))
            propostas.append(_op(aba, item, "DESATIVAR", ("ativa",)))
        elif len(ativas) > 1:
            _diag(diagnosticos, erros, "REGRA_AMBIGUA", aba, item["linha"],
                  "Mais de uma regra ativa corresponde à identidade informada.", "ACAO")
        elif inativas:
            propostas.append(_op(aba, item, "SEM_ALTERACAO"))
        else:
            sobrepostas = [r for r in regras_banco if r["ativa"] and r["categoria"] == identidade[0]
                           and r["tipo"] == tipo and r["alvo"] == alvo
                           and _sobrepoe(identidade[3], identidade[4], r["inicio"], r["fim"])]
            codigo = "REGRA_NAO_ENCONTRADA" if not sobrepostas else "REGRA_SOBREPOSTA"
            _diag(diagnosticos, erros, codigo, aba, item["linha"],
                  "Regra com identidade exata não encontrada para desativação.", "ACAO")

    projetadas = [r for r in regras_banco if r["ativa"] and id(r["obj"]) not in desativadas]
    for aba, item in linhas_regras:
        if item["acao"] == "DESATIVAR":
            continue
        linha = item["linha"]
        minimo, maximo = _decimal(item["minimo"]), _decimal(item["maximo"])
        if not _decimal_compativel_bd(minimo) or not _decimal_compativel_bd(maximo):
            _diag(diagnosticos, erros, "VALOR_EXCEDE_PRECISAO", aba, linha,
                  "Limite excede a precisão de 18 dígitos e 6 casas decimais.",
                  "MINIMO" if not _decimal_compativel_bd(minimo) else "MAXIMO")
        if (aba, linha) in erros:
            continue
        tipo = item["tipo_alvo"]
        alvo = item["materia_prima_codigo"] or item["componente_codigo"]
        refs_ok = (
            _referencia(estado_categoria, item["categoria_codigo"], aba, linha, "CATEGORIA_CODIGO", diagnosticos, erros)
            and _referencia(estado_mp if tipo == "MATERIA_PRIMA" else estado_componente, alvo, aba, linha,
                           "MATERIA_PRIMA_CODIGO" if tipo == "MATERIA_PRIMA" else "COMPONENTE_CODIGO",
                           diagnosticos, erros)
        )
        identidade = (item["categoria_codigo"], tipo, alvo, _data(item["vigencia_inicio"]), _data(item["vigencia_fim"]))
        exatas = [r for r in projetadas if
                  (r["categoria"], r["tipo"], r["alvo"], r["inicio"], r["fim"]) == identidade]
        conteudo = (
            item["tratamento"], minimo, maximo,
            item["justificativa"], item["referencia_normativa"], item.get("unidade"), item.get("base"),
        )
        def semantica(regra):
            obj = regra["obj"]
            return (obj.tratamento, obj.minimo, obj.maximo, obj.justificativa,
                    obj.referencia_normativa, obj.unidade, obj.base)
        if item["acao"] == "ATUALIZAR":
            if len(exatas) != 1:
                _diag(diagnosticos, erros, "REGRA_AMBIGUA" if len(exatas) > 1 else "REGRA_NAO_ENCONTRADA",
                      aba, linha, "Regra ativa com identidade exata não encontrada de forma unívoca.", "ACAO")
            elif semantica(exatas[0]) == conteudo:
                propostas.append(_op(aba, item, "SEM_ALTERACAO"))
            elif refs_ok:
                propostas.append(_op(aba, item, "ATUALIZAR",
                                     ("tratamento", "minimo", "maximo", "justificativa", "referencia_normativa")))
                projetadas.remove(exatas[0])
                projetadas.append({"obj": _RegraProjetada(conteudo), "categoria": identidade[0],
                                   "tipo": tipo, "alvo": alvo, "inicio": identidade[3], "fim": identidade[4],
                                   "ativa": True})
        elif item["acao"] == "CRIAR":
            if exatas:
                if len(exatas) == 1 and semantica(exatas[0]) == conteudo:
                    propostas.append(_op(aba, item, "SEM_ALTERACAO"))
                else:
                    _diag(diagnosticos, erros, "CRIAR_CONFLITA_EXISTENTE", aba, linha,
                          "Regra com a mesma identidade possui conteúdo diferente; use ATUALIZAR.", "ACAO")
                continue
            historica = [r for r in regras_banco if not r["ativa"] and
                         (r["categoria"], r["tipo"], r["alvo"], r["inicio"], r["fim"]) == identidade]
            if historica:
                _diag(diagnosticos, erros, "REATIVACAO_NAO_SUPORTADA", aba, linha,
                      "A identidade possui histórico inativo e não pode ser reativada por CRIAR.", "ACAO")
                continue
            sobrepostas = [r for r in projetadas if r["categoria"] == identidade[0]
                           and r["tipo"] == tipo and r["alvo"] == alvo
                           and _sobrepoe(identidade[3], identidade[4], r["inicio"], r["fim"])]
            if sobrepostas:
                _diag(diagnosticos, erros, "REGRA_SOBREPOSTA", aba, linha,
                      "Existe regra ativa com vigência sobreposta para a categoria e o alvo.", "VIGENCIA_INICIO")
            elif refs_ok:
                propostas.append(_op(aba, item, "CRIAR",
                                     ("tratamento", "minimo", "maximo", "justificativa",
                                      "referencia_normativa", "vigencia_inicio", "vigencia_fim")))
                projetadas.append({"obj": _RegraProjetada(conteudo), "categoria": identidade[0],
                                   "tipo": tipo, "alvo": alvo, "inicio": identidade[3], "fim": identidade[4],
                                   "ativa": True})


class _RegraProjetada:
    def __init__(self, conteudo):
        (self.tratamento, self.minimo, self.maximo, self.justificativa,
         self.referencia_normativa, self.unidade, self.base) = conteudo
