MESSAGES: dict[str, str] = {
    "welcome.intro": (
        "👋 Seu número foi vinculado à sua conta Amezia! Eu sou o assistente financeiro "
        "por aqui — registro seus gastos, respondo perguntas sobre suas finanças e te "
        "ajudo a acompanhar seus relatórios, tudo pelo WhatsApp."
    ),
    "menu.title": "Olá! Eu sou o assistente financeiro da Amezia. O que você quer fazer?",
    "menu.options": (
        "1️⃣ Registrar um gasto\n"
        "2️⃣ Conversar com a IA\n"
        "3️⃣ Consultar relatório\n"
        "4️⃣ Enviar feedback\n\n"
        "Responda com o número da opção ou volte aqui a qualquer momento enviando *0* ou *menu*."
    ),
    "menu.invalid_option": "Não entendi essa opção 🤔",
    "expense.entered": (
        "Modo Registrar ativado. Me conte o que você gastou — em texto ou áudio "
        "(ex.: \"gastei 50 no mercado\"). Envie *0* ou *menu* para voltar."
    ),
    "chat.entered": (
        "Modo Chat ativado. Pode perguntar o que quiser sobre suas finanças. "
        "Envie *0* ou *menu* para voltar."
    ),
    "report.link_message": (
        "📊 Suas despesas este mês somam R$ {total}. Veja o painel completo, com filtros e "
        "tudo, no link abaixo:\n{url}\n\nO link expira em 1 hora. Envie *0* ou *menu* para voltar."
    ),
    "expense.confirmation": "✅ Gasto registrado: R$ {amount} em {category} ({date}).",
    "expense.parse_failed": (
        "Não consegui entender esse gasto 😕 Tente algo como \"gastei 50 no mercado\"."
    ),
    "expense.reply_with_text": "Responda em texto, por favor 🙂",
    "expense.choose_category": (
        "Não achei uma categoria certa pra esse gasto. Escolha uma das opções abaixo pelo número, "
        "ou digite o nome de uma categoria nova:\n\n{options}"
    ),
    "expense.category_dedup_confirm": (
        "Você já tem uma categoria parecida: *{existing}*. Quer usar ela? Responda *sim* para "
        "usar, ou qualquer outra coisa para criar uma categoria nova mesmo."
    ),
    "expense.installment_choice": (
        "Essa despesa é:\n1) Só essa vez\n2) Parcelada\n3) Recorrente\n\nResponda com o número."
    ),
    "expense.installment_choice_invalid": "Não entendi 🤔 Responda com 1, 2 ou 3.",
    "expense.installment_amount_prompt": (
        "Você mencionou R$ {total} em {count}x. Qual o valor de cada parcela?"
    ),
    "expense.installment_amount_invalid": "Não entendi esse valor 🤔 Digite só o número (ex.: 60 ou 60,50).",
    "expense.installment_count_prompt": "Em quantas parcelas (2 a {max})?",
    "expense.installment_count_invalid": "Número de parcelas inválido. Responda um número de 2 a {max}.",
    "expense.recurrence_frequency_prompt": (
        "Com que frequência ela se repete?\n1) Semanal\n2) Mensal\n3) Anual\n\nResponda com o número."
    ),
    "expense.recurrence_frequency_invalid": "Não entendi 🤔 Responda com 1, 2 ou 3.",
    "expense.start_date_confirm": (
        "Início em {date}. Confirma? Responda *sim* ou digite outra data (formato DD/MM)."
    ),
    "expense.start_date_invalid": (
        "Não entendi essa data 🤔 Digite no formato DD/MM (ex.: 15/03), ou *sim* pra manter a data original."
    ),
    "chat.error": "Não consegui gerar uma resposta agora. Tente de novo em instantes.",
    "chat.usageLimitExceeded": (
        "Você atingiu o limite de conversas com a IA do seu plano este mês. "
        "Faça upgrade no app (Configurações > Planos) para continuar conversando sem limite."
    ),
    "feedback.prompt": "Pode mandar sua sugestão ou crítica em uma única mensagem 🙂",
    "feedback.thanks": "Obrigado pelo feedback! Ele foi enviado para a nossa equipe.",
    "common.audio_not_supported": "Áudio só é aceito no modo Registrar. Envie *1* para entrar nele.",
    "common.unlinked_number": (
        "Não encontrei nenhuma conta Amezia vinculada a este número. "
        "Vincule seu WhatsApp em /settings/profile no app para usar o bot."
    ),
    "common.generic_error": "Algo deu errado por aqui. Tente novamente em instantes.",
    "common.plan_limit_reached": (
        "Você atingiu o limite de mensagens do bot este mês no seu plano atual. "
        "Faça upgrade em /settings/plans no app para continuar usando sem limite."
    ),
}
