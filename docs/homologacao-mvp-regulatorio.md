# Homologação técnica do MVP regulatório

## Objetivo e data

Esta homologação, executada em 20 de setembro de 2026, verificou o fluxo técnico
do MVP regulatório: cadastro, avaliação server-side, diagnóstico, otimização,
versionamento e preservação histórica. Ela não interpreta normas e não constitui
aprovação, certificação ou declaração de conformidade normativa.

## Ambiente

A execução utilizou somente o ambiente local de desenvolvimento criado pelo
Docker Compose do projeto:

- PostgreSQL 16 como fonte oficial;
- backend FastAPI com as migrações aplicadas até `20260919_07`;
- frontend React/Vite;
- solver PuLP/CBC;
- branch `main` limpa e sincronizada no início da homologação.

Nenhum banco externo ou ambiente de produção foi acessado. Registros existentes
não foram apagados nem atualizados. A carga adicionou cadastros com prefixo
`HOMOLOG_`; a única mudança posterior foi uma nova vigência de preço para uma
matéria-prima criada pela própria homologação.

## Dados fictícios

Todos os nomes, preços, composições, requisitos e regras deste relatório são
fictícios e destinados exclusivamente à homologação técnica. Os textos de
observação e justificativa registram explicitamente essa finalidade.

A categoria preexistente `FORMULA_ENTERAL_PO` foi reutilizada sem alteração. A
carga criou os seguintes códigos:

- `HOMOLOG_MP_CARBO`;
- `HOMOLOG_MP_PROT`;
- `HOMOLOG_MP_LACTEA`;
- `HOMOLOG_MP_DESCONH`;
- `HOMOLOG_MP_SEM_REGRA`;
- `HOMOLOG_PROTEINA`;
- `HOMOLOG_CARBOIDRATO`;
- `HOMOLOG_LACTOSE`;
- `HOMOLOG_PROJ_ENTERAL`.

O projeto recebeu requisitos mínimos fictícios de 20 g/100 g de proteína e
40 g/100 g de carboidrato, além de teto de custo de R$ 25/kg. Foram cadastradas
quatro classificações individuais de matéria-prima e um limite agregado fictício
de 3% m/m para lactose. `HOMOLOG_MP_SEM_REGRA` permaneceu intencionalmente sem
classificação individual.

As concentrações de lactose cobriram os três estados do cadastro: ausência
confirmada com zero explícito, valor informado de 12% m/m e concentração
desconhecida mantida nula.

## Cenários e resultados

Os IDs abaixo pertencem exclusivamente ao banco local usado nesta execução. Eles
são referências de auditoria da sessão e não são reproduzíveis em outra carga.

| Cenário | Entrada principal | Resultado esperado | Resultado observado | Referência local |
| --- | --- | --- | --- | --- |
| Solução viável | MPs de carboidrato, proteína e ingrediente lácteo | Solução ótima, classificada e dentro dos limites | `Optimal`, `ATENDE`, custo R$ 15/kg; inclusões 75%, 25% e 0%; sem alertas ou pendências | execução 6 |
| MP sem classificação | MPs de carboidrato, proteína e `HOMOLOG_MP_SEM_REGRA` | Solução permitida com alerta explícito | `Optimal`, `ATENDE_COM_ALERTAS`, custo R$ 14,275/kg; alerta para a MP sem classificação | execução 7 |
| Componente desconhecido | Inclusão de `HOMOLOG_MP_DESCONH` entre as candidatas | Avaliação inconclusiva sem presumir zero | `INCONCLUSIVA`; solver não executado; custo e inclusões ausentes; pendência de lactose desconhecida | execução 8 |
| Limite agregado de lactose | Ingrediente lácteo fixado em 25% e concentração de lactose em 12% | Soma agregada igual ao teto de 3% m/m | `Optimal`, `ATENDE`, custo R$ 15,4375/kg; lactose agregada de 3% m/m | execução 9 |
| Restrições conflitantes | Mínimos técnicos de 60% e 50% para duas MPs | Rejeição antes do solver porque a soma supera 100% | `INVIAVEL`; solver não executado; diagnóstico da soma dos mínimos | execução 10 |
| Criação de versão | Execução viável usada como única origem | Versão criada pelo `execucao_id` e com snapshot server-side | Versão 1 criada com `Optimal`, custo R$ 15/kg e inclusões históricas | execução 6, versão local 6 |
| Alteração de preço | Nova vigência de R$ 22/kg para `HOMOLOG_MP_CARBO` | Nova execução usa o preço vigente sem alterar a anterior | `Optimal`, `ATENDE`, custo R$ 24/kg; inclusões de 75% e 25% | execução 11 |
| Preservação dos snapshots | Comparação da execução e da versão antes e depois da nova vigência | Histórico permanece com preço, custo e resultado originais | Execução e versão conservaram preço de R$ 10/kg e custo de R$ 15/kg | execução 6, versão local 6 |

Todos os oito cenários apresentaram o comportamento técnico esperado.

## Pontos verificados

### Limite agregado de lactose

No cenário agregado, `HOMOLOG_MP_LACTEA` foi fixada em 25% da fórmula e possuía
concentração informada de 12% m/m de lactose. A contribuição calculada foi:

```text
25% de inclusão × 12% de concentração ÷ 100 = 3% m/m na fórmula
```

O resultado atingiu exatamente o máximo fictício cadastrado e permaneceu viável.
Isso verificou que o limite se aplica à soma da substância na fórmula, e não
diretamente ao percentual de uma matéria-prima comercial.

### Matéria-prima não classificada

A MP sem regra individual participou da solução. O solver retornou solução ótima,
e a avaliação foi `ATENDE_COM_ALERTAS`, com mensagem que identificou o código da
MP não classificada. O cadastro ausente não foi tratado como proibição.

### Concentração desconhecida

A concentração desconhecida permaneceu nula. Quando essa MP participou das
candidatas de uma regra de componente, a avaliação ficou `INCONCLUSIVA`, com uma
pendência explícita. O motor não substituiu o valor desconhecido por zero e não
executou o solver com informação incompleta.

### Conflito de mínimos

Dois limites técnicos, de 60% e 50%, produziram soma mínima de 110%. O motor
classificou a execução como `INVIAVEL` antes de chamar o solver e registrou a
causa específica no diagnóstico.

### Alteração de preço e snapshots

A execução original utilizou o preço fictício de R$ 10/kg para
`HOMOLOG_MP_CARBO`. Uma nova vigência de R$ 22/kg foi adicionada depois da criação
da versão. A execução posterior usou o novo preço, enquanto a execução e a versão
anteriores mantiveram o preço de R$ 10/kg, o custo de R$ 15/kg, as inclusões, os
requisitos e a matriz histórica.

A comparação inicial da resposta de criação com a releitura integral da versão
detectou diferença de representação serializada. A verificação semântica dos
campos monetários, inclusões, vínculo com a execução, requisitos e matriz mostrou
que não houve alteração de conteúdo. Essa diferença é compatível com a
serialização de valores `NUMERIC`, que pode apresentar escala textual diferente
na releitura.

## Limitações

- A homologação usou um único ambiente local e uma carga controlada.
- Os valores e regras são fictícios e não validam requisitos legais ou normas.
- Não foram avaliadas regras reais, conversões por porção, 100 mL ou 100 kcal.
- Não houve ensaio de carga, segurança ofensiva ou concorrência em escala.
- Os IDs locais variam entre bancos e não devem ser usados como identificadores
  reproduzíveis.
- A autenticação ainda não faz parte deste MVP e deverá ser definida antes de uma
  implantação compartilhada.
- Proprietários e superusuários do PostgreSQL conservam poderes administrativos,
  inclusive para desabilitar triggers.

## Conclusão técnica

O MVP apresentou o comportamento esperado para cadastros regulatórios manuais,
limites individuais e agregados, dados desconhecidos, alertas, inviabilidade,
alteração de preços e versionamento imutável. A homologação confirma a coerência
técnica do fluxo implementado com dados fictícios; regras reais e validação
normativa permanecem fora do escopo e dependem de definição especializada.
