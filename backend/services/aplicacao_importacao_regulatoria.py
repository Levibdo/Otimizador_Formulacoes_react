from datetime import date
from decimal import Decimal

from sqlalchemy import or_, select

from models import ComposicaoMateriaPrima, MateriaPrima, Nutriente, PrecoMateriaPrima
from models.regulatorio import (
    CategoriaProduto,
    ComponenteRegulatorio,
    ComposicaoComponenteMP,
    RegraRegulatoria,
)


ABAS_REGRAS = (
    "REGRAS_REGULATORIAS_MP",
    "REGRAS_REGULATORIAS_COMPONENTE",
)


def _data(valor):
    return date.fromisoformat(valor) if valor else None


def _decimal(valor):
    return Decimal(valor) if valor is not None else None


def _resultados(operacoes):
    return {
        (item["aba"], item["linha"]): item["resultado"]
        for item in operacoes
    }


def _mapa_codigos(db, model, codigos):
    codigos = {codigo for codigo in codigos if codigo}
    if not codigos:
        return {}
    itens = db.scalars(
        select(model).where(model.codigo.in_(codigos)).order_by(model.codigo, model.id)
    ).all()
    return {item.codigo: item for item in itens}


def _aplicar_catalogos_base(db, dados, resultados):
    nutrientes = _mapa_codigos(
        db, Nutriente, (item["codigo"] for item in dados["NUTRIENTES"])
    )
    for item in sorted(dados["NUTRIENTES"], key=lambda valor: (valor["codigo"], valor["linha"])):
        resultado = resultados.get(("NUTRIENTES", item["linha"]))
        if resultado == "CRIAR":
            objeto = Nutriente(
                codigo=item["codigo"], nome=item["nome"], unidade=item["unidade"]
            )
            db.add(objeto)
            nutrientes[item["codigo"]] = objeto
        elif resultado == "ATUALIZAR":
            objeto = nutrientes[item["codigo"]]
            if item["nome"] is not None:
                objeto.nome = item["nome"]
            if item["unidade"] is not None:
                objeto.unidade = item["unidade"]
    db.flush()

    codigos_mp = {
        item["codigo"] for item in dados["MATERIAS_PRIMAS"]
    } | {
        item["materia_prima_codigo"]
        for aba in (
            "COMPOSICAO_NUTRICIONAL", "PRECOS_MP",
            "COMPOSICAO_COMPONENTES_MP", "REGRAS_REGULATORIAS_MP",
        )
        for item in dados[aba]
    }
    mps = _mapa_codigos(db, MateriaPrima, codigos_mp)
    for item in sorted(dados["MATERIAS_PRIMAS"], key=lambda valor: (valor["codigo"], valor["linha"])):
        resultado = resultados.get(("MATERIAS_PRIMAS", item["linha"]))
        if resultado == "CRIAR":
            objeto = MateriaPrima(
                codigo=item["codigo"], nome=item["nome"], ativa=item["ativa"]
            )
            db.add(objeto)
            mps[item["codigo"]] = objeto
        elif resultado == "ATUALIZAR":
            objeto = mps[item["codigo"]]
            if item["nome"] is not None:
                objeto.nome = item["nome"]
            if item["ativa"] is not None:
                objeto.ativa = item["ativa"]
    db.flush()
    return nutrientes, mps


def _aplicar_catalogos_regulatorios(db, dados, resultados):
    categorias = _mapa_codigos(
        db, CategoriaProduto,
        (
            item.get("codigo") or item.get("categoria_codigo")
            for aba in ("CATEGORIAS_PRODUTO", *ABAS_REGRAS)
            for item in dados[aba]
        ),
    )
    for item in sorted(dados["CATEGORIAS_PRODUTO"], key=lambda valor: (valor["codigo"], valor["linha"])):
        resultado = resultados.get(("CATEGORIAS_PRODUTO", item["linha"]))
        if resultado == "CRIAR":
            objeto = CategoriaProduto(
                codigo=item["codigo"], nome=item["nome"],
                descricao=item["descricao"], ativa=True, revisao=1,
            )
            db.add(objeto)
            categorias[item["codigo"]] = objeto
        elif resultado == "ATUALIZAR":
            objeto = categorias[item["codigo"]]
            if item["nome"] is not None:
                objeto.nome = item["nome"]
            if item["descricao"] is not None:
                objeto.descricao = item["descricao"]
    db.flush()

    componentes = _mapa_codigos(
        db, ComponenteRegulatorio,
        (
            item.get("codigo") or item.get("componente_codigo")
            for aba in (
                "COMPONENTES_REGULATORIOS", "COMPOSICAO_COMPONENTES_MP",
                "REGRAS_REGULATORIAS_COMPONENTE",
            )
            for item in dados[aba]
        ),
    )
    for item in sorted(dados["COMPONENTES_REGULATORIOS"], key=lambda valor: (valor["codigo"], valor["linha"])):
        resultado = resultados.get(("COMPONENTES_REGULATORIOS", item["linha"]))
        if resultado == "CRIAR":
            objeto = ComponenteRegulatorio(
                codigo=item["codigo"], nome=item["nome"],
                descricao=item["descricao"], unidade="%", base="MASSA_MASSA",
                ativo=True,
            )
            db.add(objeto)
            componentes[item["codigo"]] = objeto
        elif resultado == "ATUALIZAR":
            objeto = componentes[item["codigo"]]
            if item["nome"] is not None:
                objeto.nome = item["nome"]
            if item["descricao"] is not None:
                objeto.descricao = item["descricao"]
    db.flush()
    return categorias, componentes


def _aplicar_composicao_nutricional(db, dados, resultados, mps, nutrientes):
    chaves = {
        (mps[item["materia_prima_codigo"]].id, nutrientes[item["nutriente_codigo"]].id)
        for item in dados["COMPOSICAO_NUTRICIONAL"]
        if item["materia_prima_codigo"] in mps and item["nutriente_codigo"] in nutrientes
    }
    existentes = {}
    if chaves:
        mp_ids = {chave[0] for chave in chaves}
        nutriente_ids = {chave[1] for chave in chaves}
        objetos = db.scalars(select(ComposicaoMateriaPrima).where(
            ComposicaoMateriaPrima.materia_prima_id.in_(mp_ids),
            ComposicaoMateriaPrima.nutriente_id.in_(nutriente_ids),
        )).all()
        existentes = {
            (objeto.materia_prima_id, objeto.nutriente_id): objeto
            for objeto in objetos
        }
    for item in sorted(
        dados["COMPOSICAO_NUTRICIONAL"],
        key=lambda valor: (valor["materia_prima_codigo"], valor["nutriente_codigo"], valor["linha"]),
    ):
        resultado = resultados.get(("COMPOSICAO_NUTRICIONAL", item["linha"]))
        chave = (
            mps[item["materia_prima_codigo"]].id,
            nutrientes[item["nutriente_codigo"]].id,
        )
        if resultado == "CRIAR":
            db.add(ComposicaoMateriaPrima(
                materia_prima_id=chave[0], nutriente_id=chave[1],
                valor=Decimal(item["valor"]),
            ))
        elif resultado == "ATUALIZAR":
            existentes[chave].valor = Decimal(item["valor"])
    db.flush()


def _aplicar_precos(db, dados, resultados, mps):
    for item in sorted(
        dados["PRECOS_MP"],
        key=lambda valor: (valor["materia_prima_codigo"], valor["vigencia_inicio"], valor["linha"]),
    ):
        if resultados.get(("PRECOS_MP", item["linha"])) == "CRIAR":
            db.add(PrecoMateriaPrima(
                materia_prima_id=mps[item["materia_prima_codigo"]].id,
                preco_kg=Decimal(item["preco_kg"]),
                vigencia_inicio=date.fromisoformat(item["vigencia_inicio"]),
                vigencia_fim=_data(item["vigencia_fim"]),
            ))
    db.flush()


def _aplicar_composicoes_regulatorias(
    db, dados, resultados, mps, componentes,
):
    itens = dados["COMPOSICAO_COMPONENTES_MP"]
    chaves = {
        (
            mps[item["materia_prima_codigo"]].id,
            componentes[item["componente_codigo"]].id,
            date.fromisoformat(item["data_referencia"]),
        )
        for item in itens
    }
    existentes = {}
    if chaves:
        mp_ids = {chave[0] for chave in chaves}
        componente_ids = {chave[1] for chave in chaves}
        objetos = db.scalars(select(ComposicaoComponenteMP).where(
            ComposicaoComponenteMP.materia_prima_id.in_(mp_ids),
            ComposicaoComponenteMP.componente_id.in_(componente_ids),
        ).order_by(ComposicaoComponenteMP.id)).all()
        existentes = {
            (objeto.materia_prima_id, objeto.componente_id, objeto.data_referencia): objeto
            for objeto in objetos
        }
    for item in sorted(
        itens,
        key=lambda valor: (
            valor["materia_prima_codigo"], valor["componente_codigo"],
            valor["data_referencia"], valor["linha"],
        ),
    ):
        resultado = resultados.get(("COMPOSICAO_COMPONENTES_MP", item["linha"]))
        chave = (
            mps[item["materia_prima_codigo"]].id,
            componentes[item["componente_codigo"]].id,
            date.fromisoformat(item["data_referencia"]),
        )
        if resultado == "CRIAR":
            db.add(ComposicaoComponenteMP(
                materia_prima_id=chave[0], componente_id=chave[1],
                data_referencia=chave[2], situacao=item["situacao"],
                concentracao=_decimal(item["concentracao"]),
                fonte=item["fonte"], observacao=item["observacao"], ativo=True,
            ))
        elif resultado == "DESATIVAR":
            existentes[chave].ativo = False
    db.flush()


def _identidade_regra(item, categorias, mps, componentes):
    tipo = item["tipo_alvo"]
    alvo = (
        mps[item["materia_prima_codigo"]]
        if tipo == "MATERIA_PRIMA"
        else componentes[item["componente_codigo"]]
    )
    return (
        categorias[item["categoria_codigo"]].id,
        tipo,
        alvo.id,
        _data(item["vigencia_inicio"]),
        _data(item["vigencia_fim"]),
    )


def _nova_regra(item, categorias, mps, componentes, anterior=None):
    tipo = item["tipo_alvo"]
    alvo = (
        mps[item["materia_prima_codigo"]]
        if tipo == "MATERIA_PRIMA"
        else componentes[item["componente_codigo"]]
    )
    return RegraRegulatoria(
        categoria_id=categorias[item["categoria_codigo"]].id,
        tipo_alvo=tipo,
        materia_prima_id=alvo.id if tipo == "MATERIA_PRIMA" else None,
        componente_id=alvo.id if tipo == "COMPONENTE" else None,
        tratamento=item["tratamento"],
        minimo=_decimal(item["minimo"]), maximo=_decimal(item["maximo"]),
        unidade="%", base="MASSA_MASSA",
        justificativa=item["justificativa"],
        referencia_normativa=item["referencia_normativa"],
        revisao=anterior.revisao + 1 if anterior else 1,
        regra_anterior_id=anterior.id if anterior else None,
        ativa=True,
        vigencia_inicio=_data(item["vigencia_inicio"]),
        vigencia_fim=_data(item["vigencia_fim"]),
    )


def _aplicar_regras(db, dados, resultados, categorias, mps, componentes):
    linhas = [
        (aba, item)
        for aba in ABAS_REGRAS
        for item in dados[aba]
    ]
    identidades = [
        _identidade_regra(item, categorias, mps, componentes)
        for aba, item in linhas
        if resultados.get((aba, item["linha"])) in {"ATUALIZAR", "DESATIVAR"}
    ]
    regras = []
    if identidades:
        categoria_ids = {item[0] for item in identidades}
        mp_ids = {item[2] for item in identidades if item[1] == "MATERIA_PRIMA"}
        componente_ids = {item[2] for item in identidades if item[1] == "COMPONENTE"}
        filtros = []
        if mp_ids:
            filtros.append(
                (RegraRegulatoria.tipo_alvo == "MATERIA_PRIMA")
                & RegraRegulatoria.materia_prima_id.in_(mp_ids)
            )
        if componente_ids:
            filtros.append(
                (RegraRegulatoria.tipo_alvo == "COMPONENTE")
                & RegraRegulatoria.componente_id.in_(componente_ids)
            )
        regras = list(db.scalars(select(RegraRegulatoria).where(
            RegraRegulatoria.categoria_id.in_(categoria_ids),
            or_(*filtros),
        ).order_by(RegraRegulatoria.id)).all())
    por_identidade = {}
    for regra in regras:
        alvo_id = (
            regra.materia_prima_id
            if regra.tipo_alvo == "MATERIA_PRIMA"
            else regra.componente_id
        )
        chave = (
            regra.categoria_id, regra.tipo_alvo, alvo_id,
            regra.vigencia_inicio, regra.vigencia_fim,
        )
        por_identidade.setdefault(chave, []).append(regra)

    sucessoras = []
    for aba, item in linhas:
        resultado = resultados.get((aba, item["linha"]))
        if resultado not in {"ATUALIZAR", "DESATIVAR"}:
            continue
        identidade = _identidade_regra(item, categorias, mps, componentes)
        ativas = [regra for regra in por_identidade.get(identidade, ()) if regra.ativa]
        if len(ativas) != 1:
            raise RuntimeError("Regra ativa revalidada não foi localizada de forma unívoca.")
        anterior = ativas[0]
        anterior.ativa = False
        if resultado == "ATUALIZAR":
            sucessoras.append((item, anterior))
    db.flush()

    for item, anterior in sucessoras:
        db.add(_nova_regra(item, categorias, mps, componentes, anterior))
    for aba, item in linhas:
        if resultados.get((aba, item["linha"])) == "CRIAR":
            db.add(_nova_regra(item, categorias, mps, componentes))
    db.flush()


def aplicar_importacao_regulatoria(db, dados, operacoes):
    resultados = _resultados(operacoes)
    nutrientes, mps = _aplicar_catalogos_base(db, dados, resultados)
    categorias, componentes = _aplicar_catalogos_regulatorios(
        db, dados, resultados
    )
    _aplicar_composicao_nutricional(
        db, dados, resultados, mps, nutrientes
    )
    _aplicar_precos(db, dados, resultados, mps)
    _aplicar_composicoes_regulatorias(
        db, dados, resultados, mps, componentes
    )
    _aplicar_regras(
        db, dados, resultados, categorias, mps, componentes
    )

    for item in dados["COMPONENTES_REGULATORIOS"]:
        if resultados.get(("COMPONENTES_REGULATORIOS", item["linha"])) == "DESATIVAR":
            componentes[item["codigo"]].ativo = False
    for item in dados["CATEGORIAS_PRODUTO"]:
        if resultados.get(("CATEGORIAS_PRODUTO", item["linha"])) == "DESATIVAR":
            categorias[item["codigo"]].ativa = False
    for item in dados["MATERIAS_PRIMAS"]:
        if resultados.get(("MATERIAS_PRIMAS", item["linha"])) == "DESATIVAR":
            mps[item["codigo"]].ativa = False
    db.flush()
