MESSAGES: dict[str, str] = {
    "welcome.intro": (
        "👋 Your number has been linked to your Amezia account! I'm your financial "
        "assistant here — I register your expenses, answer questions about your "
        "finances, and help you check your reports, all through WhatsApp."
    ),
    "menu.title": "Hi! I'm Amezia's financial assistant. What would you like to do?",
    "menu.options": (
        "1️⃣ Register an expense\n"
        "2️⃣ Chat with the AI\n"
        "3️⃣ Check a report\n"
        "4️⃣ Send feedback\n\n"
        "Reply with the option number, or come back here anytime by sending *0* or *menu*."
    ),
    "menu.invalid_option": "I didn't understand that option 🤔",
    "expense.entered": (
        "Register mode activated. Tell me what you spent — in text or audio "
        '(e.g. "I spent 50 on groceries"). Send *0* or *menu* to go back.'
    ),
    "chat.entered": (
        "Chat mode activated. Ask me anything about your finances. "
        "Send *0* or *menu* to go back."
    ),
    "report.link_message": (
        "📊 Your expenses this month add up to R$ {total}. Check out the full panel, filters "
        "and all, at the link below:\n{url}\n\nThe link expires in 1 hour. Send *0* or *menu* "
        "to go back."
    ),
    "expense.confirmation": "✅ Expense registered: R$ {amount} in {category} ({date}).",
    "expense.parse_failed": (
        'I couldn\'t understand that expense 😕 Try something like "I spent 50 on groceries".'
    ),
    "expense.reply_with_text": "Please reply with text 🙂",
    "expense.choose_category": (
        "I couldn't find a good category for that expense. Pick one of the options below by "
        "number, or type the name of a new category:\n\n{options}"
    ),
    "expense.category_dedup_confirm": (
        "You already have a similar category: *{existing}*. Want to use it? Reply *yes* to use "
        "it, or anything else to create a new category anyway."
    ),
    "expense.installment_choice": (
        "Is this expense:\n1) Just this once\n2) In installments\n3) Recurring\n\n"
        "Reply with the number."
    ),
    "expense.installment_choice_invalid": "I didn't understand 🤔 Reply with 1, 2 or 3.",
    "expense.installment_amount_prompt": (
        "You mentioned R$ {total} in {count}x. What's the value of each installment?"
    ),
    "expense.installment_amount_invalid": "I didn't understand that value 🤔 Type just the number (e.g. 60 or 60.50).",
    "expense.installment_count_prompt": "How many installments (2 to {max})?",
    "expense.installment_count_invalid": "Invalid number of installments. Reply a number from 2 to {max}.",
    "expense.recurrence_frequency_prompt": (
        "How often does it repeat?\n1) Weekly\n2) Monthly\n3) Yearly\n\nReply with the number."
    ),
    "expense.recurrence_frequency_invalid": "I didn't understand 🤔 Reply with 1, 2 or 3.",
    "expense.start_date_confirm": (
        "Starting {date}. Confirm? Reply *yes* or type another date (DD/MM format)."
    ),
    "expense.start_date_invalid": (
        "I didn't understand that date 🤔 Type it as DD/MM (e.g. 15/03), or *yes* to keep the original date."
    ),
    "chat.error": "I couldn't generate a reply right now. Please try again shortly.",
    "chat.usageLimitExceeded": (
        "You've reached your plan's monthly AI conversation limit. "
        "Upgrade in the app (Settings > Plans) to keep chatting without limits."
    ),
    "feedback.prompt": "Send your suggestion or feedback in a single message 🙂",
    "feedback.thanks": "Thanks for your feedback! It was sent to our team.",
    "common.audio_not_supported": "Audio is only supported in Register mode. Send *1* to enter it.",
    "common.unlinked_number": (
        "I couldn't find any Amezia account linked to this number. "
        "Link your WhatsApp number at /settings/profile in the app to use the bot."
    ),
    "common.generic_error": "Something went wrong on our end. Please try again shortly.",
    "common.plan_limit_reached": (
        "You've reached this month's bot message limit on your current plan. "
        "Upgrade at /settings/plans in the app to keep using it without limits."
    ),
}
