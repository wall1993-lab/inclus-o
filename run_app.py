"""
Ponto de entrada usado so' para empacotar o Prepara ENEM como um unico
executavel do Windows (.exe) com o PyInstaller.

A coordenadora nao precisa mexer nesse arquivo nem entender ele - ele so'
existe para o processo de "montar" o programa pronto para clicar e usar.
"""
import os
import sys


def _resolver_caminho(nome_arquivo):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, nome_arquivo)


def _pular_pergunta_de_email_do_streamlit():
    """Sem isso, na primeira vez que abre, o Streamlit para e espera uma
    resposta no console perguntando um email - trava o programa para
    quem esta' so' clicando duas vezes no .exe."""
    pasta = os.path.join(os.path.expanduser("~"), ".streamlit")
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, "credentials.toml")
    if not os.path.exists(caminho):
        with open(caminho, "w", encoding="utf-8") as f:
            f.write('[general]\nemail = ""\n')


if __name__ == "__main__":
    _pular_pergunta_de_email_do_streamlit()
    os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"

    from streamlit.web import cli as stcli

    sys.argv = [
        "streamlit",
        "run",
        _resolver_caminho("app.py"),
        "--global.developmentMode=false",
        "--browser.gatherUsageStats=false",
    ]
    sys.exit(stcli.main())
