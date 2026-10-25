"""Controller do UC1 - Solicitar Agendamento (ator: Escola).

    from controller.agendamentoController import agendamentos_bp    
    app.register_blueprint(agendamentos_bp)
    lógica do sistema, as operações 

    
"""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
 
from model.agendamentos import Agendamento
from model.models import Peca, SessaoData, db
 
agendamentos_bp = Blueprint("agendamentos", __name__, url_prefix="/agendamentos")
 
CAMPOS_ESCOLA = ("nome", "cnpj", "email", "telefone", "responsavel")
 
 
def _inteiro(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None
 
 
def _dados_escola(origem):
    return {campo: origem.get(campo, "").strip() for campo in CAMPOS_ESCOLA}
 
 
def _carregar_sessao(valores):
    """Lê sessao_id e quantidade enviados pelas páginas do fluxo."""
    sessao_id = _inteiro(valores.get("sessao_id"))
    sessao = db.session.get(SessaoData, sessao_id) if sessao_id else None
    return sessao, _inteiro(valores.get("quantidade"))
 
 
def _voltar_ao_calendario(sessao, erro):
    """Fluxo alternativo 6a: informa o problema e mostra o calendário de novo."""
    flash(str(erro), "danger")
    if sessao is None:
        return redirect(url_for("agendamentos.catalogo"))
    return redirect(url_for("agendamentos.calendario", peca_id=sessao.peca_id))
 
 
# Passos 1-3: a escola acessa o site e escolhe a peça no catálogo
@agendamentos_bp.route("/")
def catalogo():
    return render_template("agendamentoInterface/catalogo.html", pecas=Peca.listar())
 
 
# Passo 4: o sistema exibe o calendário com as datas disponíveis
@agendamentos_bp.route("/pecas/<int:peca_id>/calendario")
def calendario(peca_id):
    peca = Peca.buscar(peca_id)
    if peca is None:
        abort(404)
    return render_template(
        "agendamentoInterface/calendario.html",
        peca=peca,
        sessoes=Agendamento.sessoes_disponiveis(peca),
        quantidade=request.args.get("quantidade", ""),
        lotacao=Agendamento.lotacao(),
    )
 
 
# Passos 5-7: escolhe a data, informa a quantidade e o sistema executa
# <<include>> Validar Disponibilidade
@agendamentos_bp.route("/pecas/<int:peca_id>/validar", methods=["POST"])
def validar_disponibilidade(peca_id):
    peca = Peca.buscar(peca_id)
    if peca is None:
        abort(404)
 
    sessao, quantidade = _carregar_sessao(request.form)
    if sessao is not None and sessao.peca_id != peca.id:
        abort(404)
 
    try:
        Agendamento.verificar_disponibilidade(sessao, quantidade)
    except ValueError as erro:
        # 6a: data indisponível -> informa e volta ao calendário
        flash(str(erro), "danger")
        return redirect(
            url_for(
                "agendamentos.calendario",
                peca_id=peca.id,
                quantidade=request.form.get("quantidade", ""),
            )
        )
 
    return redirect(
        url_for("agendamentos.formulario", sessao_id=sessao.id, quantidade=quantidade)
    )
 
 
# Passo 8: o sistema exibe o formulário para agendamento
@agendamentos_bp.route("/formulario")
def formulario():
    sessao, quantidade = _carregar_sessao(request.args)
    try:
        Agendamento.verificar_disponibilidade(sessao, quantidade)
    except ValueError as erro:
        return _voltar_ao_calendario(sessao, erro)
 
    return render_template(
        "agendamentoInterface/formulario.html",
        sessao=sessao,
        quantidade=quantidade,
        dados=_dados_escola(request.args),
        erros={},
    )
 
 
# Passos 9-11: a escola preenche os dados, o sistema valida (10) e mostra
# os dados para a escola confirmar (11)
@agendamentos_bp.route("/revisar", methods=["POST"])
def revisar():
    sessao, quantidade = _carregar_sessao(request.form)
    try:
        Agendamento.verificar_disponibilidade(sessao, quantidade)
    except ValueError as erro:
        return _voltar_ao_calendario(sessao, erro)
 
    dados = _dados_escola(request.form)
    erros = Agendamento.validar_escola(dados)
    if erros:
        # 11a: informação inválida -> volta ao formulário indicando o motivo
        flash("Há campos com erro. Corrija-os e envie novamente.", "danger")
        return render_template(
            "agendamentoInterface/formulario.html",
            sessao=sessao,
            quantidade=quantidade,
            dados=dados,
            erros=erros,
        )
 
    return render_template(
        "agendamentoInterface/confirmar.html",
        sessao=sessao,
        quantidade=quantidade,
        dados=dados,
    )
 
 
# Passo 12: o sistema autoriza o agendamento e finaliza a operação
@agendamentos_bp.route("/confirmar", methods=["POST"])
def confirmar():
    sessao, quantidade = _carregar_sessao(request.form)
    try:
        agendamento = Agendamento.solicitar(
            sessao, quantidade, _dados_escola(request.form)
        )
    except ValueError as erro:
        # outra escola pode ter reservado a data enquanto esta confirmava
        return _voltar_ao_calendario(sessao, erro)
 
    flash("Agendamento confirmado com sucesso.", "success")
    return redirect(
        url_for("agendamentos.sucesso", agendamento_id=agendamento.id)
    )
 
 
@agendamentos_bp.route("/<int:agendamento_id>/sucesso")
def sucesso(agendamento_id):
    agendamento = Agendamento.buscar(agendamento_id)
    if agendamento is None:
        abort(404)
    return render_template("agendamentoInterface/sucesso.html", agendamento=agendamento)
 