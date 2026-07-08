"""
Prepara ENEM - Painel da coordenadora
Interface unica (Streamlit) com 3 telas: Gerar cartoes, Ler cartoes, Notas.

Como rodar (Windows, com Python instalado):
    pip install -r requirements.txt
    streamlit run app.py

Isso abre uma pagina no navegador (roda tudo localmente, nada sai do
computador).
"""

import io
import os
from datetime import datetime

import fitz  # PyMuPDF, so' para desenhar a previa do cartao na tela
import streamlit as st

from gerador_cartoes import gerar, parse_lista_alunos

st.set_page_config(page_title="Prepara ENEM", page_icon="📝", layout="wide")

PASTA_SAIDA = "saida_cartoes"
os.makedirs(PASTA_SAIDA, exist_ok=True)

EXEMPLO_LISTA = (
    "Ana Beatriz Souza, 1a Serie, 2026001\n"
    "Carlos Eduardo Lima, 2a Serie, 2026002\n"
    "Marina Alves Rocha, 3a Serie, 2026003"
)


def primeira_pagina_como_imagem(caminho_pdf):
    """Abre o PDF gerado e devolve a 1a pagina como imagem (para conferencia)."""
    doc = fitz.open(caminho_pdf)
    pix = doc[0].get_pixmap(dpi=120)
    return pix.tobytes("png")


st.title("📝 Prepara ENEM — Painel da coordenadora")

aba_gerar, aba_ler, aba_notas = st.tabs(
    ["1. Gerar cartões", "2. Ler cartões escaneados", "3. Gabarito e notas"]
)

# ------------------------------------------------------------------
# ABA 1 - GERAR CARTOES
# ------------------------------------------------------------------
with aba_gerar:
    st.header("Gerar cartões-resposta em PDF")
    st.markdown(
        "Cole abaixo a lista de alunos, um por linha, no formato "
        "**nome, série, matrícula** (também aceita colar direto do Excel, "
        "separado por TAB)."
    )

    col_lista, col_config = st.columns([2, 1])

    with col_lista:
        texto_alunos = st.text_area(
            "Lista de alunos",
            value="",
            height=260,
            placeholder=EXEMPLO_LISTA,
        )

    with col_config:
        nome_simulado = st.text_input("Nome do simulado", value="PREPARA ENEM")
        num_questoes = st.number_input(
            "Número de questões", min_value=1, max_value=300, value=30, step=1
        )
        num_alternativas = st.selectbox(
            "Alternativas por questão", options=[4, 5], index=1,
            help="ENEM tradicional usa 5 (A a E)."
        )
        alternativas = ["A", "B", "C", "D", "E"][:num_alternativas]

    gerar_clicado = st.button("Gerar cartões", type="primary")

    if gerar_clicado:
        if not texto_alunos.strip():
            st.error("Cole a lista de alunos antes de gerar.")
        else:
            alunos, erros = parse_lista_alunos(texto_alunos)

            if erros:
                st.warning(
                    "Algumas linhas não puderam ser lidas e foram ignoradas:"
                )
                for erro in erros:
                    st.write(f"- {erro}")

            if not alunos:
                st.error("Nenhum aluno válido foi encontrado na lista.")
            else:
                carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
                caminho_pdf = os.path.join(PASTA_SAIDA, f"cartoes_{carimbo}.pdf")
                caminho_mapa = os.path.join(PASTA_SAIDA, f"mapa_cartao_{carimbo}.json")

                gerar(
                    alunos,
                    num_questoes=int(num_questoes),
                    alternativas=alternativas,
                    nome_simulado=nome_simulado,
                    saida_pdf=caminho_pdf,
                    saida_mapa=caminho_mapa,
                )

                st.success(
                    f"Pronto! {len(alunos)} aluno(s), {num_questoes} questões. "
                    f"Arquivos salvos em `{PASTA_SAIDA}/`."
                )

                imagem_previa = primeira_pagina_como_imagem(caminho_pdf)
                st.image(imagem_previa, caption="Prévia da 1ª folha gerada", width=420)

                col_dl1, col_dl2 = st.columns(2)
                with col_dl1:
                    with open(caminho_pdf, "rb") as f:
                        st.download_button(
                            "⬇️ Baixar PDF dos cartões", f, file_name=os.path.basename(caminho_pdf),
                            mime="application/pdf",
                        )
                with col_dl2:
                    with open(caminho_mapa, "rb") as f:
                        st.download_button(
                            "⬇️ Baixar mapa (necessário na Parte 2 - Leitor)",
                            f, file_name=os.path.basename(caminho_mapa),
                            mime="application/json",
                        )

                st.info(
                    "Guarde o arquivo do mapa — ele vai ser usado depois, na tela "
                    "'Ler cartões escaneados', para achar as bolhas certas em cada folha."
                )

# ------------------------------------------------------------------
# ABA 2 - LEITOR (ainda não construída)
# ------------------------------------------------------------------
with aba_ler:
    st.header("Ler cartões escaneados")
    st.info(
        "🚧 Ainda não construída. Vai ficar aqui a tela para subir os PDFs/PNGs "
        "escaneados e o sistema ler as bolhas automaticamente com OpenCV."
    )

# ------------------------------------------------------------------
# ABA 3 - CORRETOR (ainda não construída)
# ------------------------------------------------------------------
with aba_notas:
    st.header("Gabarito e notas")
    st.info(
        "🚧 Ainda não construída. Vai ficar aqui a tela para informar o gabarito "
        "e baixar a planilha (.xlsx) com a nota de cada aluno."
    )
