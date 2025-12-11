from decimal import Decimal
from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.core.exceptions import ValidationError

User = settings.AUTH_USER_MODEL

class Account(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='accounts')
    name = models.CharField(max_length=120)
    currency = models.CharField(max_length=3, default='RUB')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.currency})"

class Category(models.Model):
    TYPE_INCOME = 'income'
    TYPE_EXPENSE = 'expense'
    TYPE_CHOICES = [
        (TYPE_INCOME, 'Income'),
        (TYPE_EXPENSE, 'Expense'),
    ]

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=120)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='children')

    class Meta:
        unique_together = ('owner', 'name', 'type')
        ordering = ['name']

    def __str__(self):
        return self.name
    
class Transaction(models.Model):
    TYPE_INCOME = 'income'
    TYPE_EXPENSE = 'expense'
    TYPE_CHOICES = [
        (TYPE_INCOME, 'Income'),
        (TYPE_EXPENSE, 'Expense'),
    ]

    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='transactions')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='transactions')
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    date = models.DateField(default=timezone.now)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.date} — {self.amount} {self.account.currency}"

    def clean(self):
        if self.category and self.category.type != self.type:
            raise ValidationError("Тип транзакции должен соответствовать типу категории.")


class Budget(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='budgets')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='budgets')
    period_start = models.DateField(help_text='Первый день месяца')
    limit_amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])

    class Meta:
        unique_together = ('owner', 'category', 'period_start')
        ordering = ['-period_start']

    def str(self):
        return f"{self.category.name} — {self.period_start:%Y-%m} — {self.limit_amount}"

# Сигналы для автоматического обновления баланса
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver

@receiver(pre_save, sender=Transaction)
def transaction_pre_save(sender, instance, **kwargs):
    if not instance.pk:
        instance._pre_save_old_amount = None
        instance._pre_save_old_type = None
    else:
        try:
            old = Transaction.objects.get(pk=instance.pk)
            instance._pre_save_old_amount = old.amount
            instance._pre_save_old_type = old.type
            instance._pre_save_old_account = old.account
        except Transaction.DoesNotExist:
            instance._pre_save_old_amount = None
            instance._pre_save_old_type = None


@receiver(post_save, sender=Transaction)
def transaction_post_save(sender, instance, created, **kwargs):
    # Пропускаем создание (там логика уже правильная)
    if created:
        delta = instance.amount if instance.type == Transaction.TYPE_INCOME else -instance.amount
        account_obj = instance.account
        account_obj.balance = (account_obj.balance or Decimal('0.00')) + Decimal(delta)
        account_obj.save(update_fields=['balance'])
        return

    # Для обновления — проверяем, есть ли старые данные
    old_amount = getattr(instance, '_pre_save_old_amount', None)
    old_type = getattr(instance, '_pre_save_old_type', None)
    old_account = getattr(instance, '_pre_save_old_account', None)

    # Если НЕТ старых данных (первый save при update), ничего не делаем
    if old_amount is None or old_type is None or old_account is None:
        return

    # Вычитаем старый эффект
    old_delta = old_amount if old_type == Transaction.TYPE_INCOME else -old_amount
    old_account.balance = (old_account.balance or Decimal('0.00')) - Decimal(old_delta)
    old_account.save(update_fields=['balance'])

    # Добавляем новый эффект
    new_delta = instance.amount if instance.type == Transaction.TYPE_INCOME else -instance.amount
    instance.account.balance = (instance.account.balance or Decimal('0.00')) + Decimal(new_delta)
    instance.account.save(update_fields=['balance'])


@receiver(post_delete, sender=Transaction)
def transaction_post_delete(sender, instance, **kwargs):
    delta = instance.amount if instance.type == Transaction.TYPE_INCOME else -instance.amount
    acc = instance.account
    acc.balance = (acc.balance or Decimal('0.00')) - Decimal(delta)
    acc.save(update_fields=['balance'])