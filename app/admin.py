from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from .models import *
from django.db.models import Q

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'show_img','first_name', 'last_name', 'email', 'role', 'created_by', 'is_active', 'age', 'gender', 'salary')
    list_filter = ('role', 'is_active')
    search_fields = ('username', 'email')
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {
            'fields': (
                'img_preview',
                'img',
                'first_name', 
                'last_name', 
                'email',
                'phone',
                'role',
                'age',
                'gender',
                'AD',
                'JSHSHR',
                'city',
                'district',
                'neighborhood',
                'street',
                'salary',
                'KPI',
                'work_start_time',  # Add this
                'work_end_time',    # Add this
                'is_convicted',  # Sudlanganmi
                'is_married',
            )
        }),
        ('Permissions', {
            'fields': (
                'is_active',
                'is_staff',
                'is_superuser',
                'groups',
                'user_permissions'
            )
        }),
    )

    readonly_fields = ['img_preview'] 
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username', 
                'password1', 
                'password2',
                'work_start_time',  # Add this
                'work_end_time',    # Add this
                # ... other required fields ...
            ),
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            if request.user.role == User.DIRECTOR:
                return qs
            elif request.user.role == User.ADMIN:
                return qs.filter(Q(created_by=request.user) | Q(pk=request.user.pk))
        return qs
    
    def show_img(self, obj):
        if obj.img:  # `img` maydoningiz modeli ichida mavjud bo‘lishi kerak
            return format_html('<img src="{}" style="width: 35px; height: 35px; border-radius: 50%;" />', obj.img.url)
        return "No Image"
    show_img.short_description = "Profile Image"

    def img_preview(self, obj):
        if obj.img:  # `img` maydoningiz modeli ichida mavjud bo‘lishi kerak
            return format_html('<img src="{}" style="width: 90px; height: 90px; border: 2px solid black; border-radius: 5px;" />', obj.img.url)
        return "No Image"
    show_img.short_description = "Profile Image"
    
    

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

class VideoQollanmaAdmin(admin.ModelAdmin):
    list_display = ('title', 'youtube_link', 'img')  # Ko'rsatmoqchi bo'lgan maydonlar
    search_fields = ('title',)  # Qidirish maydoni

admin.site.register(VideoQollanma, VideoQollanmaAdmin)
admin.site.register(Tariff)