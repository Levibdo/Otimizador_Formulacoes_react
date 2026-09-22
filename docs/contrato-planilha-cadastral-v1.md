# Contrato da planilha cadastral 1.0

Este contrato cobre apenas a leitura e a validação estrutural de arquivos `.xlsx`.
O parser não consulta nem altera o PostgreSQL, não executa `commit` e não infere
operações. O importador legado de matérias-primas permanece disponível.

## Regras gerais

- versão do contrato: `1.0`;
- exatamente cinco abas: `LEIA_ME`, `MATERIAS_PRIMAS`, `NUTRIENTES`,
  `COMPOSICAO_NUTRICIONAL` e `PRECOS_MP`;
- o conjunto geral de ações é `CRIAR`, `ATUALIZAR` e `DESATIVAR`, limitado por aba conforme a tabela abaixo;
- cada linha de dados deve declarar sua ação;
- códigos são identificadores estáveis, não são gerados e não podem ser alterados;
- códigos começam por letra e contêm somente letras, números e `_`, com até 30 caracteres;
- células vazias em atualizações significam “não alterar” e nunca apagam dados;
- a ausência de uma composição no arquivo não solicita sua remoção;
- preços são novos períodos históricos, portanto `PRECOS_MP` aceita somente `CRIAR`;
- datas textuais usam exclusivamente ISO `AAAA-MM-DD`;
- booleanos aceitam exclusivamente os textos `SIM` e `NÃO`;
- códigos devem ser células de texto, preservam zeros e são normalizados para maiúsculas;
- decimais são normalizados como texto decimal, sem conversão para ponto flutuante pelo parser;
- fórmulas não são aceitas em nenhuma célula.

## Abas e colunas

| Aba | Colunas obrigatórias | Ações seguras | Chave de duplicidade no arquivo |
| --- | --- | --- | --- |
| `LEIA_ME` | `CHAVE`, `VALOR` | Não se aplica | `CHAVE` |
| `MATERIAS_PRIMAS` | `ACAO`, `CODIGO`, `NOME`, `ATIVA` | `CRIAR`, `ATUALIZAR`, `DESATIVAR` | `CODIGO` |
| `NUTRIENTES` | `ACAO`, `CODIGO`, `NOME`, `UNIDADE` | `CRIAR`, `ATUALIZAR` | `CODIGO` |
| `COMPOSICAO_NUTRICIONAL` | `ACAO`, `MATERIA_PRIMA_CODIGO`, `NUTRIENTE_CODIGO`, `VALOR` | `CRIAR`, `ATUALIZAR` | MP + nutriente |
| `PRECOS_MP` | `ACAO`, `MATERIA_PRIMA_CODIGO`, `PRECO_KG`, `VIGENCIA_INICIO`, `VIGENCIA_FIM` | `CRIAR` | MP + vigência inicial |

`LEIA_ME` deve possuir a chave `VERSAO_TEMPLATE` com valor textual `1.0`.
Cabeçalhos repetidos, ausentes ou desconhecidos invalidam a aba.

Em `MATERIAS_PRIMAS` e `NUTRIENTES`, `CRIAR` exige os campos cadastrais e
`ATUALIZAR` exige ao menos um campo mutável preenchido. Somente matérias-primas
aceitam `DESATIVAR`. Nutrientes não possuem estado ativo no schema atual.

Em `COMPOSICAO_NUTRICIONAL`, `CRIAR` e `ATUALIZAR` exigem valor não negativo.
Essa relação não possui estado ativo no schema atual, portanto `DESATIVAR` é
rejeitado. Uma composição que não apareça na planilha permanece inalterada.

Referências declaradas no próprio workbook são verificadas. Uma referência que
não consta nas abas cadastrais produz aviso, pois poderá apontar para um código
já existente no PostgreSQL; essa resolução pertence à futura pré-validação com o banco.

## Diagnósticos

Cada diagnóstico contém:

- `severidade`: `ERRO` ou `AVISO`;
- `aba`;
- `linha`;
- `coluna`;
- `codigo` relacionado;
- `mensagem` segura.

O resultado é válido apenas quando não possui diagnóstico de severidade `ERRO`.

## Limites de segurança

| Limite | Valor |
| --- | ---: |
| Arquivo compactado | 5 MiB |
| Conteúdo descomprimido | 30 MiB |
| Entradas internas no ZIP | 200 |
| Razão de compressão por entrada | 100:1 |
| Abas | 5 |
| Linhas por aba | 5.000 |
| Colunas por aba | 12 |
| Células no workbook | 100.000 |

Arquivos vazios, corrompidos, criptografados, com macros, caminhos internos
inválidos ou estrutura semelhante a ZIP bomb são rejeitados antes da leitura das
células.

## Template fictício

`GET /api/v1/importacoes-cadastrais/template` gera o template em memória. Os
exemplos usam somente códigos e nomes iniciados por `FICT_` ou explicitamente
descritos como fictícios. O download não consulta nem grava dados.
