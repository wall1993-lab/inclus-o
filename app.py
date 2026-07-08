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
import json
import os
import sys
from datetime import datetime

import fitz  # PyMuPDF, so' para desenhar a previa do cartao na tela
import streamlit as st

from gerador_cartoes import gerar, parse_lista_alunos, ORIENTACOES_PADRAO
from leitor_cartoes import processar_arquivos
from corretor_notas import parse_gabarito, corrigir, gerar_planilha

st.set_page_config(page_title="Prepara ENEM", page_icon="📝", layout="wide")


def _pasta_base():
    """Quando o programa e' o .exe empacotado, salva os arquivos ao lado
    do proprio .exe (nao numa pasta temporaria que some depois)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


PASTA_SAIDA = os.path.join(_pasta_base(), "saida_cartoes")
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
        bimestre = st.text_input("Bimestre", value="", placeholder="Ex: 2º Bimestre")
        turma = st.text_input("Turma", value="", placeholder="Ex: 1º A")
        num_questoes = st.number_input(
            "Número de questões", min_value=1, max_value=300, value=30, step=1
        )
        num_alternativas = st.selectbox(
            "Alternativas por questão", options=[4, 5], index=1,
            help="ENEM tradicional usa 5 (A a E)."
        )
        alternativas = ["A", "B", "C", "D", "E"][:num_alternativas]

    orientacoes_texto = st.text_area(
        "Orientações de preenchimento (uma por linha, aparecem impressas no cartão)",
        value="\n".join(ORIENTACOES_PADRAO),
        height=120,
    )

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

                orientacoes = [l for l in orientacoes_texto.splitlines() if l.strip()]

                gerar(
                    alunos,
                    num_questoes=int(num_questoes),
                    alternativas=alternativas,
                    nome_simulado=nome_simulado,
                    bimestre=bimestre,
                    turma=turma,
                    orientacoes=orientacoes,
                    saida_pdf=caminho_pdf,
                    saida_mapa=caminho_mapa,
                )

                with open(caminho_mapa, encoding="utf-8") as f:
                    st.session_state["mapa_atual"] = json.load(f)

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
# ABA 2 - LEITOR
# ------------------------------------------------------------------
with aba_ler:
    st.header("Ler cartões escaneados")
    st.markdown(
        "Envie os cartões escaneados (PDF ou imagem PNG/JPG). O sistema acha "
        "sozinho as marcas dos 4 cantos, corrige a folha e mede as bolhas — "
        "a matrícula de cada aluno vem do QR code, sem precisar digitar nada."
    )

    mapa_atual = st.session_state.get("mapa_atual")
    if mapa_atual:
        st.success(
            f"Usando o mapa gerado na aba 1 ({mapa_atual['num_questoes']} questões, "
            f"{len(mapa_atual['alunos'])} aluno(s) cadastrados)."
        )

    arquivo_mapa = st.file_uploader(
        "Se estiver numa sessão nova (sem ter gerado os cartões agora), "
        "envie aqui o arquivo mapa_cartao_*.json",
        type=["json"], key="upload_mapa_leitor",
    )
    if arquivo_mapa is not None:
        mapa_atual = json.loads(arquivo_mapa.read())
        st.session_state["mapa_atual"] = mapa_atual

    arquivos_escaneados = st.file_uploader(
        "Cartões escaneados (pode selecionar vários de uma vez)",
        type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True,
    )

    ler_clicado = st.button("Ler cartões", type="primary")

    if ler_clicado:
        if not mapa_atual:
            st.error(
                "Preciso do mapa: gere os cartões na aba 1 nesta sessão, "
                "ou envie o arquivo mapa_cartao.json acima."
            )
        elif not arquivos_escaneados:
            st.error("Envie pelo menos um arquivo escaneado.")
        else:
            arquivos_bytes = [(f.name, f.read()) for f in arquivos_escaneados]
            with st.spinner("Lendo bolhas..."):
                respostas_por_aluno, avisos = processar_arquivos(arquivos_bytes, mapa_atual)

            st.session_state["respostas_lidas"] = respostas_por_aluno

            if avisos:
                st.warning("Atenção:")
                for aviso in avisos:
                    st.write(f"- {aviso}")

            if not respostas_por_aluno:
                st.error("Não consegui ler nenhum cartão. Confira os avisos acima.")
            else:
                st.success(f"Lidos {len(respostas_por_aluno)} cartão(ões).")

                alunos_conhecidos = {a["matricula"]: a for a in mapa_atual.get("alunos", [])}
                linhas_tabela = []
                for matricula, respostas in respostas_por_aluno.items():
                    nome = alunos_conhecidos.get(matricula, {}).get("nome", "(matrícula não cadastrada)")
                    respondidas = sum(1 for v in respostas.values() if v not in (None, "MULTIPLA"))
                    em_branco = sum(1 for v in respostas.values() if v is None)
                    duplas = sum(1 for v in respostas.values() if v == "MULTIPLA")
                    linhas_tabela.append({
                        "Matrícula": matricula,
                        "Nome": nome,
                        "Respondidas": respondidas,
                        "Em branco": em_branco,
                        "Dupla marcação": duplas,
                    })
                st.dataframe(linhas_tabela, use_container_width=True)

                respostas_json = json.dumps(respostas_por_aluno, ensure_ascii=False, indent=2).encode("utf-8")
                st.download_button(
                    "⬇️ Baixar respostas lidas (JSON)", respostas_json,
                    file_name="respostas_lidas.json", mime="application/json",
                )
                st.info(
                    "Guarde esse arquivo — ele vai ser usado na aba 'Gabarito e notas' "
                    "para calcular as notas (útil se for corrigir num outro dia)."
                )

# ------------------------------------------------------------------
# ABA 3 - CORRETOR
# ------------------------------------------------------------------
with aba_notas:
    st.header("Gabarito e notas")

    mapa_atual = st.session_state.get("mapa_atual")
    respostas_por_aluno = st.session_state.get("respostas_lidas")

    col_mapa, col_respostas = st.columns(2)
    with col_mapa:
        arquivo_mapa2 = st.file_uploader(
            "mapa_cartao.json (se necessário)", type=["json"], key="upload_mapa_corretor"
        )
        if arquivo_mapa2 is not None:
            mapa_atual = json.loads(arquivo_mapa2.read())
            st.session_state["mapa_atual"] = mapa_atual
    with col_respostas:
        arquivo_respostas = st.file_uploader(
            "respostas_lidas.json (se necessário)", type=["json"], key="upload_respostas_corretor"
        )
        if arquivo_respostas is not None:
            respostas_por_aluno = json.loads(arquivo_respostas.read())
            st.session_state["respostas_lidas"] = respostas_por_aluno

    if not mapa_atual:
        st.info("Gere os cartões na aba 1 (ou envie o mapa_cartao.json acima) para continuar.")
    elif not respostas_por_aluno:
        st.info("Leia os cartões na aba 2 (ou envie o respostas_lidas.json acima) para continuar.")
    else:
        num_questoes = mapa_atual["num_questoes"]
        st.write(
            f"Simulado com {num_questoes} questões, "
            f"{len(mapa_atual['alunos'])} aluno(s) cadastrados."
        )

        gabarito_texto = st.text_area(
            "Gabarito (a resposta certa de cada questão)",
            height=150,
            placeholder=(
                "Aceita: uma letra por linha (na ordem das questões); "
                "\"numero: letra\" por linha; ou tudo numa linha só, ex: ABCDE..."
            ),
        )

        corrigir_clicado = st.button("Corrigir e gerar notas", type="primary")

        if corrigir_clicado:
            gabarito, erros_gabarito = parse_gabarito(gabarito_texto, num_questoes)
            if erros_gabarito:
                st.warning("Atenção com o gabarito:")
                for erro in erros_gabarito:
                    st.write(f"- {erro}")

            if not gabarito:
                st.error("Não consegui entender o gabarito.")
            else:
                turma_global = mapa_atual.get("turma", "")
                alunos_para_corrigir = [dict(a, turma=turma_global) for a in mapa_atual["alunos"]]

                resultado = corrigir(alunos_para_corrigir, respostas_por_aluno, gabarito, num_questoes)

                carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
                caminho_xlsx = os.path.join(PASTA_SAIDA, f"notas_{carimbo}.xlsx")
                gerar_planilha(resultado, num_questoes, saida_xlsx=caminho_xlsx)

                st.success(f"Pronto! {len(resultado)} aluno(s) corrigido(s).")

                tabela_resumo = [
                    {
                        "Nome": r["nome"],
                        "Turma": r["turma"],
                        "Matrícula": r["matricula"],
                        "Acertos": r["acertos"],
                        "Nota": r["nota"],
                        "Em branco": r["em_branco"],
                        "Dupla marcação": r["duplas_marcacoes"],
                        "Cartão lido?": "Sim" if r["recebeu_leitura"] else "NÃO",
                    }
                    for r in resultado
                ]
                st.dataframe(tabela_resumo, use_container_width=True)

                with open(caminho_xlsx, "rb") as f:
                    st.download_button(
                        "⬇️ Baixar planilha de notas (.xlsx)", f,
                        file_name=os.path.basename(caminho_xlsx),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
