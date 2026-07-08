"""
Gerador de cartao-resposta - Prepara ENEM
Peca 1 de 3 do sistema (gerador -> leitor -> corretor).

Recebe uma lista de alunos e gera:
  1) um PDF com um cartao personalizado por aluno
  2) um mapa de coordenadas (JSON) que o leitor vai usar depois

O layout e' identico para todos os alunos, entao o mapa de bolhas e'
salvo UMA vez. So' o cabecalho e o QR mudam de aluno para aluno.

Se o numero de questoes nao couber numa folha so', o cartao daquele
aluno ganha automaticamente uma 2a (ou 3a...) folha. O QR code de cada
folha grava "matricula|numero_da_folha", para o leitor (Parte 2) saber
depois a quem pertence cada folha e como junta-las.
"""

import json
import re
import qrcode
from math import ceil, floor
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader

# ----------------------------------------------------------------------
# CONFIGURACAO PADRAO (a coordenadora pode sobrescrever cada uma na tela)
# ----------------------------------------------------------------------
NUM_QUESTOES_PADRAO = 30
ALTERNATIVAS_PADRAO = ["A", "B", "C", "D", "E"]
NOME_SIMULADO_PADRAO = "PREPARA ENEM"
ORIENTACOES_PADRAO = [
    "Use caneta preta ou azul escura.",
    "Preencha toda a bolha, sem passar da linha.",
    "Marque apenas uma alternativa por questao.",
    "Nao rasure; se errar, apague bem e marque de novo.",
    "Nao dobre nem amasse esta folha.",
]

# ----------------------------------------------------------------------
# medidas do desenho (em pontos; 1 mm = 2.83 pontos) - NAO mudam com o
# numero de questoes, porque o leitor depende do tamanho fisico das
# bolhas ser sempre igual.
# ----------------------------------------------------------------------
LARGURA, ALTURA = A4
MARGEM        = 15 * mm
FID_TAM       = 6  * mm      # tamanho do quadrado de referencia (canto)
RAIO_BOLHA    = 3.2 * mm     # raio das bolhas
ESPACO_H      = 9  * mm      # distancia horizontal entre alternativas
ESPACO_V      = 8  * mm      # distancia vertical entre questoes
TOPO_GRADE    = ALTURA - 95 * mm  # onde a grade de bolhas comeca (deixa
                                  # espaco acima para cabecalho + orientacoes)
FUNDO_GRADE   = MARGEM + FID_TAM + 15 * mm  # onde a grade tem que parar


def marcas_de_referencia(c):
    """Desenha 4 quadrados pretos nos cantos. Servem de ancora:
    o leitor acha esses quadrados e corrige a folha se o scanner entortou."""
    pos = [
        (MARGEM, ALTURA - MARGEM - FID_TAM),              # sup esq
        (LARGURA - MARGEM - FID_TAM, ALTURA - MARGEM - FID_TAM),  # sup dir
        (MARGEM, MARGEM),                                  # inf esq
        (LARGURA - MARGEM - FID_TAM, MARGEM),              # inf dir
    ]
    c.setFillColorRGB(0, 0, 0)
    centros = []
    for x, y in pos:
        c.rect(x, y, FID_TAM, FID_TAM, fill=1, stroke=0)
        centros.append([round(x + FID_TAM / 2, 2), round(y + FID_TAM / 2, 2)])
    return centros


def cabecalho(c, aluno, nome_simulado, bimestre="", turma="",
              pagina_atual=1, total_paginas=1):
    """Nome do simulado, bimestre/turma, dados do aluno e QR code com a
    matricula.

    O QR grava "matricula|pagina" (ex: "2026001|1") para o leitor saber,
    de forma automatica, de quem e' a folha e qual pedaco do cartao ela
    representa - sem precisar digitar nada.
    """
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(MARGEM + 10 * mm, ALTURA - 30 * mm, nome_simulado)

    c.setFont("Helvetica", 11)
    if bimestre or turma:
        partes = []
        if turma:
            partes.append(f"Turma: {turma}")
        if bimestre:
            partes.append(f"Bimestre: {bimestre}")
        c.drawString(MARGEM + 10 * mm, ALTURA - 38 * mm, "    ".join(partes))

    c.drawString(MARGEM + 10 * mm, ALTURA - 46 * mm, f"Aluno: {aluno['nome']}")
    linha_serie = f"Serie: {aluno['serie']}    Matricula: {aluno['matricula']}"
    if total_paginas > 1:
        linha_serie += f"    Folha {pagina_atual}/{total_paginas}"
    c.drawString(MARGEM + 10 * mm, ALTURA - 52 * mm, linha_serie)

    conteudo_qr = f"{aluno['matricula']}|{pagina_atual}"
    qr = qrcode.make(conteudo_qr)
    qr_img = ImageReader(qr.get_image())
    lado = 22 * mm
    c.drawImage(qr_img, LARGURA - MARGEM - FID_TAM - lado - 4 * mm,
                ALTURA - 30 * mm - lado + 6 * mm, lado, lado)


def bloco_orientacoes(c, linhas_orientacoes):
    """Desenha a caixa de instrucoes de preenchimento (o que a
    coordenadora escreveu no campo 'Orientacoes') e a legenda visual de
    bolha correta/incorreta, no espaco entre o cabecalho e a grade."""
    topo = ALTURA - 60 * mm
    c.setFont("Helvetica-Bold", 9)
    c.setFillColorRGB(0, 0, 0)
    c.drawString(MARGEM + 10 * mm, topo, "INSTRUCOES")

    c.setFont("Helvetica", 8)
    y = topo - 5 * mm
    for linha in linhas_orientacoes:
        if not linha.strip():
            continue
        c.drawString(MARGEM + 10 * mm, y, f"- {linha.strip()}")
        y -= 4.2 * mm

    # legenda: exemplo de bolha correta (preenchida) e incorreta (com X)
    y_legenda = y - 3 * mm
    raio_exemplo = 2.6 * mm

    x1 = MARGEM + 12 * mm
    c.setFillColorRGB(0, 0, 0)
    c.circle(x1, y_legenda, raio_exemplo, fill=1, stroke=0)
    c.setFont("Helvetica", 8)
    c.drawString(x1 + 6 * mm, y_legenda - 2, "certo")

    x2 = MARGEM + 40 * mm
    c.setLineWidth(0.8)
    c.circle(x2, y_legenda, raio_exemplo, fill=0, stroke=1)
    c.line(x2 - raio_exemplo, y_legenda - raio_exemplo,
           x2 + raio_exemplo, y_legenda + raio_exemplo)
    c.line(x2 - raio_exemplo, y_legenda + raio_exemplo,
           x2 + raio_exemplo, y_legenda - raio_exemplo)
    c.drawString(x2 + 6 * mm, y_legenda - 2, "errado")


def calcular_layout_pagina(alternativas):
    """Descobre quantas colunas e linhas de questoes cabem numa folha,
    respeitando o tamanho fixo das bolhas (importante para o leitor)."""
    largura_bloco = (len(alternativas) + 1) * ESPACO_H  # +1 pro numero da questao
    largura_util = LARGURA - 2 * MARGEM - 10 * mm
    colunas = max(1, floor(largura_util / largura_bloco))

    altura_util = TOPO_GRADE - FUNDO_GRADE
    linhas = max(1, floor(altura_util / ESPACO_V) + 1)

    return colunas, linhas, largura_bloco


def grade_de_bolhas(c, alternativas, questoes_da_pagina, largura_bloco, linhas_por_coluna):
    """Desenha as bolhas de UMA pagina e devolve o mapa local:
    posicao_na_pagina (1..N) -> alternativa -> (x, y).
    'questoes_da_pagina' e' a lista de numeros de questao que entram nessa folha.
    """
    mapa = {}
    for posicao, q in enumerate(questoes_da_pagina):
        coluna = posicao // linhas_por_coluna
        linha = posicao % linhas_por_coluna
        x0 = MARGEM + 10 * mm + coluna * largura_bloco
        y = TOPO_GRADE - linha * ESPACO_V

        c.setFont("Helvetica", 10)
        c.setFillColorRGB(0, 0, 0)
        c.drawRightString(x0 + 4 * mm, y - 3, str(q))

        mapa[str(q)] = {}
        for i, alt in enumerate(alternativas):
            cx = x0 + (i + 1) * ESPACO_H
            cy = y
            c.setLineWidth(0.8)
            c.circle(cx, cy, RAIO_BOLHA, fill=0, stroke=1)
            c.setFont("Helvetica", 7)
            c.drawCentredString(cx, cy - 2.2, alt)
            mapa[str(q)][alt] = [round(cx, 2), round(cy, 2)]
    return mapa


def parse_lista_alunos(texto):
    """Converte o texto colado pela coordenadora numa lista de alunos.

    Aceita uma linha por aluno, com os campos separados por TAB (padrao
    ao colar do Excel), virgula ou ponto-e-virgula, na ordem:
    nome, serie, matricula.

    Devolve (alunos, erros). 'erros' e' uma lista de mensagens, uma para
    cada linha que nao pode ser interpretada (para mostrar na tela).
    """
    alunos = []
    erros = []
    matriculas_vistas = set()

    linhas = [l.strip() for l in texto.splitlines()]
    for numero_linha, linha in enumerate(linhas, start=1):
        if not linha:
            continue

        if "\t" in linha:
            campos = linha.split("\t")
        elif ";" in linha:
            campos = linha.split(";")
        else:
            campos = linha.split(",")
        campos = [c.strip() for c in campos]

        # ignora uma eventual linha de cabecalho (ex: "nome, serie, matricula")
        if numero_linha == 1 and campos[0].lower() in ("nome", "aluno"):
            continue

        if len(campos) < 3:
            erros.append(f"Linha {numero_linha}: esperava 3 campos "
                         f"(nome, serie, matricula), encontrei {len(campos)}: \"{linha}\"")
            continue

        nome, serie, matricula = campos[0], campos[1], campos[2]
        if not nome or not serie or not matricula:
            erros.append(f"Linha {numero_linha}: nome, serie ou matricula em branco: \"{linha}\"")
            continue

        if matricula in matriculas_vistas:
            erros.append(f"Linha {numero_linha}: matricula \"{matricula}\" repetida")
            continue
        matriculas_vistas.add(matricula)

        alunos.append({"nome": nome, "serie": serie, "matricula": matricula})

    return alunos, erros


def gerar(alunos, num_questoes=NUM_QUESTOES_PADRAO, alternativas=None,
          nome_simulado=NOME_SIMULADO_PADRAO, bimestre="", turma="",
          orientacoes=None,
          saida_pdf="cartoes.pdf", saida_mapa="mapa_cartao.json"):
    """Gera o PDF com um cartao (uma ou mais folhas) por aluno, e o
    mapa_cartao.json que a Parte 2 (leitor) vai usar."""
    if alternativas is None:
        alternativas = list(ALTERNATIVAS_PADRAO)
    if orientacoes is None:
        orientacoes = list(ORIENTACOES_PADRAO)
    if not alunos:
        raise ValueError("A lista de alunos esta vazia.")
    if num_questoes < 1:
        raise ValueError("O numero de questoes precisa ser pelo menos 1.")

    colunas, linhas_por_coluna, largura_bloco = calcular_layout_pagina(alternativas)
    questoes_por_pagina = colunas * linhas_por_coluna
    total_paginas = ceil(num_questoes / questoes_por_pagina)

    c = canvas.Canvas(saida_pdf, pagesize=A4)
    fiduciais = None
    layout_bolhas_por_pagina = []

    for aluno in alunos:
        for pagina in range(1, total_paginas + 1):
            primeira_questao = (pagina - 1) * questoes_por_pagina + 1
            ultima_questao = min(pagina * questoes_por_pagina, num_questoes)
            questoes_da_pagina = list(range(primeira_questao, ultima_questao + 1))

            fiduciais = marcas_de_referencia(c)
            cabecalho(c, aluno, nome_simulado, bimestre, turma, pagina, total_paginas)
            bloco_orientacoes(c, orientacoes)
            mapa_local = grade_de_bolhas(c, alternativas, questoes_da_pagina,
                                          largura_bloco, linhas_por_coluna)
            if len(layout_bolhas_por_pagina) < pagina:
                layout_bolhas_por_pagina.append(mapa_local)
            c.showPage()
    c.save()

    mapa = {
        "pagina": {"largura": round(LARGURA, 2), "altura": round(ALTURA, 2)},
        "marcas_referencia": fiduciais,
        "raio_bolha": round(RAIO_BOLHA, 2),
        "num_questoes": num_questoes,
        "alternativas": alternativas,
        "questoes_por_pagina": questoes_por_pagina,
        "total_paginas_por_aluno": total_paginas,
        "layout_bolhas_por_pagina": layout_bolhas_por_pagina,
        "nome_simulado": nome_simulado,
        "bimestre": bimestre,
        "turma": turma,
        "alunos": [{"nome": a["nome"], "matricula": a["matricula"],
                    "serie": a["serie"]} for a in alunos],
    }
    with open(saida_mapa, "w", encoding="utf-8") as f:
        json.dump(mapa, f, ensure_ascii=False, indent=2)
    return saida_pdf, saida_mapa


if __name__ == "__main__":
    # alunos de exemplo (na versao final isso vem do campo que a coordenadora preenche)
    alunos = [
        {"nome": "Ana Beatriz Souza",   "serie": "1a Serie", "matricula": "2026001"},
        {"nome": "Carlos Eduardo Lima", "serie": "2a Serie", "matricula": "2026002"},
        {"nome": "Marina Alves Rocha",  "serie": "3a Serie", "matricula": "2026003"},
    ]
    pdf, mapa = gerar(alunos)
    print(f"Gerado: {pdf} ({len(alunos)} cartoes) e {mapa}")
