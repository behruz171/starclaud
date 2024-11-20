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

    class Meta:
        ordering = ['username']
        
    def clean(self):
        if User.objects.count() == 0:
            return
            
        if self.role == self.SELLER and (not self.created_by or self.created_by.role != self.ADMIN):
            raise ValidationError("Sellers must be created by an Admin")
        if self.role == self.ADMIN and (not self.created_by or self.created_by.role != self.DIRECTOR):
            raise ValidationError("Admins must be created by a Director")
            
    def save(self, *args, **kwargs):
        if User.objects.count() == 0:
            self.role = self.DIRECTOR
            super().save(*args, **kwargs)
        else:
            self.clean()
            super().save(*args, **kwargs)
        
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

class Product(BaseModel):
    AVAILABLE = 'AVAILABLE'
    NOT_AVAILABLE = 'NOT_AVAILABLE'
    LENT_OUT = 'LENT_OUT'
    
    STATUS_CHOICES = [
        (AVAILABLE, 'Available'),
        (NOT_AVAILABLE, 'Not Available'),
        (LENT_OUT, 'Lent Out'),
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

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"

class Lending(models.Model):
    LENT = 'LENT'
    RETURNED = 'RETURNED'
    
    STATUS_CHOICES = [
        (LENT, 'Lent'),
        (RETURNED, 'Returned'),
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
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=LENT
    )
    
    class Meta:
        ordering = ['-borrow_date']
        
    def clean(self):
        if self.seller.role != User.SELLER:
            raise ValidationError("Only Sellers can create lending records")
        if self.seller != self.product.created_by:
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