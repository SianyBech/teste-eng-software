from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash
from model.models import db

class Usuario(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False)

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def verificar_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

    @classmethod
    def buscar_por_username(cls, username):
        return cls.query.filter_by(username=username).first()

    @classmethod
    def criar_gestor_padrao(cls, username="admin", senha="123"):
        if not cls.buscar_por_username(username):
            gestor = cls(username=username)
            gestor.set_senha(senha)
            db.session.add(gestor)
            db.session.commit()
            return gestor
        return None