from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.dispatch import receiver

class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class User(AbstractUser):
    DIRECTOR = 'DIRECTOR'
    ADMIN = 'ADMIN'
    SELLER = 'SELLER'
    
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
    work_start_time = models.CharField(max_length=20)
    work_end_time = models.CharField(max_length=20)
    AD = models.CharField(max_length=15)
    JSHSHR = models.CharField(max_length=15)
    city = models.CharField(max_length=100, blank=True, null=True)
    district = models.CharField(max_length=100, blank=True, null=True)
    neighborhood = models.CharField(max_length=100, blank=True, null=True)
    street = models.CharField(max_length=100,blank=True, null=True)
    salary = models.DecimalField(max_digits=12, decimal_places=2, null=False, default=0.00)
    KPI = models.DecimalField(max_digits=5, decimal_places=2, default=0)

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

class Category(models.Model):
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
    price = models.DecimalField(max_digits=10, decimal_places=2)
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
    quantity = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"

class Lending(models.Model):
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
    borrow_date = models.DateField()
    return_date = models.DateField()
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