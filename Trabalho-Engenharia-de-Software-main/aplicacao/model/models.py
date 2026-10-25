from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Peca(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(150), nullable=False)
    sinopse = db.Column(db.Text, nullable=False)
    ficha_tecnica = db.Column(db.Text, nullable=False, default="")
    faixa_etaria = db.Column(db.String(30), nullable=False)
    duracao_minutos = db.Column(db.Integer, nullable=False)
    mes = db.Column(db.String(20), nullable = False)
    poster_filename = db.Column(db.String(255), nullable=True)
    sessoes = db.relationship(
        "SessaoData",
        back_populates="peca",
        cascade="all, delete-orphan",
    )
    MESES = {"Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"}
    FAIXAS_ETARIAS = {"Livre", "10", "12", "14", "16", "18"}

    @classmethod
    def listar(cls):
        return cls.query.order_by(cls.titulo).all()

    @classmethod
    def buscar(cls, peca_id):
        return db.session.get(cls, peca_id)

    @classmethod
    def criar(
        cls,
        titulo,
        sinopse,
        ficha_tecnica,
        faixa_etaria,
        duracao_minutos,
        mes,
        poster_filename=None,
    ):
        titulo = titulo.strip()
        sinopse = sinopse.strip()
        ficha_tecnica = ficha_tecnica.strip()
        faixa_etaria = faixa_etaria.strip()
        mes = (mes or "").strip()

        if (
            not titulo
            or len(titulo) > 150
            or not sinopse
            or not ficha_tecnica
            or faixa_etaria not in cls.FAIXAS_ETARIAS
            or duracao_minutos <= 0
            or mes not in cls.MESES
        ):
            raise ValueError(
                "Preencha os campos, escolha uma faixa etária válida e informe "
                "uma duração válida. A ficha técnica também é obrigatória."
            )

        peca = cls(
            titulo=titulo,
            sinopse=sinopse,
            ficha_tecnica=ficha_tecnica,
            faixa_etaria=faixa_etaria,
            duracao_minutos=duracao_minutos,
            mes=mes,
            poster_filename=poster_filename,
        )
        db.session.add(peca)
        db.session.commit()
        return peca

    def atualizar(
        self,
        titulo,
        sinopse,
        ficha_tecnica,
        faixa_etaria,
        duracao_minutos,
        mes,
        poster_filename=None,
    ):
        titulo = titulo.strip()
        sinopse = sinopse.strip()
        ficha_tecnica = ficha_tecnica.strip()
        faixa_etaria = faixa_etaria.strip()
        mes = (mes or "").strip()

        if (
            not titulo
            or len(titulo) > 150
            or not sinopse
            or not ficha_tecnica
            or faixa_etaria not in self.FAIXAS_ETARIAS
            or duracao_minutos <= 0
            or mes not in self.MESES
        ):
            raise ValueError(
                "Preencha os campos, escolha uma faixa etária válida e informe "
                "uma duração válida. A ficha técnica também é obrigatória."
            )

        self.titulo = titulo
        self.sinopse = sinopse
        self.ficha_tecnica = ficha_tecnica
        self.faixa_etaria = faixa_etaria
        self.duracao_minutos = duracao_minutos
        self.mes = mes
        if poster_filename is not None:
            self.poster_filename = poster_filename
        db.session.commit()
        return self

    def excluir(self):
        for sessao in self.sessoes:
            for agendamento in list(sessao.agendamentos):
                db.session.delete(agendamento)
        db.session.delete(self)
        db.session.commit()

    def listar_sessoes(self):
        return (
            SessaoData.query.filter_by(peca_id=self.id)
            .order_by(SessaoData.data_hora)
            .all()
        )


class SessaoData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    peca_id = db.Column(db.Integer, db.ForeignKey("peca.id"), nullable=False)
    data_hora = db.Column(db.DateTime, nullable=False)
    peca = db.relationship("Peca", back_populates="sessoes")

    @classmethod
    def agendar(cls, peca, data_hora: datetime):
        sessao = cls(peca=peca, data_hora=data_hora)
        db.session.add(sessao)
        db.session.commit()
        return sessao

    def excluir(self):
        for agendamento in list(self.agendamentos):
            db.session.delete(agendamento)
        db.session.delete(self)
        db.session.commit()
