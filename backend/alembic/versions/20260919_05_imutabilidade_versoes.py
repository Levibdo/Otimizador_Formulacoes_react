"""Impede alteração e exclusão de versões e dos snapshots contidos na linha."""

from alembic import op


revision = "20260919_05"
down_revision = "20260918_04"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE FUNCTION impedir_mutacao_versao_formula()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION USING
                ERRCODE = '23514',
                MESSAGE = 'Versões de fórmula são imutáveis: UPDATE e DELETE não são permitidos.',
                HINT = 'Crie uma nova versão; para retirar um projeto de uso, arquive-o.';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_versoes_formulas_imutaveis
        BEFORE UPDATE OR DELETE ON versoes_formulas
        FOR EACH ROW EXECUTE FUNCTION impedir_mutacao_versao_formula()
    """)


def downgrade():
    op.execute("DROP TRIGGER trg_versoes_formulas_imutaveis ON versoes_formulas")
    op.execute("DROP FUNCTION impedir_mutacao_versao_formula()")
