"""Agendamento de sessões exclusivas (UC1 - Solicitar Agendamento).
 agendamento é do tipo db model, estamos modelando uma tabela de banco de dados,
  é como uma camada de tradução, aqui é o local principal de comunicação com o banco de dados. 

"""
import re
from datetime import datetime

from flask import current_app
from sqlalchemy.exc import IntegrityError

from model.models import SessaoData, db


class Agendamento(db.Model):
    CONFIRMADO = "CONFIRMADO"
    CANCELADO = "CANCELADO"
    # Peca não tem coluna de lotação; este é o valor padrão por sessão.
    # Para mudar sem editar o código: app.config["LOTACAO_SESSAO"] = 150
    LOTACAO_PADRAO = 100

    id = db.Column(db.Integer, primary_key=True)
    sessao_id = db.Column(
        db.Integer, db.ForeignKey("sessao_data.id"), nullable=False
    )
    escola_nome = db.Column(db.String(150), nullable=False)
    escola_cnpj = db.Column(db.String(14), nullable=False)
    escola_email = db.Column(db.String(150), nullable=False)
    escola_telefone = db.Column(db.String(20), nullable=False)
    responsavel = db.Column(db.String(150), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default=CONFIRMADO)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.now)

    # backref evita ter que editar SessaoData: sessao.agendamentos fica disponível.
    sessao = db.relationship(
        "SessaoData", backref=db.backref("agendamentos", lazy=True)
    )

    # Sessão exclusiva: no máximo um agendamento confirmado por sessão.
    # O índice parcial garante isso mesmo se duas escolas confirmarem ao mesmo tempo.
    __table_args__ = (
        db.Index(
            "uq_agendamento_sessao_confirmado",
            "sessao_id",
            unique=True,
            sqlite_where=db.text("status = 'CONFIRMADO'"),
            postgresql_where=db.text("status = 'CONFIRMADO'"),
        ),
    )
#metodos pra interagir com o banco de dados

    @classmethod
    def lotacao(cls):
        return current_app.config.get("LOTACAO_SESSAO", cls.LOTACAO_PADRAO)

    @classmethod
    def buscar(cls, agendamento_id):
        return db.session.get(cls, agendamento_id)

    @classmethod
    def sessao_reservada(cls, sessao):
        return (
            cls.query.filter_by(sessao_id=sessao.id, status=cls.CONFIRMADO).first()
            is not None
        )

    @classmethod
    def sessoes_disponiveis(cls, peca):
        """Datas futuras da peça que ainda não foram reservadas (passo 4)."""
        return (
            SessaoData.query.filter(
                SessaoData.peca_id == peca.id,
                SessaoData.data_hora >= datetime.now(),
                ~SessaoData.agendamentos.any(cls.status == cls.CONFIRMADO),
            )
            .order_by(SessaoData.data_hora)
            .all()
        )

    @classmethod
    def verificar_disponibilidade(cls, sessao, quantidade):
        """<<include>> Validar Disponibilidade (passo 7).

        Levanta ValueError com o motivo quando a data não pode ser reservada
        (fluxo alternativo 6a).
        """
        if sessao is None:
            raise ValueError("Selecione uma data no calendário.")
        if quantidade is None or quantidade < 1:
            raise ValueError("Informe a quantidade de ingressos (mínimo 1).")
        if sessao.data_hora < datetime.now():
            raise ValueError("A data escolhida já passou.")
        if cls.sessao_reservada(sessao):
            raise ValueError("A data escolhida não está disponível.")
        lotacao = cls.lotacao()
        if quantidade > lotacao:
            raise ValueError(
                f"A quantidade informada ({quantidade}) excede a lotação "
                f"da sessão ({lotacao})."
            )

    @staticmethod
    def validar_escola(dados):
        """Passo 10: valida os dados da escola.

        Retorna {campo: mensagem}; dicionário vazio quando tudo está válido
        (fluxo alternativo 11a usa as mensagens para indicar o motivo).
        """
        erros = {}
        if len(dados.get("nome", "").strip()) < 3:
            erros["nome"] = "Informe o nome da escola (mínimo 3 caracteres)."
        if len(re.sub(r"\D", "", dados.get("cnpj", ""))) != 14:
            erros["cnpj"] = "O CNPJ deve ter 14 dígitos."
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", dados.get("email", "").strip()):
            erros["email"] = "Informe um e-mail válido."
        if len(re.sub(r"\D", "", dados.get("telefone", ""))) not in (10, 11):
            erros["telefone"] = "Informe um telefone com DDD (10 ou 11 dígitos)."
        if len(dados.get("responsavel", "").strip()) < 3:
            erros["responsavel"] = "Informe o nome do responsável."
        return erros

    @classmethod
    def solicitar(cls, sessao, quantidade, dados):
        """Passo 12: reserva a sessão para a escola."""
        cls.verificar_disponibilidade(sessao, quantidade)
        if cls.validar_escola(dados):
            raise ValueError("Corrija os dados da escola antes de confirmar.")

        agendamento = cls(
            sessao=sessao,
            quantidade=quantidade,
            escola_nome=dados["nome"].strip(),
            escola_cnpj=re.sub(r"\D", "", dados["cnpj"]),
            escola_email=dados["email"].strip(),
            escola_telefone=re.sub(r"\D", "", dados["telefone"]),
            responsavel=dados["responsavel"].strip(),
        )
        db.session.add(agendamento)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            raise ValueError("A data escolhida não está disponível.")
        return agendamento