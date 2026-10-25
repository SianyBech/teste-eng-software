from datetime import datetime
from pathlib import Path
from uuid import uuid4
from flask_login import login_required
from sqlalchemy import or_, cast, String

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from werkzeug.utils import secure_filename

from model.models import Peca, SessaoData, db

pecas_bp = Blueprint("pecas", __name__)
EXTENSOES_POSTER = {"jpg", "jpeg", "png", "gif", "webp"}


@pecas_bp.route("/pecas")
def listar_pecas():
    termo = request.args.get("q", "").strip()           #leitura do campo de pesquisa
    pecas = Peca.listar()
    if termo:               
            pecas = [p for p in pecas if termo.lower() in p.titulo.lower()] 
    return render_template("pecaInterface/index.html", pecas=pecas)


def salvar_poster(arquivo):
    if not arquivo or not arquivo.filename:
        return None

    nome_seguro = secure_filename(arquivo.filename)
    extensao = nome_seguro.rsplit(".", 1)[-1].lower() if "." in nome_seguro else ""
    if extensao not in EXTENSOES_POSTER:
        raise ValueError("Envie uma imagem JPG, PNG, GIF ou WebP.")

    nome_arquivo = f"{uuid4().hex}.{extensao}"
    pasta_uploads = Path(current_app.config["UPLOAD_FOLDER"])
    pasta_uploads.mkdir(parents=True, exist_ok=True)
    arquivo.save(pasta_uploads / nome_arquivo)
    return nome_arquivo


def remover_poster(nome_arquivo):
    if nome_arquivo:
        caminho = Path(current_app.config["UPLOAD_FOLDER"]) / nome_arquivo
        try:
            caminho.unlink()
        except FileNotFoundError:
            pass


@pecas_bp.route("/uploads/<path:nome_arquivo>")
def servir_poster(nome_arquivo):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], nome_arquivo)


@pecas_bp.route("/pecas/criar", methods=["GET", "POST"])
@login_required
def criar_peca():
    if request.method == "POST":
        titulo = request.form.get("titulo", "").strip()
        sinopse = request.form.get("sinopse", "").strip()
        ficha_tecnica = request.form.get("ficha_tecnica", "").strip()
        faixa_etaria = request.form.get("faixa_etaria", "").strip()
        mes = request.form.get("mes", "").strip()
        try:
            duracao_minutos = int(request.form.get("duracao_minutos", ""))
        except ValueError:
            duracao_minutos = 0

        nome_poster = None
        try:
            nome_poster = salvar_poster(request.files.get("poster"))
            Peca.criar(
                titulo,
                sinopse,
                ficha_tecnica,
                faixa_etaria,
                duracao_minutos,
                mes,
                poster_filename=nome_poster,
            )
        except ValueError as erro:
            remover_poster(nome_poster)
            flash(str(erro), "danger")
            return render_template("pecaInterface/criar.html", peca=None)

        flash("Peça cadastrada com sucesso.", "success")
        return redirect(url_for("pecas.listar_pecas"))

    return render_template("pecaInterface/criar.html", peca=None)


@pecas_bp.route("/pecas/<int:peca_id>/editar", methods=["GET", "POST"])
@login_required
def editar_peca(peca_id):
    peca = Peca.buscar(peca_id)
    if peca is None:
        abort(404)

    if request.method == "POST":
        try:
            duracao_minutos = int(request.form.get("duracao_minutos", ""))
        except ValueError:
            duracao_minutos = 0

        nome_poster = None
        try:
            nome_poster = salvar_poster(request.files.get("poster"))
            nome_poster_antigo = peca.poster_filename
            peca.atualizar(
                titulo=request.form.get("titulo", ""),
                sinopse=request.form.get("sinopse", ""),
                ficha_tecnica=request.form.get("ficha_tecnica", ""),
                faixa_etaria=request.form.get("faixa_etaria", ""),
                duracao_minutos=duracao_minutos,
                mes=request.form.get("mes", "").strip(),
                poster_filename=nome_poster,
            )
        except ValueError as erro:
            remover_poster(nome_poster)
            flash(str(erro), "danger")
            return render_template("pecaInterface/editar.html", peca=peca)

        if nome_poster:
            remover_poster(nome_poster_antigo)
        flash("Peça atualizada com sucesso.", "success")
        return redirect(url_for("pecas.listar_pecas"))

    return render_template("pecaInterface/editar.html", peca=peca)


@pecas_bp.route("/pecas/<int:peca_id>/excluir", methods=["POST"])
@login_required
def excluir_peca(peca_id):
    peca = Peca.buscar(peca_id)
    if peca is None:
        abort(404)

    nome_poster = peca.poster_filename
    peca.excluir()
    remover_poster(nome_poster)
    flash("Peça e suas sessões foram excluídas.", "success")
    return redirect(url_for("pecas.listar_pecas"))


@pecas_bp.route("/pecas/<int:peca_id>/calendario", methods=["GET", "POST"])
@login_required
def gerenciar_calendario(peca_id):
    peca = Peca.buscar(peca_id)
    if peca is None:
        abort(404)

    if request.method == "POST":
        try:
            data_hora = datetime.fromisoformat(request.form.get("data_hora", ""))
        except ValueError:
            flash("Informe uma data e um horário válidos.", "danger")
            return redirect(url_for("pecas.gerenciar_calendario", peca_id=peca.id))

        SessaoData.agendar(peca, data_hora)
        flash("Sessão adicionada ao calendário.", "success")
        return redirect(url_for("pecas.gerenciar_calendario", peca_id=peca.id))

    return render_template(
        "pecaInterface/calendario.html",
        peca=peca,
        sessoes=peca.listar_sessoes(),
    )


@pecas_bp.route(
    "/pecas/<int:peca_id>/sessoes/<int:sessao_id>/excluir",
    methods=["POST"],
)
@login_required
def excluir_sessao(peca_id, sessao_id):
    peca = Peca.buscar(peca_id)
    if peca is None:
        abort(404)

    sessao = db.session.get(SessaoData, sessao_id)
    if sessao is None or sessao.peca_id != peca.id:
        abort(404)

    sessao.excluir()
    flash("Sessão excluída.", "success")
    return redirect(url_for("pecas.gerenciar_calendario", peca_id=peca.id))
