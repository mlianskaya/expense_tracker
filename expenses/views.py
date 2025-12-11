from django.utils import timezone
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Account, Category, Transaction, Budget
from django.contrib.auth import login, authenticate
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from .forms import CustomUserCreationForm
from decimal import Decimal

# Кастомные представления для аутентификации
class CustomLoginView(LoginView):
    template_name = 'expenses/login.html'
    redirect_authenticated_user = True

class CustomLogoutView(LogoutView):
    next_page = '/'

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)  # Автоматически входим после регистрации
            return redirect('expenses:home')
    else:
        form = CustomUserCreationForm()
    return render(request, 'expenses/register.html', {'form': form})

# Account Views
class AccountListView(LoginRequiredMixin, ListView):
    model = Account
    template_name = 'expenses/account_list.html'

    def get_queryset(self):
        return Account.objects.filter(owner=self.request.user)

class AccountCreateView(LoginRequiredMixin, CreateView):
    model = Account
    fields = ['name', 'currency', 'balance']
    template_name = 'expenses/account_form.html'
    success_url = reverse_lazy('expenses:account_list')

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

class AccountUpdateView(LoginRequiredMixin, UpdateView):
    model = Account
    fields = ['name', 'currency', 'balance']
    template_name = 'expenses/account_form.html'
    success_url = reverse_lazy('expenses:account_list')

    def get_queryset(self):
        # Чтобы пользователь не редактировал чужие счета
        return Account.objects.filter(owner=self.request.user)


class AccountDeleteView(LoginRequiredMixin, DeleteView):
    model = Account
    template_name = 'expenses/account_confirm_delete.html'
    success_url = reverse_lazy('expenses:account_list')

    def get_queryset(self):
        return Account.objects.filter(owner=self.request.user)
    
# Transaction Views
class TransactionListView(LoginRequiredMixin, ListView):
    model = Transaction
    template_name = 'expenses/transaction_list.html'
    paginate_by = 20

    def get_queryset(self):
        qs = Transaction.objects.filter(
            account__owner=self.request.user
        ).order_by('-date')

        # --- фильтр по дате "от" ---
        date_from = self.request.GET.get('date_from')
        if date_from:
            qs = qs.filter(date__gte=date_from)

        # --- фильтр по дате "до" ---
        date_to = self.request.GET.get('date_to')
        if date_to:
            qs = qs.filter(date__lte=date_to)

        # --- фильтр по категории ---
        category = self.request.GET.get('category')
        if category:
            qs = qs.filter(category_id=category)

        # --- фильтр по счёту ---
        account = self.request.GET.get('account')
        if account:
            qs = qs.filter(account_id=account)

        # --- фильтр по типу ---
        tr_type = self.request.GET.get('type')
        if tr_type in ['income', 'expense']:
            qs = qs.filter(type=tr_type)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # данные для выпадающих списков
        context['categories'] = Category.objects.filter(owner=user)
        context['accounts'] = Account.objects.filter(owner=user)

        # сохраняем значения фильтров в форме
        context['selected'] = {
            'date_from': self.request.GET.get('date_from', ''),
            'date_to': self.request.GET.get('date_to', ''),
            'category': self.request.GET.get('category', ''),
            'account': self.request.GET.get('account', ''),
            'type': self.request.GET.get('type', ''),
        }
        return context

class TransactionCreateView(LoginRequiredMixin, CreateView):
    model = Transaction
    fields = ['account', 'category', 'amount', 'type', 'date', 'description']
    template_name = 'expenses/transaction_form.html'
    success_url = reverse_lazy('expenses:transaction_list')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['account'].queryset = Account.objects.filter(owner=self.request.user)
        form.fields['category'].queryset = Category.objects.filter(owner=self.request.user)
        return form

from django.db.models.signals import post_save

class TransactionUpdateView(LoginRequiredMixin, UpdateView):
    model = Transaction
    fields = ['account', 'category', 'amount', 'type', 'date', 'description']
    template_name = 'expenses/transaction_form.html'
    success_url = reverse_lazy('expenses:transaction_list')

    def get_queryset(self):
        return Transaction.objects.filter(account__owner=self.request.user)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['account'].queryset = Account.objects.filter(owner=self.request.user)
        form.fields['category'].queryset = Category.objects.filter(owner=self.request.user)
        return form

    def form_valid(self, form):
        # 1. Берем старую транзакцию из БД ДО сохранения
        old_tx = Transaction.objects.get(pk=self.object.pk)

        # 2. Сохраняем ссылку на оригинальный обработчик сигнала
        from .models import transaction_post_save  # импорт функции сигнала
        post_save.disconnect(transaction_post_save, sender=Transaction)

        # 3. Сохраняем новую версию транзакции (без срабатывания сигнала)
        response = super().form_valid(form)
        new_tx = self.object  # уже сохраненная транзакция

        # 4. Считаем дельту по старой и новой транзакции и обновляем баланс
        def delta_for(tx):
            return tx.amount if tx.type == Transaction.TYPE_INCOME else -tx.amount

        # если счет изменился, нужно поправить оба
        if old_tx.account_id == new_tx.account_id:
            # один и тот же счет
            account = new_tx.account
            account.balance = (account.balance or Decimal('0.00')) - delta_for(old_tx) + delta_for(new_tx)
            account.save(update_fields=['balance'])
        else:
            # старый счет: вычесть старую транзакцию
            old_acc = old_tx.account
            old_acc.balance = (old_acc.balance or Decimal('0.00')) - delta_for(old_tx)
            old_acc.save(update_fields=['balance'])

            # новый счет: добавить новую транзакцию
            new_acc = new_tx.account
            new_acc.balance = (new_acc.balance or Decimal('0.00')) + delta_for(new_tx)
            new_acc.save(update_fields=['balance'])

        # 5. Включаем сигнал обратно
        post_save.connect(transaction_post_save, sender=Transaction)

        return response


class TransactionDeleteView(LoginRequiredMixin, DeleteView):
    model = Transaction
    template_name = 'expenses/transaction_confirm_delete.html'
    success_url = reverse_lazy('expenses:transaction_list')

    def get_queryset(self):
        return Transaction.objects.filter(account__owner=self.request.user)

# Category Views
class CategoryListView(LoginRequiredMixin, ListView):

    model = Category
    template_name = 'expenses/category_list.html'
    context_object_name = 'category_list'  # чтобы работало category_list в шаблоне

    def get_queryset(self):
        return Category.objects.filter(owner=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Добавляем текущий месяц для фильтрации бюджетов
        context['now'] = timezone.now()
        return context


class CategoryCreateView(LoginRequiredMixin, CreateView):
    model = Category
    fields = ['name', 'parent']
    template_name = 'expenses/category_form.html'
    success_url = reverse_lazy('expenses:category_list')

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['parent'].queryset = Category.objects.filter(owner=self.request.user)
        return form
    
class CategoryUpdateView(LoginRequiredMixin, UpdateView):
    model = Category
    fields = ['name', 'parent']
    template_name = 'expenses/category_form.html'
    success_url = reverse_lazy('expenses:category_list')

    def get_queryset(self):
        return Category.objects.filter(owner=self.request.user)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['parent'].queryset = (
            Category.objects
            .filter(owner=self.request.user)
            .exclude(pk=self.object.pk)
        )
        return form

class CategoryDeleteView(LoginRequiredMixin, DeleteView):
    model = Category
    template_name = 'expenses/category_confirm_delete.html'
    success_url = reverse_lazy('expenses:category_list')

    def get_queryset(self):
        return Category.objects.filter(owner=self.request.user)

class BudgetCreateView(LoginRequiredMixin, CreateView):
    model = Budget
    fields = ['category', 'period_start', 'limit_amount']
    template_name = 'expenses/budget_form.html'
    success_url = reverse_lazy('expenses:category_list')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['category'].queryset = Category.objects.filter(owner=self.request.user)
        return form

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

class BudgetListView(LoginRequiredMixin, ListView):
    model = Budget
    template_name = 'expenses/budget_list.html'
    context_object_name = 'budgets'

    def get_queryset(self):
        return Budget.objects.filter(owner=self.request.user).select_related('category')

class BudgetUpdateView(LoginRequiredMixin, UpdateView):
    model = Budget
    fields = ['period_start', 'limit_amount']
    template_name = 'expenses/budget_form.html'
    success_url = reverse_lazy('expenses:category_list')

    def get_queryset(self):
        return Budget.objects.filter(owner=self.request.user)

    def get_form(self):
        form = super().get_form()
        form.fields['period_start'].widget.attrs.update({'class': 'form-control'})
        form.fields['limit_amount'].widget.attrs.update({'class': 'form-control'})
        return form

# Home page
def home(request):
    return render(request, 'expenses/home.html')
