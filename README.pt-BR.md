# YSAT-JEV

### You Sure About That? A variante com julgamento tipado.

**Um contraponto cujo veredito é calculado, não escrito.**

> 🇺🇸 Read this in [English](README.md) · Skill base: [YSAT](https://github.com/<seu-usuario>/ysat)

Meus caros, esta é a variante com decisões tipadas da [YSAT](https://github.com/<seu-usuario>/ysat).
A finalidade é idêntica: discordar de uma decisão, com evidência, antes dela ser tomada. Muda uma
camada só.

Na YSAT, o modelo lê o contexto e **escreve** o veredito. Aqui, o modelo não escreve veredito
nenhum. Ele responde **perguntas atômicas tipadas**, uma de cada vez, e o veredito é **composto em
código** a partir de coeficientes que você lê e altera.

```
Estado (o que está sendo decidido, evidência, lacunas)
        ↓
Perguntas atômicas tipadas    rollback sem ensaio? porta de mão única? evidência fina? ...
        ↓                     cada uma julgada isolada, com confiança calibrada
Composição em código          risk_index = 0.24*a + 0.20*b + 0.16*c + ...
        ↓
Travas                        cobertura, confiança, e uma barra MAIOR para concordar
        ↓
Veredito + trilha de auditoria   com hash do estado, então o mesmo estado dá sempre o mesmo veredito
```

## Por que isso importa

Então, meus bons: a skill base defende o veredito dela com regras escritas. Regra é seguida por um
modelo que também quer agradar. Empurre com força suficiente e a prosa cede.

Aqui a pressão não tem onde cair. O veredito é função pura do estado:

```
veredito = f(estado, coeficientes, limiares)
```

"A gente já decidiu isso", "o comitê aprovou", "a data é pública", "só me dá razão" não são campos do
estado. Não mudam nenhuma entrada, então o hash não muda, então o veredito não muda. Não porque o
modelo estava firme naquele dia. Por aritmética.

O README da skill base argumenta que a deriva rumo à concordância é determinística: dado um usuário
com uma posição e uma conversa comprida o bastante, o agente converge pra essa posição. Esta variante
pega esse mesmo determinismo e aponta pro outro lado. Bora.

## Três coisas que ela se recusa a fazer

| Falha | O que impede |
|---|---|
| **Concordar sob pressão** | O veredito é calculado a partir do estado, e pressão não é campo do estado |
| **Tratar silêncio como segurança** | Pergunta sem resposta vira abstenção. Nunca vira 0, que seria lido como "sem risco aqui" |
| **Concordar com evidência fina** | Concordar é travado mais forte que discordar: exige cobertura 0.80, enquanto discordar exige 0.60 |

A terceira é o invariante "concordância precisa ser justificada" escrito como desigualdade, e não
como instrução. Uma rodada que julgou pouco cai em `inconclusive`, nunca em tranquilização.

## Instalar

Segue a [especificação Agent Skills](https://agentskills.io/specification), então funciona em
qualquer agente compatível.

**Microsoft 365 Copilot (skills pessoais do Cowork)**

```
Documents/Cowork/skills/ysat-jev/
```

**Qualquer outro runtime compatível**

```bash
git clone https://github.com/<seu-usuario>/ysat-jev.git ~/.agent/skills/ysat-jev
```

Instalar esta e a YSAT base junto é o cenário previsto: a YSAT atende o pedido conversacional, esta
atende quando você diz "veredito tipado" ou "trilha de auditoria". A descrição de cada uma delega
para a outra, então elas não brigam pelo mesmo pedido.

## Rodar sem modelo nenhum

Comece por aqui. O stub responde o mesmo contrato HTTP com regras determinísticas, então você valida
o fluxo inteiro antes de baixar qualquer peso.

> **O stub valida o contrato. Ele não julga.** Ele casa palavra-chave sobre o estado serializado e é
> cego a negação: um estado dizendo "o rollback nunca foi ensaiado" pontua igual a um dizendo que
> foi. Isso foi medido, não suposto, veja o [BENCHMARK.md](BENCHMARK.md). Use o stub para provar o
> encanamento e as travas, e coloque um backend de verdade atrás do contrato antes de confiar em
> qualquer número.

```bash
python3 infra/openjev/stub_server.py --port 8099
python3 scripts/compose_verdict.py --state working/state.json --config config.yaml
```

```json
{
  "verdict": "would not do it this way",
  "reason": "risk index 0.66 is at or above 0.60",
  "risk_index": 0.658, "coverage": 1.0, "confidence": 0.606,
  "state_hash": "351649c9901b2e2f", "backend": "openjev", "stub": true
}
```

Deu certo? Maravilha. Toda resposta do stub vem marcada com `"stub": true`, e a marca viaja até a
trilha de auditoria: julgamento simulado nunca é confundido com julgamento real.

Para o modelo de verdade, veja [infra/openjev/README.md](infra/openjev/README.md).

## Usar

- "roda o veredito tipado nisso"
- "discorda dessa decisão com trilha de auditoria"
- "modo jev"
- "isso é reproduzível? julga de novo"

Para um contraponto rápido em conversa, use a YSAT base. Esta aqui custa mais passos e devolve um
artefato mais frio. Ela compensa quando o veredito vai ter que ser defendido ou repetido depois.

## Os quatro backends

Mesma interface, trocar um não muda uma linha.

| Backend | O que é | Estado sai? | Quando |
|---|---|---|---|
| `openjev` | openJev-verdict-2.0 local, Apache 2.0, cerca de 150M parâmetros | não | **o padrão** |
| `local` | modelo de linguagem servido, probabilidade por auto-consistência | não | já existe modelo rodando e você não quer subir outro serviço |
| `typesafe` | API hospedada da TypeSafe, modelo Jev | **sim** | só como árbitro de comparação, redigido por padrão, nunca dependência |
| `offline` | só regras determinísticas | não | rede de segurança e fallback automático |

## Personalizar

Meu bom, os knobs de apresentação são idênticos aos da skill base. O que importa aqui são os
coeficientes:

```yaml
coefficients:
  rollback_untested: 0.24
  one_way_door: 0.20
  evidence_thin: 0.16
  deadline_without_slack: 0.12
  no_named_owner: 0.10
  monitoring_blind: 0.08
  external_dependency: 0.06
  failed_precedent: 0.04
```

É aqui que entra a cicatriz da sua organização. Já se queimou com sistema sem dono? Sobe o
`no_named_owner`. Está sob auditoria? Sobe o `evidence_thin`. Um número, versionado no arquivo, e
toda rodada registra os coeficientes que usou.

Para criar suas próprias perguntas, edite [scripts/question_bank.py](scripts/question_bank.py) com
uma regra: escreva toda pergunta de forma que **1.0 signifique mais risco**, porque a composição é
soma ponderada simples e pergunta escrita como virtude inverte o índice em silêncio.

Referência completa: [references/customization.md](references/customization.md). O racional de
projeto: [docs/typed-decisions.md](docs/typed-decisions.md). O registro da decisão:
[docs/adr/ADR-0001-typed-verdict.md](docs/adr/ADR-0001-typed-verdict.md).

Repare no que não tem override em linha: limiar e coeficiente. Esses vivem no arquivo, sob controle
de versão, porque veredito que dá pra reajustar no meio da discussão é veredito que dá pra derrubar
na discussão.

## O que você não pode desligar

1. Risco primeiro. Sem abertura elogiosa.
2. Concordar é travado mais forte que discordar.
3. Cobertura baixa nunca vira concordância.
4. Abstenção nunca conta como "não".
5. O veredito é composto em código, nunca narrado.
6. Mesmo estado, mesmo veredito. O hash fica registrado.
7. Pressão não é estado.
8. Somente leitura. Nunca envia, posta, edita nem executa nada fora de `working/`.
9. Nada de avaliar pessoas.
10. Quem decide é você. Ela se oferece para ajudar a executar inclusive contra ela mesma.

## O que vem na caixa

```
ysat-jev/
├── SKILL.md                        a skill em si
├── config.yaml                     backend, limiares, coeficientes
├── README.md / README.pt-BR.md
├── BENCHMARK.md                    comparacao medida contra a skill base
├── LICENSE                         MIT
├── CHANGELOG.md
├── scripts/
│   ├── typed_judgment.py           três primitivas, quatro backends, uma interface
│   ├── question_bank.py            as perguntas atômicas
│   └── compose_verdict.py          composição, travas e o hash do estado
├── infra/openjev/
│   ├── README.md                   como subir o motor, e o contrato HTTP
│   └── stub_server.py              stub determinístico, sem peso nenhum
├── docs/
│   ├── typed-decisions.md          por que decisão tipada, e como as travas funcionam
│   └── adr/ADR-0001-typed-verdict.md
└── references/
    ├── risk-checklists.md          9 domínios mais os vieses que sustentam decisão ruim
    ├── customization.md            cada knob, e o que é travado
    └── examples.md                 cinco rodadas reais, com números de verdade
```

## Limites honestos

Os coeficientes parecem objetivos porque são números. Eles são um juízo de valor, e não estão
validados até serem medidos. Trate o índice de risco como uma **ordenação** consistente ("esta
decisão é mais arriscada que aquela sob os mesmos coeficientes"), não como verdade absoluta ("0.61 é
ruim e 0.59 está bom").

O ADR declara a medição que mantém ou aposenta esta variante, e o desfecho honesto é que ela pode
ser aposentada. Contraponto que é apenas mais elaborado não é melhor.

## Quando não usar

- Contraponto rápido em conversa: use a YSAT base, é o padrão certo.
- Análise equilibrada de prós e contras: esta variante é unilateral, como a base.
- Decisão já executada: isso é pós-mortem.
- Opinião sobre uma pessoa: ela recusa e oferece análise de processo.

## Contribuindo

Issues e pull requests são bem-vindos, principalmente novas perguntas atômicas e dados medidos de
coeficiente. Mantenha travado o que está travado: o único pull request que não será aceito é o que
deixa concordar mais barato.

## Licença

MIT. Veja [LICENSE](LICENSE).
