from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'lendings', views.LendingViewSet, basename='lending')
router.register(r'sales', views.SaleViewSet, basename='sale')
app_name = 'app'


urlpatterns = [
    path('login/', views.LoginView.as_view(), name='login'),
    path('login_as_user/', views.LoginAsUserView.as_view(), name='login_as_user'),
    path('signup/', views.SignUpView.as_view(), name='signup'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    
    # Product URLs
    path('products/', views.ProductListCreateView.as_view(), name='product-list'),
    path('products/<int:pk>/', views.ProductDetailView.as_view(), name='product-detail'),
    path('products/<int:pk>/status/', views.ProductStatusUpdateView.as_view(), name='product-status'),

    # Lending URL s
    path('', include(router.urls)),

    path('', include(router.urls)),
    
    # Category URLs
    path('categories/', views.CategoryListCreateView.as_view(), name='category-list'),
    path('categories/<int:pk>/', views.CategoryDetailView.as_view(), name='category-detail'),
    # path('category-view/', views.CategoryViewSet.as_view()),

    path('sellers/<int:id>/statistics/', views.SellerStatisticsView.as_view(), name='seller-statistics'),
    
    # Include router URLs
    path('', include(router.urls)),
    path('user/<int:id>/',views.UserDetailView.as_view(), name='user-detail'),
    path('users/', views.UserListView.as_view(), name='user-list'),

    path('user/image/', views.UserImageView.as_view(), name='user-image'),
    path('user/<int:user_id>/statistics/', views.UserStatisticsView.as_view(), name='user-statistics'),
    path('user/<int:user_id>/monthly_income/', views.UserMonthlyIncomeView.as_view(), name='user-monthly-income'),
    path('user/<int:user_id>/management/', views.UserManagementView.as_view(), name='user-management'),


    path('statistics/', views.StatisticsView.as_view(), name='statistics'),
    path('statistics/daily/', views.DailyStatisticsView.as_view(), name='daily-statistics'),
    path('statistics/weekly/', views.WeeklyStatisticsView.as_view(), name='weekly-statistics'),
    path('statistics/monthly/', views.MonthlyStatisticsView.as_view(), name='monthly-statistics'),
    path('statistics/yearly/', views.YearlyStatisticsView.as_view(), name='yearly-statistics'),
    path('statistics/yearly/<int:year>/', views.YearlyDetailStatisticsView.as_view(), name='yearly-statistics'),

    path('videoqollanma/', views.VideoQollanmaListView.as_view(), name='videoqollanma-list'),

    # Tariff lar uchun API lar
    path('tariffs/', views.TariffCreateView.as_view(), name='tariff-create'),
    path('tariff/', views.TariffRetrieveView.as_view(), name='tariff-retrieve'),
] 