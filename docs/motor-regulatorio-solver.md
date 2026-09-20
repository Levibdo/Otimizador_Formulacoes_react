# Motor regulatório server-side

O fluxo regulatório do MVP usa exclusivamente dados lidos do PostgreSQL. O cliente escolhe matérias-primas candidatas, uma data de referência e limites técnicos mais rigorosos; preços, composição nutricional, concentrações e regras não podem substituir o cadastro oficial.

## Fluxo

`POST /api/v1/projetos/{id}/otimizacoes` carrega projeto, categoria, requisitos, matérias-primas ativas, preços vigentes, composição e regras ativas. O servidor combina requisitos técnicos e regras, executa diagnósticos prévios, chama o solver e persiste uma execução imutável. `GET /api/v1/otimizacoes/{id}` devolve o snapshot integral.

As execuções registram a versão `regulatorio-1.0`, escolhas recebidas, IDs, códigos e nomes, preços e vigências, composições, concentrações regulatórias, revisão das regras, limites efetivos, requisitos, alertas, pendências e resultado anterior ao arredondamento de apresentação. A API não oferece atualização ou exclusão, e uma trigger PostgreSQL bloqueia `UPDATE` e `DELETE` diretos.

## Restrições

- `NUTRIENTE` vira mínimo e/ou máximo na composição; item e unidade precisam coincidir com o cadastro.
- `MP` vira mínimo e/ou máximo de inclusão em `%`.
- `CUSTO` aceita somente teto em `R$/kg`; mínimo gera erro explícito.
- `PROIBIDA` fixa máximo zero; `OBRIGATORIA`, `LIMITADA` e `PERMITIDA` aplicam os limites cadastrados.
- o mínimo efetivo é o maior mínimo, e o máximo efetivo é o menor máximo entre projeto, regra e escolha técnica.
- componentes usam a soma `inclusão da MP × concentração / 100` para todas as candidatas.

Concentração `AUSENTE_CONFIRMADO` com valor zero participa do cálculo. Registro `DESCONHECIDO` ou ausência de registro para uma candidata torna a avaliação `INCONCLUSIVA`; nenhuma concentração é presumida como zero. MP sem regra individual continua candidata e gera `ATENDE_COM_ALERTAS` quando há solução.

Os estados são `SEM_AVALIACAO_REGULATORIA`, `ATENDE`, `ATENDE_COM_ALERTAS`, `INCONCLUSIVA`, `INVIAVEL` e `ERRO_TECNICO`. Uma inviabilidade retornada pelo solver recebe diagnóstico genérico quando não existe evidência para atribuir causa específica.

## Versões e compatibilidade

`POST /api/v1/projetos/{id}/versoes` aceita `execucao_id`. O servidor valida que a execução pertence ao projeto, possui solução ótima e estado apto, e copia seus snapshots para a versão histórica.

O `/optimize` e a criação de versão com resultado completo enviado pelo cliente permanecem disponíveis temporariamente para a interface React atual. Esse caminho é legado, não usa os cadastros oficiais do motor regulatório e não expressa avaliação ou conformidade regulatória. A futura adaptação da interface deve executar a otimização vinculada ao projeto e guardar o `execucao_id` retornado.

As regras são manuais. O resultado representa apenas a aplicação matemática do cadastro disponível e não constitui interpretação normativa nem certificação automática de conformidade.
