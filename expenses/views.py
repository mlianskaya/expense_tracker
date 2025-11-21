from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Account, Category, Transaction, Budget
from django.contrib.auth import login, authenticate
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from .forms import CustomUserCreationForm

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

# Transaction Views
class TransactionListView(LoginRequiredMixin, ListView):
    model = Transaction
    template_name = 'expenses/transaction_list.html'
    paginate_by = 20

    def get_queryset(self):
        return Transaction.objects.filter(account__owner=self.request.user).order_by('-date')

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

# Category Views
class CategoryListView(LoginRequiredMixin, ListView):
    model = Category
    template_name = 'expenses/category_list.html'

    def get_queryset(self):
        return Category.objects.filter(owner=self.request.user)

class CategoryCreateView(LoginRequiredMixin, CreateView):
    model = Category
    fields = ['name', 'type', 'parent']
    template_name = 'expenses/category_form.html'
    success_url = reverse_lazy('expenses:category_list')

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['parent'].queryset = Category.objects.filter(owner=self.request.user)
        return form

# Home page
def home(request):
    return render(request, 'expenses/home.html')
