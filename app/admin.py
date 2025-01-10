from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import *

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username','first_name', 'last_name', 'email', 'role', 'created_by', 'is_active', 'age', 'gender', 'salary')
    list_filter = ('role', 'is_active')
    search_fields = ('username', 'email')
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('img','first_name', 'last_name', 'age', 'gender', 'work_start_time', 'work_end_time', 'AD', 'JSHSHR', 'city', 'district', 'neighborhood', 'street', 'salary', 'KPI')}),
        ('Permissions', {'fields': ('role', 'created_by', 'is_active')}),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            if request.user.role == User.DIRECTOR:
                return qs
            elif request.user.role == User.ADMIN:
                return qs.filter(Q(created_by=request.user) | Q(pk=request.user.pk))
        return qs

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'status', 'created_by', 'admin', 'lend_count', 'category', 'img', 'choice', 'rental_price', 'location', 'quantity', 'weight')
    list_filter = ('status', 'admin', 'category', 'choice')
    search_fields = ('name', 'description', 'category__name')
    
    fieldsets = (
        (None, {'fields': ('name', 'description', 'price', 'status', 'created_by', 'admin', 'lend_count', 'category')}),
        ('Product Details', {'fields': ('img', 'choice', 'rental_price', 'location', 'quantity', 'weight')}),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            if request.user.role == User.ADMIN:
                return qs.filter(admin=request.user)
            elif request.user.role == User.SELLER:
                return qs.filter(created_by=request.user)
        return qs

@admin.register(Lending)
class LendingAdmin(admin.ModelAdmin):
    list_display = ('product', 'seller', 'borrower_name', 'return_date', 'status')
    list_filter = ('status', 'borrow_date')
    search_fields = ('borrower_name', 'product__name')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            if request.user.role == User.ADMIN:
                return qs.filter(product__admin=request.user)
            elif request.user.role == User.SELLER:
                return qs.filter(seller=request.user)
        return qs
admin.site.register(Category)
admin.site.register(Sale)
