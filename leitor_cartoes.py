"""
Leitor de cartao-resposta - Prepara ENEM
Peca 2 de 3 do sistema (gerador -> leitor -> corretor).

Le os cartoes ESCANEADOS (PDF ou imagem) com visao computacional
classica (OpenCV) - sem IA, sem LLM. E' um problema determinístico:
achar 4 quadrados nos cantos, corrigir a perspectiva da folha, e medir
se cada bolha esta' escura ou nao. Inspirado no projeto OMRChecker.

Passo a passo para cada folha escaneada:
  1) acha as 4 marcas de referencia (quadrados pretos) nos cantos;
  2) usa essas marcas para "desentortar" a folha (warp de perspectiva),
     trazendo ela para o mesmo tamanho/posicao do PDF original;
  3) le o QR code (matricula + numero da folha);
  4) usa o mapa_cartao.json (gerado na Parte 1) para ir direto em cada
     coordenada de bolha e medir se esta preenchida.
"""

import io
import os

import cv2
import numpy as np

PONTOS_POR_POLEGADA = 72
DPI_CANONICO = 200  # resolucao interna usada para reprocessar as folhas

LIMIAR_PREENCHIMENTO = 0.35   # % minima de pixels escuros pra contar como "marcada"
MARGEM_MINIMA_ENTRE_MARCAS = 0.15  # diferenca minima pra nao considerar dupla marcacao


class ErroLeitura(Exception):
    """Erro ao processar uma folha (ex: nao achou as marcas de referencia)."""


def _escala_px_por_pt(dpi=DPI_CANONICO):
    return dpi / PONTOS_POR_POLEGADA


def carregar_paginas_como_imagens(dados_arquivo, nome_arquivo):
    """Converte um arquivo (bytes) em uma lista de imagens OpenCV (uma por
    pagina). Aceita PDF (todas as paginas) ou imagem unica (PNG/JPG)."""
    extensao = os.path.splitext(nome_arquivo)[1].lower()

    if extensao == ".pdf":
        import fitz  # PyMuPDF

        doc = fitz.open(stream=dados_arquivo, filetype="pdf")
        imagens = []
        for pagina in doc:
            pix = pagina.get_pixmap(dpi=DPI_CANONICO)
            arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                pix.height, pix.width, pix.n
            )
            if pix.n == 4:
                arr = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
            elif pix.n == 3:
                arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            else:
                arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
            imagens.append(arr)
        return imagens

    arr = cv2.imdecode(np.frombuffer(dados_arquivo, dtype=np.uint8), cv2.IMREAD_COLOR)
    if arr is None:
        raise ErroLeitura(f"Nao consegui abrir a imagem '{nome_arquivo}'.")
    return [arr]


def encontrar_marcas_referencia(imagem_cinza):
    """Acha os 4 quadrados pretos dos cantos e devolve os centros deles em
    pixels, na ordem [sup-esq, sup-dir, inf-esq, inf-dir].
    Devolve None se nao achar os 4."""
    altura, largura = imagem_cinza.shape[:2]

    _, binaria = cv2.threshold(
        imagem_cinza, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )
    contornos, _ = cv2.findContours(binaria, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    area_min = (largura * 0.008) * (altura * 0.008)
    area_max = (largura * 0.05) * (altura * 0.05)

    candidatos = []
    for cnt in contornos:
        area = cv2.contourArea(cnt)
        if area < area_min or area > area_max:
            continue
        x, y, bw, bh = cv2.boundingRect(cnt)
        if bh == 0:
            continue
        aspecto = bw / bh
        if 0.6 < aspecto < 1.4:
            candidatos.append((x + bw / 2, y + bh / 2))

    if len(candidatos) < 4:
        return None

    cantos_esperados = [(0, 0), (largura, 0), (0, altura), (largura, altura)]
    escolhidos = []
    restantes = list(candidatos)
    for canto in cantos_esperados:
        melhor = min(restantes, key=lambda c: (c[0] - canto[0]) ** 2 + (c[1] - canto[1]) ** 2)
        restantes.remove(melhor)
        escolhidos.append(melhor)

    return escolhidos


def _pontos_mapa_para_pixels(pontos_pt, escala, altura_alvo_px):
    """Converte coordenadas do mapa_cartao.json (sistema do reportlab: origem
    no canto inferior esquerdo) para pixels de imagem (origem no canto
    superior esquerdo)."""
    return [(x * escala, altura_alvo_px - y * escala) for x, y in pontos_pt]


def corrigir_perspectiva(imagem_cinza, pontos_mapa_referencia):
    """Acha as marcas de referencia na imagem escaneada e desentorta a
    folha para o tamanho canonico (mesma escala do PDF gerado)."""
    escala = _escala_px_por_pt()
    largura_alvo = pontos_mapa_referencia["pagina"]["largura"] * escala
    altura_alvo = pontos_mapa_referencia["pagina"]["altura"] * escala

    pontos_imagem = encontrar_marcas_referencia(imagem_cinza)
    if pontos_imagem is None:
        raise ErroLeitura(
            "Nao encontrei as 4 marcas pretas dos cantos nesta folha. "
            "Confira se a folha inteira apareceu no escaneamento/foto."
        )

    pontos_destino = _pontos_mapa_para_pixels(
        pontos_mapa_referencia["marcas_referencia"], escala, altura_alvo
    )

    matriz = cv2.getPerspectiveTransform(
        np.float32(pontos_imagem), np.float32(pontos_destino)
    )
    corrigida = cv2.warpPerspective(
        imagem_cinza, matriz, (int(round(largura_alvo)), int(round(altura_alvo)))
    )
    return corrigida, escala, largura_alvo, altura_alvo


def ler_qr(imagem_cinza):
    """Le o QR code (gravado como 'matricula|pagina') e devolve (matricula, pagina)
    ou (None, None) se nao achar."""
    detector = cv2.QRCodeDetector()
    conteudo, _, _ = detector.detectAndDecode(imagem_cinza)
    if not conteudo or "|" not in conteudo:
        return None, None
    matricula, pagina_str = conteudo.split("|", 1)
    try:
        pagina = int(pagina_str)
    except ValueError:
        pagina = None
    return matricula, pagina


def _proporcao_preenchida(imagem_binaria, x_px, y_px, raio_px):
    """Mede que fracao dos pixels dentro do circulo (um pouco menor que a
    bolha impressa, pra nao pegar o traco da borda) esta escura."""
    raio_medida = max(2, int(raio_px * 0.7))
    altura, largura = imagem_binaria.shape[:2]

    x0, x1 = int(x_px - raio_medida), int(x_px + raio_medida)
    y0, y1 = int(y_px - raio_medida), int(y_px + raio_medida)
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(largura, x1), min(altura, y1)
    if x1 <= x0 or y1 <= y0:
        return 0.0

    recorte = imagem_binaria[y0:y1, x0:x1]
    mascara = np.zeros(recorte.shape, dtype=np.uint8)
    centro_local = (x_px - x0, y_px - y0)
    cv2.circle(mascara, (int(centro_local[0]), int(centro_local[1])), raio_medida, 255, -1)

    pixels_do_circulo = mascara > 0
    total = np.count_nonzero(pixels_do_circulo)
    if total == 0:
        return 0.0
    escuros = np.count_nonzero((recorte > 0) & pixels_do_circulo)
    return escuros / total


def decidir_resposta(proporcoes, limiar=LIMIAR_PREENCHIMENTO,
                      margem_minima=MARGEM_MINIMA_ENTRE_MARCAS):
    """A partir de {alternativa: proporcao_preenchida}, decide a resposta:
    a letra marcada, None (em branco) ou 'MULTIPLA' (mais de uma bolha
    preenchida, sem uma se destacar claramente)."""
    marcadas = [alt for alt, p in proporcoes.items() if p >= limiar]
    if not marcadas:
        return None
    if len(marcadas) == 1:
        return marcadas[0]

    ordenadas = sorted(proporcoes.items(), key=lambda kv: -kv[1])
    primeira, segunda = ordenadas[0][1], ordenadas[1][1]
    if primeira - segunda >= margem_minima:
        return ordenadas[0][0]
    return "MULTIPLA"


def ler_pagina(imagem_bgr, mapa):
    """Processa UMA folha escaneada (ja' carregada como imagem OpenCV) e
    devolve {"matricula": ..., "pagina": ..., "respostas": {"1": "A", ...}}."""
    cinza = cv2.cvtColor(imagem_bgr, cv2.COLOR_BGR2GRAY) if imagem_bgr.ndim == 3 else imagem_bgr

    corrigida, escala, largura_alvo, altura_alvo = corrigir_perspectiva(cinza, mapa)

    matricula, pagina = ler_qr(corrigida)
    if not matricula:
        # tenta de novo direto na imagem original, antes do warp
        # (as vezes o QR fica mais nitido sem a reamostragem do warp)
        matricula, pagina = ler_qr(cinza)
    if not matricula:
        raise ErroLeitura(
            "Nao consegui ler o QR code desta folha (matricula do aluno)."
        )

    pagina = pagina or 1
    total_paginas = mapa.get("total_paginas_por_aluno", 1)
    if pagina < 1 or pagina > total_paginas:
        raise ErroLeitura(
            f"O QR code informa a folha {pagina}, mas o simulado so' tem "
            f"{total_paginas} folha(s) por aluno."
        )

    _, binaria = cv2.threshold(corrigida, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    layout = mapa["layout_bolhas_por_pagina"][pagina - 1]
    raio_px = mapa["raio_bolha"] * escala

    respostas = {}
    for questao, coordenadas_alternativas in layout.items():
        proporcoes = {}
        for alt, (x_pt, y_pt) in coordenadas_alternativas.items():
            x_px = x_pt * escala
            y_px = altura_alvo - y_pt * escala
            proporcoes[alt] = _proporcao_preenchida(binaria, x_px, y_px, raio_px)
        respostas[questao] = decidir_resposta(proporcoes)

    return {"matricula": matricula, "pagina": pagina, "respostas": respostas}


def processar_arquivos(arquivos, mapa):
    """'arquivos' e' uma lista de (nome_arquivo, dados_em_bytes).
    Devolve (respostas_por_aluno, avisos):
      respostas_por_aluno: {matricula: {"1": "A", "2": None, ...}}
      avisos: lista de mensagens (folhas que deram problema)
    """
    respostas_por_aluno = {}
    folhas_recebidas_por_aluno = {}
    avisos = []

    for nome_arquivo, dados in arquivos:
        try:
            paginas = carregar_paginas_como_imagens(dados, nome_arquivo)
        except Exception as e:
            avisos.append(f"{nome_arquivo}: nao consegui abrir o arquivo ({e}).")
            continue

        for indice_pagina, imagem in enumerate(paginas, start=1):
            origem = nome_arquivo if len(paginas) == 1 else f"{nome_arquivo} (pagina {indice_pagina})"
            try:
                resultado = ler_pagina(imagem, mapa)
            except ErroLeitura as e:
                avisos.append(f"{origem}: {e}")
                continue

            matricula = resultado["matricula"]
            respostas_por_aluno.setdefault(matricula, {})
            respostas_por_aluno[matricula].update(resultado["respostas"])
            folhas_recebidas_por_aluno.setdefault(matricula, set()).add(resultado["pagina"])

    total_paginas = mapa.get("total_paginas_por_aluno", 1)
    if total_paginas > 1:
        for matricula, paginas_lidas in folhas_recebidas_por_aluno.items():
            faltando = set(range(1, total_paginas + 1)) - paginas_lidas
            if faltando:
                avisos.append(
                    f"Matricula {matricula}: faltam a(s) folha(s) "
                    f"{sorted(faltando)} de {total_paginas}."
                )

    return respostas_por_aluno, avisos
