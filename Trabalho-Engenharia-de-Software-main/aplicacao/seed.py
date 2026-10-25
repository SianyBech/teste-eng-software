"""Carrega dados de teste no banco: peças com pôster e sessões (datas).

Uso, na pasta aplicacao e com o venv ativo:

    python seed.py                   # carrega dados_teste/pecas.json
    python seed.py --limpar          # apaga as peças desse arquivo e carrega de novo
    python seed.py --arquivo meu.json

Pode rodar várias vezes: peças que já existem (mesmo título) são puladas.
As datas do arquivo são "dias a partir de hoje", então as sessões ficam
sempre no futuro e aparecem no calendário de agendamento.
"""
import argparse
import json
import shutil
import struct
import zlib
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from app import app
from model.agendamentos import Agendamento
from model.models import Peca, SessaoData, db

PASTA_DADOS = Path(__file__).resolve().parent / "dados_teste"
ARQUIVO_PADRAO = PASTA_DADOS / "pecas.json"
EXTENSOES_POSTER = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MESES_PT = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]
ESCOLA_TESTE = {
    "nome": "Escola Teste Aurora",
    "cnpj": "11.222.333/0001-81",
    "email": "contato@escolateste.exemplo",
    "telefone": "(11) 98888-7777",
    "responsavel": "Maria Souza",
}


# ---------------------------------------------------------------- pôsteres
def _cores(titulo):
    """Duas cores (topo e base do degradê) escolhidas a partir do título."""
    h = zlib.crc32(titulo.encode("utf-8"))
    r, g, b = (h >> 16) & 255, (h >> 8) & 255, h & 255
    # faixas escolhidas para nunca passar de 255 (topo mais escuro, base mais clara)
    return (30 + r // 4, 20 + g // 4, 50 + b // 4), (120 + r // 2, 80 + g // 2, 110 + b // 2)


def _fonte(tamanho):
    from PIL import ImageFont

    candidatas = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    for caminho in candidatas:
        if Path(caminho).exists():
            return ImageFont.truetype(caminho, tamanho)
    try:
        return ImageFont.load_default(size=tamanho)
    except TypeError:  # Pillow antigo: só existe a fonte pequena padrão
        return ImageFont.load_default()


def _quebrar_linhas(texto, draw, fonte, largura_max):
    linhas, atual = [], ""
    for palavra in texto.split():
        teste = f"{atual} {palavra}".strip()
        if atual and draw.textlength(teste, font=fonte) > largura_max:
            linhas.append(atual)
            atual = palavra
        else:
            atual = teste
    if atual:
        linhas.append(atual)
    return linhas


def _poster_com_pillow(titulo, destino):
    from PIL import Image, ImageDraw

    largura, altura = 400, 600
    topo, base = _cores(titulo)
    img = Image.new("RGB", (largura, altura))
    draw = ImageDraw.Draw(img)
    for y in range(altura):
        t = y / (altura - 1)
        cor = tuple(int(topo[i] + (base[i] - topo[i]) * t) for i in range(3))
        draw.line([(0, y), (largura, y)], fill=cor)
    draw.rectangle([16, 16, largura - 17, altura - 17], outline=(255, 255, 255), width=3)

    pequena, grande = _fonte(18), _fonte(36)
    draw.text((largura / 2, 52), "TEATRO TPE", font=pequena, fill=(255, 255, 255), anchor="mm")
    linhas = _quebrar_linhas(titulo, draw, grande, largura - 90)
    altura_linha = 48
    y = altura / 2 - altura_linha * len(linhas) / 2
    for linha in linhas:
        draw.text((largura / 2, y), linha, font=grande, fill=(255, 255, 255), anchor="mm")
        y += altura_linha
    draw.text((largura / 2, altura - 52), "PÔSTER DE TESTE", font=pequena, fill=(255, 255, 255), anchor="mm")
    img.save(destino, "PNG")


def _poster_sem_pillow(titulo, destino, largura=300, altura=450):
    """Plano B sem dependências: degradê com moldura (sem texto), PNG escrito à mão."""
    topo, base = _cores(titulo)
    linhas = []
    for y in range(altura):
        t = y / (altura - 1)
        cor = bytes(int(topo[i] + (base[i] - topo[i]) * t) for i in range(3))
        linha = bytearray(b"\x00")  # filtro "nenhum" da linha
        for x in range(largura):
            borda = x < 10 or x >= largura - 10 or y < 10 or y >= altura - 10
            linha += b"\xff\xff\xff" if borda else cor
        linhas.append(bytes(linha))

    def bloco(tipo, dados):
        corpo = tipo + dados
        return struct.pack(">I", len(dados)) + corpo + struct.pack(">I", zlib.crc32(corpo) & 0xFFFFFFFF)

    png = (
        b"\x89PNG\r\n\x1a\n"
        + bloco(b"IHDR", struct.pack(">IIBBBBB", largura, altura, 8, 2, 0, 0, 0))
        + bloco(b"IDAT", zlib.compress(b"".join(linhas), 9))
        + bloco(b"IEND", b"")
    )
    Path(destino).write_bytes(png)


def gerar_poster(titulo, pasta_uploads):
    nome = f"{uuid4().hex}.png"
    destino = pasta_uploads / nome
    try:
        _poster_com_pillow(titulo, destino)
    except ImportError:
        _poster_sem_pillow(titulo, destino)
    return nome


def copiar_poster(nome_origem, pasta_uploads):
    """Usa uma imagem sua de dados_teste/posters; devolve None se não der."""
    origem = PASTA_DADOS / "posters" / nome_origem
    if not origem.is_file() or origem.suffix.lower() not in EXTENSOES_POSTER:
        print(f"    aviso: pôster '{nome_origem}' não encontrado (ou extensão inválida); gerando um.")
        return None
    nome = f"{uuid4().hex}{origem.suffix.lower()}"
    shutil.copyfile(origem, pasta_uploads / nome)
    return nome


def remover_arquivo(nome, pasta_uploads):
    if nome:
        try:
            (pasta_uploads / nome).unlink()
        except FileNotFoundError:
            pass


# ------------------------------------------------------------------- dados
def calcular_datas(item, agora):
    hora, minuto = (int(p) for p in item.get("hora", "20:00").split(":"))
    base = agora.replace(hour=hora, minute=minuto, second=0, microsecond=0)
    dias = sorted(set(int(d) for d in item["dias"]))
    if not dias or dias[0] < 1:
        raise ValueError("'dias' deve ter pelo menos um valor e todos >= 1")
    return [base + timedelta(days=d) for d in dias]


def apagar_peca(peca, pasta_uploads):
    for sessao in list(peca.sessoes):
        for agendamento in list(sessao.agendamentos):
            db.session.delete(agendamento)
    db.session.commit()
    poster = peca.poster_filename
    peca.excluir()
    remover_arquivo(poster, pasta_uploads)


def carregar(arquivo, limpar):
    dados = json.loads(Path(arquivo).read_text(encoding="utf-8"))
    pasta_uploads = Path(app.config["UPLOAD_FOLDER"])
    pasta_uploads.mkdir(parents=True, exist_ok=True)
    agora = datetime.now()
    total = {"pecas": 0, "sessoes": 0, "reservas": 0, "puladas": 0}

    existentes = {p.titulo: p for p in Peca.listar()}
    for item in dados["pecas"]:
        titulo = item["titulo"]
        print(f"- {titulo}")

        if titulo in existentes:
            if not limpar:
                print("    já existe, pulando (use --limpar para recarregar)")
                total["puladas"] += 1
                continue
            apagar_peca(existentes[titulo], pasta_uploads)
            print("    versão antiga apagada")

        try:
            datas = calcular_datas(item, agora)
        except (KeyError, ValueError) as erro:
            print(f"    ERRO nas datas: {erro}; peça ignorada")
            total["puladas"] += 1
            continue

        mes = item.get("mes") or MESES_PT[datas[0].month - 1]
        if mes not in Peca.MESES:
            print(
                f"    aviso: o mês '{mes}' não está em Peca.MESES (confira a grafia no "
                "models.py, ex.: 'Setmebro' em vez de 'Setembro'); peça ignorada"
            )
            total["puladas"] += 1
            continue

        poster = copiar_poster(item["poster"], pasta_uploads) if item.get("poster") else None
        if poster is None:
            poster = gerar_poster(titulo, pasta_uploads)

        try:
            peca = Peca.criar(
                titulo=titulo,
                sinopse=item["sinopse"],
                ficha_tecnica=item["ficha_tecnica"],
                faixa_etaria=item["faixa_etaria"],
                duracao_minutos=int(item["duracao_minutos"]),
                mes=mes,
                poster_filename=poster,
            )
        except KeyError as erro:
            remover_arquivo(poster, pasta_uploads)
            print(f"    ERRO: campo obrigatório ausente no arquivo: {erro}")
            total["puladas"] += 1
            continue
        except ValueError as erro:
            remover_arquivo(poster, pasta_uploads)
            print(f"    ERRO ao criar a peça: {erro}")
            total["puladas"] += 1
            continue

        sessoes = [SessaoData.agendar(peca, data) for data in datas]
        total["pecas"] += 1
        total["sessoes"] += len(sessoes)

        for sessao in sessoes[: int(item.get("reservadas", 0))]:
            try:
                Agendamento.solicitar(sessao, 30, ESCOLA_TESTE)
                total["reservas"] += 1
            except ValueError as erro:
                print(f"    aviso: reserva de teste não criada: {erro}")

        print(f"    {mes} | {len(sessoes)} sessões | pôster {poster}")

    print(
        f"\nPronto: {total['pecas']} peça(s), {total['sessoes']} sessão(ões), "
        f"{total['reservas']} reserva(s) de teste; {total['puladas']} pulada(s)."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Carrega dados de teste no Teatro TPE.")
    parser.add_argument("--arquivo", default=str(ARQUIVO_PADRAO), help="JSON com as peças")
    parser.add_argument("--limpar", action="store_true", help="apaga e recria as peças do arquivo")
    argumentos = parser.parse_args()
    with app.app_context():
        carregar(argumentos.arquivo, argumentos.limpar)
