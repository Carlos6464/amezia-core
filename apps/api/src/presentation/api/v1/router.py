from fastapi import APIRouter

from src.presentation.api.v1.admin.activity_router import router as admin_activity_router
from src.presentation.api.v1.admin.ai_usage_router import router as admin_ai_usage_router
from src.presentation.api.v1.admin.auth_router import router as admin_auth_router
from src.presentation.api.v1.admin.evolution_router import router as admin_evolution_router
from src.presentation.api.v1.admin.feedback_router import router as admin_feedback_router
from src.presentation.api.v1.admin.payments_router import router as admin_payments_router
from src.presentation.api.v1.admin.plan_prices_router import router as admin_plan_prices_router
from src.presentation.api.v1.admin.stats_router import router as admin_stats_router
from src.presentation.api.v1.admin.users_router import router as admin_users_router
from src.presentation.api.v1.ai_usage.router import router as ai_usage_router
from src.presentation.api.v1.auth.router import router as auth_router
from src.presentation.api.v1.bot.router import router as bot_router
from src.presentation.api.v1.categories.router import router as categories_router
from src.presentation.api.v1.conversations.router import router as conversations_router
from src.presentation.api.v1.feedback.router import router as feedback_router
from src.presentation.api.v1.reports.router import router as reports_router
from src.presentation.api.v1.subscriptions.router import router as subscriptions_router
from src.presentation.api.v1.transactions.router import router as transactions_router
from src.presentation.api.v1.webhook.evolution_router import router as webhook_evolution_router
from src.presentation.api.v1.webhooks.stripe_router import router as webhook_stripe_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(bot_router)
router.include_router(categories_router)
router.include_router(transactions_router)
router.include_router(conversations_router)
router.include_router(feedback_router)
router.include_router(reports_router)
router.include_router(subscriptions_router)
router.include_router(ai_usage_router)
router.include_router(admin_auth_router)
router.include_router(admin_stats_router)
router.include_router(admin_users_router)
router.include_router(admin_evolution_router)
router.include_router(admin_feedback_router)
router.include_router(admin_plan_prices_router)
router.include_router(admin_ai_usage_router)
router.include_router(admin_activity_router)
router.include_router(admin_payments_router)
router.include_router(webhook_evolution_router)
router.include_router(webhook_stripe_router)
