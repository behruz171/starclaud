from typing import Iterable
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib import admin
from rest_framework import serializers
from django.utils import timezone
import pytz
from decimal import Decimal
from django.utils.timezone import now

class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class User(AbstractUser):
    DIRECTOR = 'DIRECTOR'
    ADMIN = 'ADMIN'
    SELLER = 'SELLER'

    CONVICTED_CHOICES = [
        ('yes', 'Ha'),
        ('no', 'Yoq')
    ]

    MARRIED_CHOICES = [
        ('yes', 'Ha'),
        ('no', 'Yoq')
    ]
    
    ROLE_CHOICES = [
        (DIRECTOR, 'Director'),
        (ADMIN, 'Admin'),
        (SELLER, 'Seller'),
    ]
    
    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default=SELLER
    )
    created_by = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='created_users'
    )
    img = models.ImageField(upload_to='user_images/')
    age = models.PositiveIntegerField(null=True)
    gender = models.CharField(max_length=10)
    work_start_time = models.TimeField(max_length=20, default=now)
    work_end_time = models.TimeField(max_length=20, default=now)
    AD = models.CharField(max_length=15)
    phone = models.CharField(max_length=15, blank=True, null=True)
    JSHSHR = models.CharField(max_length=15)
    city = models.CharField(max_length=100, blank=True, null=True)
    district = models.CharField(max_length=100, blank=True, null=True)
    neighborhood = models.CharField(max_length=100, blank=True, null=True)
    street = models.CharField(max_length=100,blank=True, null=True)
    salary = models.DecimalField(max_digits=12, decimal_places=2, null=False, default=0.00)
    KPI = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    is_convicted = models.CharField(
        max_length=10,
        # choices=CONVICTED_CHOICES,
        null=True,
        blank=True  # Dastlabki qiymati "Yoq"
    )  # Sudlanganmi

    is_married = models.CharField(
        max_length=10,
        # choices=MARRIED_CHOICES,
        null=True,
        blank=True # Dastlabki qiymati "Yoq"
    )  # Oilalik

    class Meta:
        ordering = ['username']
        
    # def clean(self):
    #     if User.objects.count() == 0:
    #         return
            
    #     if self.role == self.SELLER and (not self.created_by or self.created_by.role != self.ADMIN):
    #         raise ValidationError("Sellers must be created by an Admin")
    #     if self.role == self.ADMIN and (not self.created_by or self.created_by.role != self.DIRECTOR):
    #         raise ValidationError("Admins must be created by a Director")
            
    def save(self, *args, **kwargs):
        if User.objects.count() == 0:
            self.role = self.DIRECTOR
            super().save(*args, **kwargs)
        else:
            self.clean()
            super().save(*args, **kwargs)
        
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

class Category(BaseModel):
    name = models.CharField(max_length=255, unique=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='categories'
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

class Product(BaseModel):
    AVAILABLE = 'AVAILABLE'
    NOT_AVAILABLE = 'NOT_AVAILABLE'
    LENT_OUT = 'LENT_OUT'
    
    STATUS_CHOICES = [
        (AVAILABLE, 'Available'),
        (NOT_AVAILABLE, 'Not Available'),
        (LENT_OUT, 'Lent Out'),
    ]

    CHOICE_OPTIONS = [
        ('RENT', 'Rent'),
        ('SELL', 'Sell'),
    ]
    
    name = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(max_digits=25, decimal_places=2, null=True, blank=True)
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default=AVAILABLE
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='products'
    )
    admin = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='admin_products'
    )
    lend_count = models.IntegerField(default=0)
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='products'
    )
    img = models.ImageField(upload_to='product_images/', null=False)
    choice = models.CharField(max_length=4, choices=CHOICE_OPTIONS, null=False)
    rental_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    quantity = models.PositiveIntegerField(default=0, blank=True, null=True)
    weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    scan_code = models.CharField(max_length=300, blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"
    
    def save(self,*args, **kwargs):
        if not self.quantity and not self.weight:
            raise ValidationError("Quantity yoki Product Weight dan biri kiritilishi shart.")
        if self.quantity and self.weight:
            raise ValidationError("Faqat Quantity yoki Product Weight dan birini kiriting, ikkalasini emas.")
        if self.choice == 'RENT':
            if self.price:
                raise ValidationError("Bu mahsulot nasiyaga berish uchun uchun")
        if self.choice == 'SELL':
            if self.rental_price:
                raise ValidationError("Bu mahsulot faqat sotish uchun")
        if self.rental_price and self.price:
            raise ValidationError("faqat bitta malumot yuborishingiz mumkin!")
        # if not self.price and not self.rental_price:
        #     raise ValidationError("price yoki rental price maydonlaridan birini kiritishingiz kerak!")
        super().save(*args, **kwargs)



class Lending(BaseModel):
    LENT = 'LENT'
    RETURNED = 'RETURNED'

    PERCENTAGE1 = '25%'
    PERCENTAGE2 = '50%'
    PERCENTAGE3 = '75%'
    PERCENTAGE4 = '100%'

    
    
    STATUS_CHOICES = [
        (LENT, 'Lent'),
        (RETURNED, 'Returned'),
    ]
    PERCENTAGE_CHOICES = [
        (PERCENTAGE1, '25%'),
        (PERCENTAGE2, '50%'),
        (PERCENTAGE3, '75%'),
        (PERCENTAGE4, '100%')
    ]
    
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='lendings'
    )
    seller = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='lendings'
    )
    borrower_name = models.CharField(max_length=255)
    borrow_date = models.DateTimeField(auto_now_add=True)
    return_date = models.DateTimeField()
    actual_return_date = models.DateField(null=True, blank=True)
    AD = models.CharField(max_length=15)
    JSHSHR = models.CharField(max_length=15)
    adress = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    spare_phone = models.CharField(max_length=20)
    percentage = models.CharField(
        max_length=25,
        choices=PERCENTAGE_CHOICES
    )
    const = models.CharField(max_length=100)
    pledge = models.ImageField(upload_to='pledge_img')


    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=LENT
    )
    class Meta:
        ordering = ['-borrow_date']
        
    def clean(self):
        print(self.seller.created_by)
        print(self.product.admin)
        if self.seller != self.product.admin and self.seller.created_by != self.product.admin:
            raise ValidationError("Sellers can only lend their own products")
        if self.product.choice != 'RENT':
            raise ValidationError("Bu mahsulot ijaraga berish uchun emas")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
        
    def __str__(self):
        return f"{self.product.name} lent to {self.borrower_name}"

# Signal handlers for Lending model
@receiver(post_save, sender=Lending)
def update_product_status(sender, instance, created, **kwargs):
    product = instance.product
    
    if created:
        # New lending record
        product.status = Product.LENT_OUT
        product.lend_count += 1
    elif instance.status == Lending.RETURNED and instance.actual_return_date:
        # Product returned
        product.status = Product.AVAILABLE
        
    product.save()


class Sale(BaseModel):
    STATUS_CHOICES = [
        ('COMPLETED', 'Completed'),
        ('PENDING', 'Pending'),
        ('CANCELLED', 'Cancelled'),
    ]

    PAYMENT_TYPE_CHOICES = [
        ('CASH', 'Naqd'),
        ('CARD', 'Karta'),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='sales')
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sales')
    buyer = models.CharField(max_length=100)
    sale_price = models.DecimalField(max_digits=10, decimal_places=2)
    sale_date = models.DateTimeField(auto_now_add=True)
    quantity = models.PositiveIntegerField(null=True, blank=True)
    product_weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    payment_type = models.CharField(max_length=10, choices=PAYMENT_TYPE_CHOICES, default='CASH')
    reason_cancelled = models.CharField(max_length=200, null=True, blank=True)

    class Meta:
        ordering = ['-sale_date']

    def __str__(self):
        return f"{self.product.name} sold by {self.seller.username} to {self.buyer} for {self.sale_price}"

    def save(self, *args, **kwargs):
        # Mahsulotning mavjud miqdorini tekshirish
        if not self.quantity and not self.product_weight:
            raise ValidationError("Quantity yoki Product Weight dan biri kiritilishi shart.")
        
        if self.quantity and self.product_weight:
            raise ValidationError("Faqat Quantity yoki Product Weight dan birini kiriting, ikkalasini emas.")

        if self.quantity:
            if not self.product.quantity:
                raise ValidationError("productning soni yoq")
            if self.quantity > self.product.quantity:
                raise ValidationError("Sotilayotgan miqdor mahsulotning mavjud miqdoridan oshib ketmasligi kerak.")
        
        if self.product_weight:
            if not self.product.weight:
                raise ValidationError("productning soni yoq")
            if self.product_weight > self.product.weight:
                raise ValidationError("Sotilayotgan og'irlik mahsulotning mavjud og'irligidan oshib ketmasligi kerak.")
        
        # Mahsulotning choice ni tekshirish
        if self.product.choice != 'SELL':
            raise ValidationError("Faqat 'SELL' tanloviga ega mahsulotlarni sotish mumkin.")
        
        if self.product.admin != self.seller.created_by and self.product.admin != self.seller:
            raise ValidationError("Sotuvchi mahsulotning admini bilan bir xil 'created_by' ga ega bo'lishi kerak.")
        # Agar hammasi to'g'ri bo'lsa, saqlash

        # Sotilgandan so'ng, mahsulotning miqdorini yangilash
        if self.pk:
            old_instance = Sale.objects.get(pk=self.pk)
            old_quantity = old_instance.quantity or 0
            old_weight = old_instance.product_weight or 0
        else:
            old_quantity = 0
            old_weight = 0
        
        if not self.pk:  # Yangi ob'ekt
            if self.quantity:
                self.product.quantity -= self.quantity
            elif self.product_weight:
                self.product.weight -= Decimal(self.product_weight)
        else:  # Yangilanish
            if self.status == 'CANCELLED' and old_instance.status != 'CANCELLED':
                # Cancel qilinganda, eski qiymatni qaytarish
                if old_quantity:
                    self.product.quantity += old_quantity
                if old_weight:
                    self.product.weight += Decimal(old_weight)
            elif self.status != 'CANCELLED' and old_instance.status == 'CANCELLED':
                # Cancel'dan qayta sotilishga o'tgan bo'lsa
                if self.quantity:
                    self.product.quantity -= self.quantity
                elif self.product_weight:
                    self.product.weight -= Decimal(self.product_weight)

        # Mahsulotni saqlash
        self.product.save()
        super().save(*args, **kwargs)

    


class VideoQollanma(models.Model):
    ROLE_CHOICES = [
        ('SELLER', 'Seller'),
        ('ADMIN', 'Admin'),
        ('DIRECTOR', 'Director'),
    ]

    title = models.CharField(max_length=255)  # Video qollanmaning sarlavhasi
    youtube_link = models.URLField(max_length=200)  # Youtube video linki
    youtube_link_img = models.URLField(max_length=200)  # Youtube video rasm linki
    img = models.ImageField(upload_to='video_qollanma_images/')  # Video qollanma uchun rasm
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)  # Role tanlovi

    def __str__(self):
        return self.title


class Tariff(BaseModel):
    STATUS_CHOICES = [
        ('active', 'Ishlayapti'),
        ('inactive', 'Ishlamayapti'),
    ]

    name = models.CharField(max_length=255)
    user = models.ForeignKey(User, on_delete=models.CASCADE)  # Director
    director_count = models.PositiveIntegerField(default=0)
    admin_count = models.PositiveIntegerField(default=0)
    seller_count = models.PositiveIntegerField(default=0)
    product_count = models.PositiveIntegerField(default=0)
    category_count = models.PositiveIntegerField(default=0)
    from_date = models.DateTimeField()
    to_date = models.DateTimeField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)

    def save(self, *args, **kwargs):
        # Agar bu yangi tarif bo'lsa, avvalgi tarifni inactive holatiga o'tkazish
        if self.pk is None:  # Yangi ob'ekt
            previous_tariff = Tariff.objects.filter(user=self.user, status='active').first()
            if previous_tariff:
                previous_tariff.status = 'inactive'
                previous_tariff.save()  # Eski tarifni saqlash

        super().save(*args, **kwargs) 

    def __str__(self):
        return self.name
    


class Cart(BaseModel):
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='carts')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Cart of {self.seller.username} created at {self.created_at}"

class CartItem(BaseModel):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.product.name} in cart of {self.cart.seller.username}"


class CashWithdrawal(BaseModel):
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='withdrawals')
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    comment = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Withdrawal of {self.amount} by {self.seller.username} on {self.created_at}"