# Prepara ENEM — Sistema de correção de cartões-resposta

Programa local (roda só no computador da escola, sem internet, sem login,
sem nuvem) para gerar, ler e corrigir os cartões-resposta do simulado
"Prepara ENEM".

Três partes:
1. **Gerador** — cria os cartões-resposta em PDF, personalizados por aluno, com QR code.
2. **Leitor** — lê os cartões escaneados com visão computacional (OpenCV), sem IA.
3. **Corretor** — compara com o gabarito e gera a planilha de notas (.xlsx).

## Como instalar (Windows)

1. Instale o [Python](https://www.python.org/downloads/) (marque a opção "Add Python to PATH" durante a instalação).
2. Abra o "Prompt de Comando" nesta pasta e rode:
   ```
   pip install -r requirements.txt
   ```

## Como usar

Rode:
```
streamlit run app.py
```

Isso abre uma página no navegador com o painel. Fica aberta enquanto o
comando estiver rodando; para fechar, volte ao Prompt de Comando e
aperte `Ctrl+C`.

### Tela 1 — Gerar cartões

- Cole a lista de alunos (um por linha: `nome, série, matrícula`; também
  aceita colar direto do Excel).
- Preencha nome do simulado, bimestre, turma e as orientações de
  preenchimento (aparecem impressas no cartão).
- Ajuste o número de questões do simulado.
- Clique em "Gerar cartões" para baixar o PDF (para imprimir) e o
  arquivo `mapa_cartao_*.json` (guarde — ele é necessário na tela 2,
  o Leitor, para achar as bolhas certas).
- Se o número de questões não couber numa folha, o sistema cria
  automaticamente uma 2ª folha para aquele aluno.

### Tela 2 — Ler cartões escaneados

- Envie os cartões escaneados (PDF ou imagem PNG/JPG), quantos quiser de
  uma vez.
- O sistema acha sozinho as marcas dos 4 cantos, corrige a folha (mesmo
  se o escaneamento ficar um pouco torto) e mede cada bolha. A matrícula
  de cada aluno vem do QR code — não precisa digitar nada.
- Baixe o `respostas_lidas.json` ao final (serve para corrigir depois,
  mesmo numa sessão nova do programa).

### Tela 3 — Gabarito e notas

- Digite o gabarito (a resposta certa de cada questão). Aceita: uma
  letra por linha, `numero: letra` por linha, ou tudo numa linha só
  (ex: `ABCDE...`).
- Clique em "Corrigir e gerar notas" para ver a tabela de notas na tela
  e baixar a planilha `.xlsx` completa (nota, acertos, questões em
  branco, dupla marcação e a resposta de cada aluno em cada questão).
