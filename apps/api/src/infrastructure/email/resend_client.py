import asyncio

import resend

from src.infrastructure.config import get_settings


class ResendEmailClient:
    """
    Autor: Carlos Adriano
    Data: 2026-08-16
    Descrição: Envia o email transacional de reset de senha via Resend, com
    link para `FRONTEND_URL/reset-password?token=...`. O SDK do Resend é
    síncrono — o envio roda numa thread separada (`asyncio.to_thread`) para
    não bloquear o event loop do FastAPI. Remetente configurável via
    `MAIL_FROM_ADDRESS`/`MAIL_FROM_NAME` (precisa ser um domínio/endereço
    verificado na conta Resend, senão o envio falha).
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._frontend_url = settings.FRONTEND_URL
        self._from_email = f"{settings.MAIL_FROM_NAME} <{settings.MAIL_FROM_ADDRESS}>"
        if settings.RESEND_API_KEY:
            resend.api_key = settings.RESEND_API_KEY

    async def send_password_reset_email(self, to_email: str, token: str, language: str) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Monta e envia o email de reset de senha no idioma do
        usuário. Chamado por RequestPasswordResetUseCase só quando a conta
        existe e tem senha local (nunca revela isso ao chamador).
        """
        reset_url = f"{self._frontend_url}/reset-password?token={token}"
        subject, body = self._build_content(reset_url, language)
        await asyncio.to_thread(
            resend.Emails.send,
            {"from": self._from_email, "to": [to_email], "subject": subject, "html": body},
        )

    def _build_content(self, reset_url: str, language: str) -> tuple[str, str]:
        """
        Autor: Carlos Adriano
        Data: 2026-09-09
        Descrição: Monta assunto e textos do email de reset, em PT-BR
        (default) ou EN conforme `language` (RN-10). O HTML em si é
        renderizado por `_render_email_html`, que aplica a identidade
        visual do app (cores/fonte de apps/web/src/styles.css) — aqui só
        ficam os textos já traduzidos.
        """
        if language == "en":
            subject = "Reset your Amezia password"
            heading = "Reset your password"
            intro = (
                "We received a request to reset your Amezia password. "
                "Click the button below to choose a new one:"
            )
            button_text = "Reset password"
            expiry_text = "This link expires in 30 minutes."
            ignore_text = "If you didn't request this, you can safely ignore this email."
        else:
            subject = "Redefinir sua senha Amezia"
            heading = "Redefinir sua senha"
            intro = (
                "Recebemos um pedido para redefinir sua senha do Amezia. "
                "Clique no botão abaixo para escolher uma nova:"
            )
            button_text = "Redefinir senha"
            expiry_text = "Este link expira em 30 minutos."
            ignore_text = "Se você não pediu isso, pode ignorar este email com segurança."

        body = self._render_email_html(reset_url, heading, intro, button_text, expiry_text, ignore_text)
        return subject, body

    def _render_email_html(
        self,
        reset_url: str,
        heading: str,
        intro: str,
        button_text: str,
        expiry_text: str,
        ignore_text: str,
    ) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-09-09
        Descrição: Renderiza o HTML do email de reset a partir dos textos
        já traduzidos por `_build_content`, isolando o layout/estilo
        (idêntico entre PT-BR e EN) do conteúdo textual. Layout em tabelas
        (não flexbox/grid) por compatibilidade com clientes de email como
        Outlook; cores/fonte seguem a identidade visual do app
        (apps/web/src/styles.css: --accent #4f46e5, --t1 #0f172a,
        --t2 #475569, --bg #e9edf3).
        """
        return f"""\
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#e9edf3;padding:32px 16px;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <tr>
    <td align="center">
      <table role="presentation" width="480" cellpadding="0" cellspacing="0" style="max-width:480px;width:100%;background-color:#ffffff;border-radius:12px;overflow:hidden;">
        <tr>
          <td style="padding:32px 40px 8px;text-align:center;">
            <img src="https://amezia.com.br/assets/imagens/logo.png" alt="Amezia" width="56" style="display:block;margin:0 auto 16px;" />
            <h1 style="margin:0;font-size:20px;color:#0f172a;">{heading}</h1>
          </td>
        </tr>
        <tr>
          <td style="padding:8px 40px 32px;text-align:center;">
            <p style="margin:0 0 24px;font-size:15px;line-height:1.5;color:#475569;">{intro}</p>
            <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 auto;">
              <tr>
                <td style="background-color:#4f46e5;background-image:linear-gradient(135deg,#4f46e5,#2563eb);border-radius:8px;">
                  <a href="{reset_url}" style="display:inline-block;padding:12px 28px;font-size:15px;font-weight:600;color:#ffffff;text-decoration:none;">{button_text}</a>
                </td>
              </tr>
            </table>
            <p style="margin:24px 0 0;font-size:13px;color:#94a3b8;">{expiry_text}</p>
            <p style="margin:4px 0 0;font-size:13px;color:#94a3b8;">{ignore_text}</p>
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>"""
