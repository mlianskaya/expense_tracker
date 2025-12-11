from django.urls import path
from . import views
from .views import CustomLoginView, CustomLogoutView

app_name = 'expenses'

urlpatterns = [
    # Аутентификация
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', CustomLogoutView.as_view(), name='logout'),
    path('register/', views.register, name='register'),

    # Главная страница
    path('', views.home, name='home'),

    # Остальные URL...
    path('accounts/', views.AccountListView.as_view(), name='account_list'),
    path('accounts/add/', views.AccountCreateView.as_view(), name='account_add'),
    path('transactions/', views.TransactionListView.as_view(), name='transaction_list'),
    path('transactions/add/', views.TransactionCreateView.as_view(), name='transaction_add'),
    path('transactions/<int:pk>/edit/', views.TransactionUpdateView.as_view(), name='transaction_edit'),
    path('transactions/<int:pk>/delete/', views.TransactionDeleteView.as_view(), name='transaction_delete'),
    path('categories/', views.CategoryListView.as_view(), name='category_list'),
    path('categories/add/', views.CategoryCreateView.as_view(), name='category_add'),
]