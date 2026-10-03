from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class PasswordHasher:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Hash e verificação de senha via bcrypt (passlib) — usado por
    RegisterUserUseCase, LoginUseCase, ChangePasswordUseCase e
    ResetPasswordUseCase.
    """

    def hash(self, plain_password: str) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Gera o hash bcrypt (com salt aleatório embutido) de uma
        senha em texto puro — nunca a própria senha é persistida.
        """
        return _pwd_context.hash(plain_password)

    def verify(self, plain_password: str, password_hash: str) -> bool:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Confere se `plain_password` corresponde ao hash
        armazenado, sem nunca decodificar o hash de volta em texto puro
        (bcrypt é de mão única).
        """
        return _pwd_context.verify(plain_password, password_hash)
