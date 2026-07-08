# Prepara ENEM — Sistema de correção de cartões-resposta

Programa local (roda só no computador da escola, sem internet, sem login,
sem nuvem) para gerar, ler e corrigir os cartões-resposta do simulado
"Prepara ENEM".

Três partes:
1. **Gerador** — cria os cartões-resposta em PDF, personalizados por aluno, com QR code.
2. **Leitor** — lê os cartões escaneados com visão computacional (OpenCV), sem IA. *(em construção)*
3. **Corretor** — compara com o gabarito e gera a planilha de notas. *(em construção)*

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
- Ajuste o número de questões do simulado.
- Clique em "Gerar cartões" para baixar o PDF (para imprimir) e o
  arquivo `mapa_cartao_*.json` (guarde — ele será usado na Parte 2, o
  Leitor, para achar as bolhas certas).
- Se o número de questões não couber numa folha, o sistema cria
  automaticamente uma 2ª folha para aquele aluno.
