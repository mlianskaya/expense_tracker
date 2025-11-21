from django.contrib import admin
from .models import Account, Category, Transaction, Budget

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'currency', 'balance', 'created_at')
    list_filter = ('currency',)
    search_fields = ('name', 'owner__username')

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'type', 'parent')
    list_filter = ('type',)
    search_fields = ('name',)

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('date', 'account', 'category', 'amount', 'type')
    list_filter = ('date', 'category', 'account', 'type')
    search_fields = ('description',)

@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ('category', 'owner', 'period_start', 'limit_amount')
    list_filter = ('period_start',)
    search_fields = ('category__name',)