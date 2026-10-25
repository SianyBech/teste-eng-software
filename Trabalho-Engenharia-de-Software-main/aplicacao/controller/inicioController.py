from flask import Blueprint, render_template, request, redirect, url_for


inicio_bp = Blueprint("inicio", __name__)


@inicio_bp.route("/")
def index():
    termo = request.args.get("q","").strip() #leitura do campo de busca
    if termo:                                   
        return redirect(url_for("pecas.listar_pecas", q=termo))
    return render_template("inicioInterface/index.html")