from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from models import ComposicaoMateriaPrima, MateriaPrima, Nutriente, PrecoMateriaPrima
from services.planilha_cadastral import ABAS, parsear_planilha_cadastral


MAX_DIAGNOSTICOS_RESPOSTA = 200
MAX_OPERACOES_RESPOSTA = 500


def _diagnostico(severidade, aba, mensagem, linha=None, coluna=None, codigo=None):
    return {
        "severidade": severidade,
        "aba": aba,
        "linha": linha,
        "coluna": coluna,
        "codigo": codigo,
        "mensagem": mensagem,
    }


def _resumo_vazio():
    return {
        aba: {
            "criar": 0,
            "atualizar": 0,
            "desativar": 0,
            "sem_alteracao": 0,
            "avisos": 0,
            "erros": 0,
        }
        for aba in (*ABAS, "GERAL")
    }


def _adicionar_diagnostico(diagnosticos, erros_por_linha, severidade, aba, mensagem,
                           linha=None, coluna=None, codigo=None):
    diagnosticos.append(_diagnostico(severidade, aba, mensagem, linha, coluna, codigo))
    if severidade == "ERRO" and aba and linha is not None:
        erros_por_linha.add((aba, linha))


def _decimal(valor):
    if valor is None:
        return None
    try:
        return Decimal(valor)
    except (InvalidOperation, ValueError):
        return None


def _decimal_compativel_bd(valor: Decimal | None) -> bool:
    if valor is None or not valor.is_finite():
        return False
    sinal, digitos, expoente = valor.as_tuple()
    casas = max(-expoente, 0)
    inteiros = max(len(digitos) + expoente, 0)
    return casas <= 6 and inteiros <= 12


def _periodos_sobrepostos(inicio_a, fim_a, inicio_b, fim_b):
    return inicio_a <= (fim_b or date.max) and inicio_b <= (fim_a or date.max)


def _consultar_estado(db: Session, dados):
    codigos_mp = {
        item["codigo"] for item in dados["MATERIAS_PRIMAS"] if item["codigo"]
    } | {
        item["materia_prima_codigo"]
        for aba in ("COMPOSICAO_NUTRICIONAL", "PRECOS_MP")
        for item in dados[aba]
        if item["materia_prima_codigo"]
    }
    nomes_mp = {
        item["nome"] for item in dados["MATERIAS_PRIMAS"] if item["nome"]
    }
    codigos_nutriente = {
        item["codigo"] for item in dados["NUTRIENTES"] if item["codigo"]
    } | {
        item["nutriente_codigo"]
        for item in dados["COMPOSICAO_NUTRICIONAL"]
        if item["nutriente_codigo"]
    }
    nomes_nutriente = {
        item["nome"] for item in dados["NUTRIENTES"] if item["nome"]
    }

    with db.no_autoflush:
        mps = list(db.scalars(select(MateriaPrima).where(
            or_(MateriaPrima.codigo.in_(codigos_mp), MateriaPrima.nome.in_(nomes_mp))
        ).order_by(MateriaPrima.codigo, MateriaPrima.id)).all()) if codigos_mp or nomes_mp else []
        nutrientes = list(db.scalars(select(Nutriente).where(
            or_(Nutriente.codigo.in_(codigos_nutriente), Nutriente.nome.in_(nomes_nutriente))
        ).order_by(Nutriente.codigo, Nutriente.id)).all()) if codigos_nutriente or nomes_nutriente else []

        mp_ids = [item.id for item in mps if item.codigo in codigos_mp]
        nutriente_ids = [item.id for item in nutrientes if item.codigo in codigos_nutriente]
        composicoes = []
        if mp_ids and nutriente_ids:
            composicoes = list(db.scalars(select(ComposicaoMateriaPrima).where(
                ComposicaoMateriaPrima.materia_prima_id.in_(mp_ids),
                ComposicaoMateriaPrima.nutriente_id.in_(nutriente_ids),
            ).order_by(
                ComposicaoMateriaPrima.materia_prima_id,
                ComposicaoMateriaPrima.nutriente_id,
                ComposicaoMateriaPrima.id,
            )).all())
        precos = list(db.scalars(select(PrecoMateriaPrima).where(
            PrecoMateriaPrima.materia_prima_id.in_(mp_ids)
        ).order_by(
            PrecoMateriaPrima.materia_prima_id,
            PrecoMateriaPrima.vigencia_inicio,
            PrecoMateriaPrima.id,
        )).all()) if mp_ids else []
        usos_nutrientes = dict(db.execute(
            select(ComposicaoMateriaPrima.nutriente_id, func.count())
            .where(ComposicaoMateriaPrima.nutriente_id.in_(nutriente_ids))
            .group_by(ComposicaoMateriaPrima.nutriente_id)
        ).all()) if nutriente_ids else {}

    return mps, nutrientes, composicoes, precos, usos_nutrientes


def _finalizar(versao, digest, dados, diagnosticos, propostas, erros_por_linha):
    ordem_abas = {aba: indice for indice, aba in enumerate((*ABAS, "GERAL"))}
    diagnosticos = sorted(
        diagnosticos,
        key=lambda item: (
            ordem_abas.get(item["aba"] or "GERAL", len(ordem_abas)),
            item["linha"] if item["linha"] is not None else -1,
            item["coluna"] or "",
            item["codigo"] or "",
            item["severidade"],
            item["mensagem"],
        ),
    )
    propostas = sorted(
        propostas,
        key=lambda item: (
            ordem_abas.get(item["aba"], len(ordem_abas)),
            item["codigo"] or "",
            item["linha"],
        ),
    )
    resumo = _resumo_vazio()
    operacoes = []
    for proposta in propostas:
        if (proposta["aba"], proposta["linha"]) in erros_por_linha:
            continue
        resultado = proposta["resultado"]
        chave = {
            "CRIAR": "criar",
            "ATUALIZAR": "atualizar",
            "DESATIVAR": "desativar",
            "SEM_ALTERACAO": "sem_alteracao",
        }[resultado]
        resumo[proposta["aba"]][chave] += 1
        operacoes.append(proposta)

    for item in diagnosticos:
        aba = item["aba"] if item["aba"] in resumo else "GERAL"
        if item["severidade"] == "ERRO":
            resumo[aba]["erros"] += 1
        elif item["severidade"] == "AVISO":
            resumo[aba]["avisos"] += 1

    erros = sum(1 for item in diagnosticos if item["severidade"] == "ERRO")
    diagnosticos_total = len(diagnosticos)
    operacoes_total = len(operacoes)
    truncado = (
        diagnosticos_total > MAX_DIAGNOSTICOS_RESPOSTA
        or operacoes_total > MAX_OPERACOES_RESPOSTA
    )
    return {
        "versao": versao,
        "sha256": digest,
        "valido_para_confirmacao": erros == 0,
        "resumo": resumo,
        "operacoes": operacoes[:MAX_OPERACOES_RESPOSTA],
        "operacoes_total": operacoes_total,
        "diagnosticos": diagnosticos[:MAX_DIAGNOSTICOS_RESPOSTA],
        "diagnosticos_total": diagnosticos_total,
        "resultado_truncado": truncado,
    }


def pre_validar_planilha_cadastral(
    conteudo: bytes,
    nome_arquivo: str,
    db: Session,
    digest_arquivo: str | None = None,
) -> dict:
    digest = digest_arquivo or sha256(conteudo).hexdigest()
    estrutural = parsear_planilha_cadastral(conteudo, nome_arquivo)
    dados = estrutural["dados"]
    diagnosticos = [
        item
        for item in estrutural["diagnosticos"]
        if not (
            item["severidade"] == "AVISO"
            and "deverá existir no banco na pré-validação" in item["mensagem"]
        )
    ]
    erros_por_linha = {
        (item["aba"], item["linha"])
        for item in diagnosticos
        if item["severidade"] == "ERRO" and item["aba"] and item["linha"] is not None
    }
    propostas = []
    if not estrutural["valido"]:
        return _finalizar(
            estrutural["versao"], digest, dados, diagnosticos, propostas, erros_por_linha
        )

    mps, nutrientes, composicoes, precos, usos_nutrientes = _consultar_estado(db, dados)
    mp_por_codigo = {item.codigo: item for item in mps}
    mp_por_nome = {item.nome: item for item in mps}
    nutriente_por_codigo = {item.codigo: item for item in nutrientes}
    nutriente_por_nome = {item.nome: item for item in nutrientes}
    composicao_por_chave = {
        (item.materia_prima_id, item.nutriente_id): item for item in composicoes
    }
    precos_por_mp = defaultdict(list)
    for item in precos:
        precos_por_mp[item.materia_prima_id].append(item)

    nomes_mp_workbook = defaultdict(list)
    for item in dados["MATERIAS_PRIMAS"]:
        if item["nome"]:
            nomes_mp_workbook[item["nome"]].append(item)
    nomes_nutriente_workbook = defaultdict(list)
    for item in dados["NUTRIENTES"]:
        if item["nome"]:
            nomes_nutriente_workbook[item["nome"]].append(item)

    for item in dados["MATERIAS_PRIMAS"]:
        linha, codigo, acao = item["linha"], item["codigo"], item["acao"]
        existente = mp_por_codigo.get(codigo)
        if item["nome"] is not None and len(item["nome"]) > 200:
            _adicionar_diagnostico(diagnosticos, erros_por_linha, "ERRO", "MATERIAS_PRIMAS",
                                   "Nome excede o limite de 200 caracteres.", linha, "NOME", codigo)
        if item["nome"] and len(nomes_mp_workbook[item["nome"]]) > 1:
            _adicionar_diagnostico(diagnosticos, erros_por_linha, "ERRO", "MATERIAS_PRIMAS",
                                   "Nome repetido entre matérias-primas do arquivo.", linha, "NOME", codigo)
        if acao == "CRIAR":
            if existente:
                _adicionar_diagnostico(diagnosticos, erros_por_linha, "ERRO", "MATERIAS_PRIMAS",
                                       "Código de matéria-prima já cadastrado.", linha, "CODIGO", codigo)
            conflito_nome = mp_por_nome.get(item["nome"])
            if conflito_nome and conflito_nome.codigo != codigo:
                _adicionar_diagnostico(diagnosticos, erros_por_linha, "ERRO", "MATERIAS_PRIMAS",
                                       "Nome de matéria-prima já pertence a outro código.", linha, "NOME", codigo)
            propostas.append({"aba": "MATERIAS_PRIMAS", "linha": linha, "codigo": codigo,
                              "acao": acao, "resultado": "CRIAR",
                              "campos_alterados": ["nome", "ativa"]})
        elif acao == "ATUALIZAR":
            if not existente:
                _adicionar_diagnostico(diagnosticos, erros_por_linha, "ERRO", "MATERIAS_PRIMAS",
                                       "Matéria-prima não encontrada para atualização.", linha, "CODIGO", codigo)
                continue
            conflito_nome = mp_por_nome.get(item["nome"]) if item["nome"] else None
            if conflito_nome and conflito_nome.id != existente.id:
                _adicionar_diagnostico(diagnosticos, erros_por_linha, "ERRO", "MATERIAS_PRIMAS",
                                       "Nome de matéria-prima já pertence a outro código.", linha, "NOME", codigo)
            campos = []
            if item["nome"] is not None and item["nome"] != existente.nome:
                campos.append("nome")
            if item["ativa"] is not None and item["ativa"] != existente.ativa:
                campos.append("ativa")
            propostas.append({"aba": "MATERIAS_PRIMAS", "linha": linha, "codigo": codigo,
                              "acao": acao, "resultado": "ATUALIZAR" if campos else "SEM_ALTERACAO",
                              "campos_alterados": campos})
        elif acao == "DESATIVAR":
            if not existente:
                _adicionar_diagnostico(diagnosticos, erros_por_linha, "ERRO", "MATERIAS_PRIMAS",
                                       "Matéria-prima não encontrada para desativação.", linha, "CODIGO", codigo)
                continue
            propostas.append({"aba": "MATERIAS_PRIMAS", "linha": linha, "codigo": codigo,
                              "acao": acao,
                              "resultado": "DESATIVAR" if existente.ativa else "SEM_ALTERACAO",
                              "campos_alterados": ["ativa"] if existente.ativa else []})

    for item in dados["NUTRIENTES"]:
        linha, codigo, acao = item["linha"], item["codigo"], item["acao"]
        existente = nutriente_por_codigo.get(codigo)
        if item["nome"] is not None and len(item["nome"]) > 120:
            _adicionar_diagnostico(diagnosticos, erros_por_linha, "ERRO", "NUTRIENTES",
                                   "Nome excede o limite de 120 caracteres.", linha, "NOME", codigo)
        if item["unidade"] is not None and len(item["unidade"]) > 30:
            _adicionar_diagnostico(diagnosticos, erros_por_linha, "ERRO", "NUTRIENTES",
                                   "Unidade excede o limite de 30 caracteres.", linha, "UNIDADE", codigo)
        if item["nome"] and len(nomes_nutriente_workbook[item["nome"]]) > 1:
            _adicionar_diagnostico(diagnosticos, erros_por_linha, "ERRO", "NUTRIENTES",
                                   "Nome repetido entre nutrientes do arquivo.", linha, "NOME", codigo)
        if acao == "CRIAR":
            if existente:
                _adicionar_diagnostico(diagnosticos, erros_por_linha, "ERRO", "NUTRIENTES",
                                       "Código de nutriente já cadastrado.", linha, "CODIGO", codigo)
            conflito_nome = nutriente_por_nome.get(item["nome"])
            if conflito_nome and conflito_nome.codigo != codigo:
                _adicionar_diagnostico(diagnosticos, erros_por_linha, "ERRO", "NUTRIENTES",
                                       "Nome de nutriente já pertence a outro código.", linha, "NOME", codigo)
            propostas.append({"aba": "NUTRIENTES", "linha": linha, "codigo": codigo,
                              "acao": acao, "resultado": "CRIAR",
                              "campos_alterados": ["nome", "unidade"]})
        elif acao == "ATUALIZAR":
            if not existente:
                _adicionar_diagnostico(diagnosticos, erros_por_linha, "ERRO", "NUTRIENTES",
                                       "Nutriente não encontrado para atualização.", linha, "CODIGO", codigo)
                continue
            conflito_nome = nutriente_por_nome.get(item["nome"]) if item["nome"] else None
            if conflito_nome and conflito_nome.id != existente.id:
                _adicionar_diagnostico(diagnosticos, erros_por_linha, "ERRO", "NUTRIENTES",
                                       "Nome de nutriente já pertence a outro código.", linha, "NOME", codigo)
            campos = []
            if item["nome"] is not None and item["nome"] != existente.nome:
                campos.append("nome")
            if item["unidade"] is not None and item["unidade"] != existente.unidade:
                if usos_nutrientes.get(existente.id, 0):
                    _adicionar_diagnostico(
                        diagnosticos, erros_por_linha, "ERRO", "NUTRIENTES",
                        "A unidade não pode ser alterada porque o nutriente possui composições históricas.",
                        linha, "UNIDADE", codigo,
                    )
                else:
                    campos.append("unidade")
            propostas.append({"aba": "NUTRIENTES", "linha": linha, "codigo": codigo,
                              "acao": acao, "resultado": "ATUALIZAR" if campos else "SEM_ALTERACAO",
                              "campos_alterados": campos})

    mps_workbook = {item["codigo"]: item for item in dados["MATERIAS_PRIMAS"] if item["codigo"]}
    nutrientes_workbook = {item["codigo"]: item for item in dados["NUTRIENTES"] if item["codigo"]}

    def resolver_mp(codigo):
        item = mps_workbook.get(codigo)
        if item and item["acao"] == "CRIAR":
            if ("MATERIAS_PRIMAS", item["linha"]) in erros_por_linha:
                return "WORKBOOK_INVALIDO", item
            return "WORKBOOK", item
        existente = mp_por_codigo.get(codigo)
        return ("BANCO", existente) if existente else (None, None)

    def resolver_nutriente(codigo):
        item = nutrientes_workbook.get(codigo)
        if item and item["acao"] == "CRIAR":
            if ("NUTRIENTES", item["linha"]) in erros_por_linha:
                return "WORKBOOK_INVALIDO", item
            return "WORKBOOK", item
        existente = nutriente_por_codigo.get(codigo)
        return ("BANCO", existente) if existente else (None, None)

    for item in dados["COMPOSICAO_NUTRICIONAL"]:
        aba, linha, acao = "COMPOSICAO_NUTRICIONAL", item["linha"], item["acao"]
        codigo = f'{item["materia_prima_codigo"]}/{item["nutriente_codigo"]}'
        origem_mp, mp = resolver_mp(item["materia_prima_codigo"])
        origem_nutriente, nutriente = resolver_nutriente(item["nutriente_codigo"])
        mp_lote = mps_workbook.get(item["materia_prima_codigo"])
        if origem_mp == "WORKBOOK_INVALIDO":
            _adicionar_diagnostico(diagnosticos, erros_por_linha, "ERRO", aba,
                                   "Matéria-prima referenciada possui criação inválida no arquivo.", linha,
                                   "MATERIA_PRIMA_CODIGO", item["materia_prima_codigo"])
        elif not mp:
            _adicionar_diagnostico(diagnosticos, erros_por_linha, "ERRO", aba,
                                   "Matéria-prima referenciada não existe no arquivo nem no banco.", linha,
                                   "MATERIA_PRIMA_CODIGO", item["materia_prima_codigo"])
        elif (origem_mp == "BANCO" and not mp.ativa) or (
            mp_lote and (mp_lote["acao"] == "DESATIVAR" or mp_lote.get("ativa") is False)
        ):
            _adicionar_diagnostico(diagnosticos, erros_por_linha, "ERRO", aba,
                                   "Composição não pode usar matéria-prima inativa ou desativada no lote.", linha,
                                   "MATERIA_PRIMA_CODIGO", item["materia_prima_codigo"])
        if origem_nutriente == "WORKBOOK_INVALIDO":
            _adicionar_diagnostico(diagnosticos, erros_por_linha, "ERRO", aba,
                                   "Nutriente referenciado possui criação inválida no arquivo.", linha,
                                   "NUTRIENTE_CODIGO", item["nutriente_codigo"])
        elif not nutriente:
            _adicionar_diagnostico(diagnosticos, erros_por_linha, "ERRO", aba,
                                   "Nutriente referenciado não existe no arquivo nem no banco.", linha,
                                   "NUTRIENTE_CODIGO", item["nutriente_codigo"])
        valor = _decimal(item["valor"])
        if valor is not None and not _decimal_compativel_bd(valor):
            _adicionar_diagnostico(diagnosticos, erros_por_linha, "ERRO", aba,
                                   "Valor excede a precisão suportada de 18 dígitos e 6 casas decimais.",
                                   linha, "VALOR", codigo)
        existente = None
        if origem_mp == origem_nutriente == "BANCO":
            existente = composicao_por_chave.get((mp.id, nutriente.id))
        if acao == "CRIAR" and existente:
            _adicionar_diagnostico(diagnosticos, erros_por_linha, "ERRO", aba,
                                   "Composição já cadastrada para este par de códigos.", linha, None, codigo)
        elif acao == "ATUALIZAR" and not existente:
            _adicionar_diagnostico(diagnosticos, erros_por_linha, "ERRO", aba,
                                   "Composição não encontrada para atualização.", linha, None, codigo)
        resultado = "CRIAR" if acao == "CRIAR" else "ATUALIZAR"
        campos = ["valor"]
        if existente and valor == existente.valor:
            resultado, campos = "SEM_ALTERACAO", []
        propostas.append({"aba": aba, "linha": linha, "codigo": codigo, "acao": acao,
                          "resultado": resultado, "campos_alterados": campos})

    propostas_preco = []
    for item in dados["PRECOS_MP"]:
        aba, linha = "PRECOS_MP", item["linha"]
        codigo = item["materia_prima_codigo"]
        origem_mp, mp = resolver_mp(codigo)
        mp_lote = mps_workbook.get(codigo)
        if origem_mp == "WORKBOOK_INVALIDO":
            _adicionar_diagnostico(diagnosticos, erros_por_linha, "ERRO", aba,
                                   "Matéria-prima referenciada possui criação inválida no arquivo.", linha,
                                   "MATERIA_PRIMA_CODIGO", codigo)
        elif not mp:
            _adicionar_diagnostico(diagnosticos, erros_por_linha, "ERRO", aba,
                                   "Matéria-prima referenciada não existe no arquivo nem no banco.", linha,
                                   "MATERIA_PRIMA_CODIGO", codigo)
        elif (origem_mp == "BANCO" and not mp.ativa) or (
            mp_lote and (mp_lote["acao"] == "DESATIVAR" or mp_lote.get("ativa") is False)
        ):
            _adicionar_diagnostico(diagnosticos, erros_por_linha, "ERRO", aba,
                                   "Preço não pode usar matéria-prima inativa ou desativada no lote.", linha,
                                   "MATERIA_PRIMA_CODIGO", codigo)
        preco = _decimal(item["preco_kg"])
        if preco is not None and not _decimal_compativel_bd(preco):
            _adicionar_diagnostico(diagnosticos, erros_por_linha, "ERRO", aba,
                                   "Preço excede a precisão suportada de 18 dígitos e 6 casas decimais.",
                                   linha, "PRECO_KG", codigo)
        inicio = date.fromisoformat(item["vigencia_inicio"]) if item["vigencia_inicio"] else None
        fim = date.fromisoformat(item["vigencia_fim"]) if item["vigencia_fim"] else None
        proposta = {"aba": aba, "linha": linha, "codigo": codigo, "acao": "CRIAR",
                    "resultado": "CRIAR",
                    "campos_alterados": ["preco_kg", "vigencia_inicio", "vigencia_fim"],
                    "inicio": inicio, "fim": fim, "origem_mp": origem_mp, "mp": mp}
        propostas_preco.append(proposta)
        if origem_mp == "BANCO" and inicio:
            for existente in sorted(
                precos_por_mp[mp.id],
                key=lambda valor: (valor.vigencia_inicio, valor.vigencia_fim or date.max, valor.id),
            ):
                if _periodos_sobrepostos(inicio, fim, existente.vigencia_inicio, existente.vigencia_fim):
                    _adicionar_diagnostico(
                        diagnosticos, erros_por_linha, "ERRO", aba,
                        f"Período de preço se sobrepõe à vigência existente iniciada em {existente.vigencia_inicio.isoformat()}.",
                        linha, "VIGENCIA_INICIO", codigo,
                    )

    por_codigo = defaultdict(list)
    for proposta in propostas_preco:
        por_codigo[proposta["codigo"]].append(proposta)
    for codigo in sorted(por_codigo):
        itens = sorted(
            por_codigo[codigo],
            key=lambda item: (
                item["inicio"] or date.min,
                item["fim"] or date.max,
                item["linha"],
            ),
        )
        for indice, atual in enumerate(itens):
            if not atual["inicio"]:
                continue
            for anterior in itens[:indice]:
                if anterior["inicio"] and _periodos_sobrepostos(
                    atual["inicio"], atual["fim"], anterior["inicio"], anterior["fim"]
                ):
                    _adicionar_diagnostico(
                        diagnosticos, erros_por_linha, "ERRO", "PRECOS_MP",
                        f"Período de preço se sobrepõe à linha {anterior['linha']} do arquivo.",
                        atual["linha"], "VIGENCIA_INICIO", codigo,
                    )
                    _adicionar_diagnostico(
                        diagnosticos, erros_por_linha, "ERRO", "PRECOS_MP",
                        f"Período de preço se sobrepõe à linha {atual['linha']} do arquivo.",
                        anterior["linha"], "VIGENCIA_INICIO", codigo,
                    )
    for item in propostas_preco:
        item.pop("inicio")
        item.pop("fim")
        item.pop("origem_mp")
        item.pop("mp")
        propostas.append(item)

    return _finalizar(
        estrutural["versao"], digest, dados, diagnosticos, propostas, erros_por_linha
    )
