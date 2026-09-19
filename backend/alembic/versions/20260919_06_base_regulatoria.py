"""Base cadastral regulatória híbrida: MPs comerciais e componentes agregados."""
from alembic import op
import sqlalchemy as sa

revision = '20260919_06'
down_revision = '20260919_05'
branch_labels = None
depends_on = None


def datas():
    return [
        sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('atualizado_em', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]


def upgrade():
    op.create_table('categorias_produto',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('codigo', sa.String(50), nullable=False, unique=True),
        sa.Column('nome', sa.String(200), nullable=False),
        sa.Column('descricao', sa.Text()),
        sa.Column('ativa', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('revisao', sa.Integer(), nullable=False, server_default='1'),
        *datas(),
        sa.CheckConstraint('revisao > 0', name='ck_categoria_revisao'),
        sa.CheckConstraint("codigo ~ '^[A-Z][A-Z0-9_]*$'", name='ck_categoria_codigo'),
        sa.CheckConstraint("length(trim(nome)) > 0", name='ck_categoria_nome'),
    )
    op.create_table('componentes_regulatorios',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('codigo', sa.String(50), nullable=False, unique=True),
        sa.Column('nome', sa.String(200), nullable=False),
        sa.Column('descricao', sa.Text()),
        sa.Column('unidade', sa.String(10), nullable=False, server_default='%'),
        sa.Column('base', sa.String(30), nullable=False, server_default='MASSA_MASSA'),
        sa.Column('ativo', sa.Boolean(), nullable=False, server_default=sa.true()),
        *datas(),
        sa.CheckConstraint("unidade = '%' AND base = 'MASSA_MASSA'", name='ck_componente_base'),
        sa.CheckConstraint("codigo ~ '^[A-Z][A-Z0-9_]*$'", name='ck_componente_codigo'),
        sa.CheckConstraint("length(trim(nome)) > 0", name='ck_componente_nome'),
    )
    op.create_table('composicoes_componentes_mp',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('materia_prima_id', sa.Integer(), sa.ForeignKey('materias_primas.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('componente_id', sa.Integer(), sa.ForeignKey('componentes_regulatorios.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('concentracao', sa.Numeric(18, 6)),
        sa.Column('situacao', sa.String(30), nullable=False),
        sa.Column('fonte', sa.Text()),
        sa.Column('observacao', sa.Text()),
        sa.Column('data_referencia', sa.Date(), nullable=False),
        sa.Column('ativo', sa.Boolean(), nullable=False, server_default=sa.true()),
        *datas(),
        sa.UniqueConstraint('materia_prima_id', 'componente_id', 'data_referencia', name='uq_componente_mp_data'),
        sa.CheckConstraint('concentracao IS NULL OR (concentracao >= 0 AND concentracao <= 100)', name='ck_concentracao_percentual'),
        sa.CheckConstraint("(situacao = 'INFORMADO' AND concentracao IS NOT NULL) OR (situacao = 'AUSENTE_CONFIRMADO' AND concentracao IS NOT NULL AND concentracao = 0) OR (situacao = 'DESCONHECIDO' AND concentracao IS NULL)", name='ck_concentracao_situacao'),
    )
    op.create_table('regras_regulatorias',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('categoria_id', sa.Integer(), sa.ForeignKey('categorias_produto.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('tipo_alvo', sa.String(20), nullable=False),
        sa.Column('materia_prima_id', sa.Integer(), sa.ForeignKey('materias_primas.id', ondelete='RESTRICT')),
        sa.Column('componente_id', sa.Integer(), sa.ForeignKey('componentes_regulatorios.id', ondelete='RESTRICT')),
        sa.Column('tratamento', sa.String(20), nullable=False),
        sa.Column('minimo', sa.Numeric(18, 6)),
        sa.Column('maximo', sa.Numeric(18, 6)),
        sa.Column('unidade', sa.String(10), nullable=False, server_default='%'),
        sa.Column('base', sa.String(30), nullable=False, server_default='MASSA_MASSA'),
        sa.Column('justificativa', sa.Text(), nullable=False),
        sa.Column('referencia_normativa', sa.Text()),
        sa.Column('revisao', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('regra_anterior_id', sa.Integer(), sa.ForeignKey('regras_regulatorias.id', ondelete='RESTRICT'), unique=True),
        sa.Column('ativa', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('vigencia_inicio', sa.Date()),
        sa.Column('vigencia_fim', sa.Date()),
        *datas(),
        sa.CheckConstraint("(tipo_alvo = 'MATERIA_PRIMA' AND materia_prima_id IS NOT NULL AND componente_id IS NULL) OR (tipo_alvo = 'COMPONENTE' AND componente_id IS NOT NULL AND materia_prima_id IS NULL)", name='ck_regra_alvo'),
        sa.CheckConstraint("tratamento IN ('PERMITIDA', 'PROIBIDA', 'OBRIGATORIA', 'LIMITADA')", name='ck_regra_tratamento'),
        sa.CheckConstraint('minimo IS NULL OR (minimo >= 0 AND minimo <= 100)', name='ck_regra_minimo'),
        sa.CheckConstraint('maximo IS NULL OR (maximo >= 0 AND maximo <= 100)', name='ck_regra_maximo'),
        sa.CheckConstraint('minimo IS NULL OR maximo IS NULL OR minimo <= maximo', name='ck_regra_limites'),
        sa.CheckConstraint("tratamento != 'OBRIGATORIA' OR (minimo IS NOT NULL AND minimo > 0)", name='ck_regra_obrigatoria'),
        sa.CheckConstraint("tratamento != 'PROIBIDA' OR (maximo IS NOT NULL AND maximo = 0 AND (minimo IS NULL OR minimo = 0))", name='ck_regra_proibida'),
        sa.CheckConstraint("tratamento != 'LIMITADA' OR minimo IS NOT NULL OR maximo IS NOT NULL", name='ck_regra_limitada'),
        sa.CheckConstraint("unidade = '%' AND base = 'MASSA_MASSA'", name='ck_regra_base'),
        sa.CheckConstraint('vigencia_inicio IS NULL OR vigencia_fim IS NULL OR vigencia_fim >= vigencia_inicio', name='ck_regra_vigencia'),
        sa.CheckConstraint('revisao > 0', name='ck_regra_revisao'),
        sa.CheckConstraint("length(trim(justificativa)) > 0", name='ck_regra_justificativa'),
    )
    op.create_index('ix_regras_regulatorias_categoria_id', 'regras_regulatorias', ['categoria_id'])
    # Range types já possuem operadores GiST; não exige extensão btree_gist.
    for alvo in ('materia_prima_id', 'componente_id'):
        op.execute(f"""
            ALTER TABLE regras_regulatorias ADD CONSTRAINT ex_regra_{alvo}_vigencia
            EXCLUDE USING gist (
                int8range(categoria_id, categoria_id, '[]') WITH =,
                int8range({alvo}, {alvo}, '[]') WITH =,
                daterange(vigencia_inicio, vigencia_fim, '[]') WITH &&
            ) WHERE (ativa AND {alvo} IS NOT NULL)
        """)
    op.add_column('projetos', sa.Column('categoria_produto_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_projeto_categoria_produto', 'projetos', 'categorias_produto', ['categoria_produto_id'], ['id'], ondelete='RESTRICT')
    op.create_index('ix_projetos_categoria_produto_id', 'projetos', ['categoria_produto_id'])

    op.execute("""
        CREATE FUNCTION proteger_cadastro_regulatorio() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'Cadastro regulatório não pode ser apagado; desative ou revise o registro.' USING ERRCODE = '23514';
            END IF;
            IF NEW.id IS DISTINCT FROM OLD.id OR NEW.criado_em IS DISTINCT FROM OLD.criado_em THEN
                RAISE EXCEPTION 'Identificação e criação do cadastro são estáveis.' USING ERRCODE = '23514';
            END IF;
            IF TG_TABLE_NAME IN ('categorias_produto', 'componentes_regulatorios') THEN
                IF NEW.codigo IS DISTINCT FROM OLD.codigo THEN
                    RAISE EXCEPTION 'Código regulatório é estável e não pode ser alterado.' USING ERRCODE = '23514';
                END IF;
                IF TG_TABLE_NAME = 'categorias_produto' THEN
                    NEW.revisao := OLD.revisao + 1;
                END IF;
            ELSE
                IF (to_jsonb(NEW) - ARRAY['ativa', 'ativo', 'atualizado_em']) IS DISTINCT FROM
                   (to_jsonb(OLD) - ARRAY['ativa', 'ativo', 'atualizado_em']) THEN
                    RAISE EXCEPTION 'Conteúdo histórico não pode ser alterado; crie uma revisão ou nova data de referência.' USING ERRCODE = '23514';
                END IF;
            END IF;
            NEW.atualizado_em := clock_timestamp();
            RETURN NEW;
        END $$
    """)
    for tabela in ('categorias_produto', 'componentes_regulatorios', 'composicoes_componentes_mp', 'regras_regulatorias'):
        op.execute(f'CREATE TRIGGER trg_{tabela}_historico BEFORE UPDATE OR DELETE ON {tabela} FOR EACH ROW EXECUTE FUNCTION proteger_cadastro_regulatorio()')
    op.execute("""
        CREATE FUNCTION atualizar_revisao_categoria_regulatoria() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            UPDATE categorias_produto SET atualizado_em = clock_timestamp() WHERE id = NEW.categoria_id;
            RETURN NEW;
        END $$
    """)
    op.execute('CREATE TRIGGER trg_regra_revisao_categoria AFTER INSERT OR UPDATE ON regras_regulatorias FOR EACH ROW EXECUTE FUNCTION atualizar_revisao_categoria_regulatoria()')
    op.execute("INSERT INTO categorias_produto (codigo, nome, descricao) VALUES ('FORMULA_ENTERAL_PO', 'Fórmula enteral em pó', 'Categoria piloto do cadastro manual; sem certificação normativa automática.')")


def downgrade():
    op.drop_index('ix_projetos_categoria_produto_id', table_name='projetos')
    op.drop_constraint('fk_projeto_categoria_produto', 'projetos', type_='foreignkey')
    op.drop_column('projetos', 'categoria_produto_id')
    op.execute('DROP TRIGGER trg_regra_revisao_categoria ON regras_regulatorias')
    op.execute('DROP FUNCTION atualizar_revisao_categoria_regulatoria()')
    for tabela in ('regras_regulatorias', 'composicoes_componentes_mp', 'componentes_regulatorios', 'categorias_produto'):
        op.drop_table(tabela)
    op.execute('DROP FUNCTION proteger_cadastro_regulatorio()')
