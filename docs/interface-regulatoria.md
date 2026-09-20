# Interface do MVP regulatório

A aba **Regulatório** mantém os cadastros manuais de categorias, componentes, composições por matéria-prima e regras. Os formulários respeitam a distinção entre concentração informada, ausência confirmada com zero explícito e concentração desconhecida. Registros históricos são revisados ou desativados, sem exclusão física.

Projetos podem ser vinculados a uma categoria. O vínculo continua opcional e nenhum projeto histórico recebe categoria automaticamente. A categoria piloto aparece pelo código estável `FORMULA_ENTERAL_PO`.

## Modos de otimização

**Otimização do projeto** é o modo recomendado. O navegador envia somente o projeto, as MPs candidatas, limites técnicos adicionais e a data de referência para `POST /api/v1/projetos/{id}/otimizacoes`. Preços, matriz, composições e regras são obtidos pelo servidor no PostgreSQL. O resultado mostra solver, estado regulatório, execução, custo, fórmula, composição, regras, limites, alertas, pendências e diagnóstico.

Uma execução apta pode gerar versão exclusivamente por `execucao_id`. A interface não reconstrói o snapshot e mantém o projeto da execução bloqueado no formulário de salvamento.

**Simulação manual legada** preserva o contrato `/optimize` usado anteriormente. A tela informa explicitamente que esse modo não realiza avaliação regulatória. O salvamento legado continua enviando o resultado completo enquanto a migração da interface não for concluída em todos os fluxos.

## Linguagem e acessibilidade

Os estados usam mensagens textuais e não dependem apenas de cor. Formulários possuem labels, botões mantêm foco nativo e a navegação principal aceita teclado. Grades passam para uma coluna em larguras menores e mantêm tabelas com rolagem horizontal em notebook.

As mensagens da API são apresentadas sem stack traces ou objetos brutos. Indisponibilidade da API recebe mensagem própria e os campos preenchidos permanecem na tela após falhas.

Esta interface aplica apenas regras cadastradas manualmente. Não interpreta normas, não faz certificação e não suporta bases por porção, 100 mL ou 100 kcal.
