from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required, login_user, logout_user
from model.usuario import Usuario

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        senha = request.form.get("senha", "").strip()

        usuario = Usuario.buscar_por_username(username)
        if usuario and usuario.verificar_senha(senha):
            login_user(usuario)
            flash(f"Bem-vindo(a), {usuario.username}!", "success")

            proxima_pagina = request.args.get("next") or url_for("pecas.listar_pecas")
            return redirect(proxima_pagina)

        flash("Utilizador ou palavra-passe incorretos.", "danger")

    return render_template("authInterface/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Sessão encerrada com sucesso.", "info")
    return redirect(url_for("auth.login"))