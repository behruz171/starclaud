from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views import UserDetailView, UserListView

router = DefaultRouter()
router.register(r'lendings', views.LendingViewSet, basename='lending')

app_name = 'app'

urlpatterns = [
    path('login/', views.LoginView.as_view(), name='login'),
    path('signup/', views.SignUpView.as_view(), name='signup'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    
    # Product URLs
    path('products/', views.ProductListCreateView.as_view(), name='product-list'),
    path('products/<int:pk>/', views.ProductDetailView.as_view(), name='product-detail'),
    path('products/<int:pk>/status/', views.ProductStatusUpdateView.as_view(), name='product-status'),
    
    # Category URLs
    path('categories/', views.CategoryListCreateView.as_view(), name='category-list'),
    # path('category-view/', views.CategoryViewSet.as_view()),
    
    # Include router URLs
    path('', include(router.urls)),
    path('user/<int:id>/', UserDetailView.as_view(), name='user-detail'),
    path('users/', UserListView.as_view(), name='user-list'),
] 