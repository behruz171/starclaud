from rest_framework import serializers, generics, status
from decimal import Decimal
from django.contrib.auth.hashers import make_password
from rest_framework.permissions import IsAuthenticated
from .models import *
from django.db.models import Sum
from rest_framework.response import Response


class UserListSerializer(serializers.ModelSerializer):
    monthly_sales = serializers.IntegerField(read_only=True)
    monthly_lendings = serializers.IntegerField(read_only=True)
    total_products_sold = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        read_only=True
    )
    class Meta:
        model = User
        fields = ["id","img","first_name" ,"username", "role", "KPI", "salary", 'monthly_sales','monthly_lendings', 'total_products_sold' ]

class UserDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'role', 'img', 'age', 'gender', 
                  'work_start_time', 'work_end_time', 'phone', 'AD', 'JSHSHR', 
                  'city', 'district', 'neighborhood', 'street', 
                  'salary', 'KPI', 'is_convicted','is_married',]
        read_only_fields = fields

class UserSerializer(serializers.ModelSerializer):
    # admin = serializers.CharField(source='created_by.username', read_only=True)
    created_users = UserListSerializer(many=True, read_only=True)  # Users created by the director
    
    class Meta:
        model = User
        fields = ['id', 'username', 'password', 'role','first_name', 'last_name', 'img', 'age', 'gender', 
                  'work_start_time', 'work_end_time', 'phone', 'AD', 'JSHSHR', 
                  'city', 'district', 'neighborhood', 'street', 
                  'salary', 'KPI', 'created_users', 'is_convicted', 'is_married']
        extra_kwargs = {
            'password': {'write_only': True},
        }

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Agar user director bo'lsa, unga bog'langan userlarni qaytaradi
        if instance.role == User.DIRECTOR:
            data['admins'] = UserListSerializer(
                instance.created_users.filter(role=User.ADMIN), 
                many=True
            ).data
            data['sellers'] = UserListSerializer(
                instance.created_users.filter(role=User.SELLER), 
                many=True
            ).data
            data.pop('created_users', None)  # created_users ni olib tashlaymiz
        return data

    def validate(self, attrs):
        request = self.context.get('request')
        if not request or not request.user:
            raise serializers.ValidationError("Authentication required")

        user = request.user
        role = attrs.get('role', '').upper()

        # Director ADMIN va SELLER yarata oladi
        if user.role == User.DIRECTOR:
            if role not in [User.ADMIN, User.SELLER]:
                raise serializers.ValidationError({
                    "error": "Director can only create admins or sellers"
                })
        # Admin faqat SELLER yarata oladi
        elif user.role == User.ADMIN:
            if role != User.SELLER:
                raise serializers.ValidationError({
                    "error": "Admin can only create sellers"
                })
        # Boshqalar yarata olmaydi
        else:
            raise serializers.ValidationError({
                "error": "You do not have permission to create users"
            })

        attrs['role'] = role
        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        # Ensure the user is a director to create other users
        print(validated_data)
        if user.role == User.DIRECTOR:
            created_by = user
        # Admin faqat SELLER yarata oladi
        elif user.role == User.ADMIN and validated_data.get('role') == User.SELLER:
            created_by = user.created_by  # Director as creator
        else:
            raise serializers.ValidationError({
                "error": "You do not have permission to create users"
            })
        
        # Create the user and set the created_by field
        new_user = User.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password'],
            role=validated_data.get('role', User.SELLER),
            first_name=validated_data.get('first_name',''),
            last_name=validated_data.get('last_name',''),
            img=validated_data.get('img', ''),
            gender=validated_data.get('gender', ''),
            work_start_time=validated_data.get('work_start_time', ''),
            work_end_time=validated_data.get('work_end_time', ''),
            phone=validated_data.get('phone', ''),
            age=validated_data.get('age', 0),
            AD=validated_data.get('AD',''),
            JSHSHR=validated_data.get('JSHSHR', ''),
            city=validated_data.get('city', ''),
            district=validated_data.get('district', ''),
            neighborhood=validated_data.get('neighborhood', ''),
            street=validated_data.get('street', ''),
            salary=validated_data.get('salary',0),
            KPI=validated_data.get("KPI", 0),
            is_married=validated_data.get('is_married', ''),
            is_convicted=validated_data.get('is_convicted', ''),

            created_by=created_by  # Set the creator as the director
        )
        return new_user



class UserManagementSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = "__all__"

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name']

    def create(self, validated_data):
        user = self.context['request'].user
        
        # Check if the user is a seller
        if user.role == User.SELLER:
            raise serializers.ValidationError("Sellers cannot create categories.")
        
        # If the user is an admin, set created_by to the director who created the admin
        if user.role == User.ADMIN:
            if user.created_by:  # Assuming created_by is the director
                validated_data['created_by'] = user.created_by
            else:
                raise serializers.ValidationError("Admin must be associated with a director.")
        
        # If the user is a director, set created_by to themselves
        if user.role == User.DIRECTOR:
            validated_data['created_by'] = user
        
        return super().create(validated_data)

class CategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'pk'  # ID orqali qidirish uchun

    def get_queryset(self):
        user = self.request.user
        
        if user.role == User.DIRECTOR:
            return Category.objects.filter(created_by=user)
        elif user.role in [User.ADMIN, User.SELLER]:
            return Category.objects.filter(created_by=user.created_by)
        
        return Category.objects.none()

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        
        if serializer.is_valid():
            # Faqat director o'zi yaratgan categoryni update qila oladi
            if request.user.role == User.DIRECTOR and instance.created_by == request.user:
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"error": "You don't have permission to update this category"}, 
                    status=status.HTTP_403_FORBIDDEN
                )
                
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Faqat director o'zi yaratgan categoryni o'chira oladi
        if request.user.role == User.DIRECTOR and instance.created_by == request.user:
            instance.delete()
            return Response(
                {"message": "Category deleted successfully"}, 
                status=status.HTTP_204_NO_CONTENT
            )
        else:
            return Response(
                {"error": "You don't have permission to delete this category"}, 
                status=status.HTTP_403_FORBIDDEN
            )

class ProductSerializer(serializers.ModelSerializer):
    seller = serializers.CharField(source='created_by.username', read_only=True)
    admin = serializers.CharField(source='admin.username', read_only=True)
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Product
        fields = ['id', 'name', 'description', 'price', 'status', 
                  'lend_count', 'seller', 'admin', 'created_at', 
                  'category', 'category_name', 'img', 'choice', 
                  'rental_price', 'location', 'quantity', 'weight', 'scan_code']
        read_only_fields = ['status', 'lend_count', 'created_at', 'seller', 'admin']

    def validate(self, attrs):
        user = self.context['request'].user
        if user.role not in [User.ADMIN, User.DIRECTOR]:
            raise serializers.ValidationError("Only Admin or Director can create products")
        
        # choice maydoni uchun tekshirish
        if attrs.get('choice') not in dict(Product.CHOICE_OPTIONS):
            raise serializers.ValidationError({"choice": "Invalid choice. Must be 'RENT' or 'SELL'."})

        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        
        if user.role == User.DIRECTOR:
            validated_data['created_by'] = user
            validated_data['admin'] = user
        elif user.role == User.ADMIN:
            if not user.created_by:
                raise serializers.ValidationError(
                    "Unable to create product: Admin must be associated with a director"
                )
            validated_data['created_by'] = user
            validated_data['admin'] = user.created_by
            
        return super().create(validated_data)

class LendingProductDetailsSerializer(serializers.ModelSerializer):
    category = serializers.CharField(source="category.name", read_only=True)
    class Meta:
        model = Product
        fields = ['id', 'name', 'img', 'category', 'rental_price', 'status']


class LendingSerializer(serializers.ModelSerializer):
    product_detail = LendingProductDetailsSerializer(source='product', read_only=True)
    remaining_percentage = serializers.SerializerMethodField()  # Remaining percentage
    amount_given = serializers.SerializerMethodField()  # Amount given
    amount_remaining = serializers.SerializerMethodField()  # Remaining amount

    class Meta:
        model = Lending
        fields = [
            'id',
            'product',
            'product_detail',
            'borrower_name', 
            'borrow_date', 
            'return_date', 
            'actual_return_date', 
            'pledge',
            'const',
            'status', 
            'percentage', 
            'remaining_percentage', 
            'amount_given', 
            'amount_remaining',
            'phone',
            'spare_phone',
            'AD',
            'JSHSHR',
            'adress'
        ]
        read_only_fields = ['status']

    def create(self, validated_data):
        user = self.context['request'].user
        if not user:
            raise serializers.ValidationError("User information is missing.")
        
        uzbekistan_tz = pytz.timezone('Asia/Tashkent')
        current_time = timezone.now().astimezone(uzbekistan_tz)
        current_time = current_time.time()

        # Get director's working hours
        if user.role == User.DIRECTOR:
            work_start = user.work_start_time
            work_end = user.work_end_time
        else:
            # If user is ADMIN or SELLER, get their director's working hours
            director = user.created_by
            work_start = director.work_start_time
            work_end = director.work_end_time
        
        if not (work_start <= current_time <= work_end):
            raise serializers.ValidationError({
                "error": "Faqat berilgan vaqt oraligida ijaraga berishingiz mumkin",
                "working_hours": f"{work_start} dan {work_end} gacha"
            }, code=status.HTTP_403_FORBIDDEN)
        
        validated_data['seller'] = user
        return super().create(validated_data)

    def get_remaining_percentage(self, obj):
        if obj.percentage:
            percentage_str = obj.percentage.replace('%', '').strip()
            try:
                percentage = int(percentage_str)
                return f"{100 - percentage}%"  # Remaining percentage
            except ValueError:
                return None
        return None

    def get_amount_given(self, obj):
        if obj.product and obj.product.rental_price and obj.percentage:
            percentage_str = obj.percentage.replace('%', '').strip()
            try:
                percentage = int(percentage_str)
                rental_price = Decimal(obj.product.rental_price)
                # Amount given: rental_price - (100 - percentage)%
                discount_amount = (rental_price * (100 - percentage)) / 100
                return rental_price - discount_amount
            except ValueError:
                return None
        return None

    def get_amount_remaining(self, obj):
        if obj.product and obj.product.rental_price and obj.percentage:
            percentage_str = obj.percentage.replace('%', '').strip()
            try:
                percentage = int(percentage_str)
                rental_price = Decimal(obj.product.rental_price)
                # Remaining amount: rental_price - percentage%
                discount_amount = (rental_price * percentage) / 100
                return rental_price - discount_amount
            except ValueError:
                return None
        return None
  


class SellerStatisticsSerializer(serializers.ModelSerializer):
    products_sold = serializers.SerializerMethodField()
    lendings_count = serializers.SerializerMethodField()
    total_sold_price = serializers.SerializerMethodField()
    total_rental_price = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'salary', 'products_sold', 'lendings_count', 'total_sold_price', 'total_rental_price']

    def get_products_sold(self, obj):
        # Count only products with choice 'SELL'
        return obj.products.filter(choice='SELL').count()  # Count of products created by the seller with choice 'SELL'

    def get_lendings_count(self, obj):
        return obj.lendings.count()
    
    def get_total_sold_price(self, obj):
        # Calculate the total price of products with choice 'SELL'
        total_price = obj.products.filter(choice='SELL').aggregate(total_price=Sum('price'))['total_price'] or 0
        
        # Calculate the amount after applying the KPI percentage
        kpi_percentage = obj.KPI  # Assuming KPI is stored as a percentage (e.g., 20 for 20%)
        discount_amount = (total_price * kpi_percentage) / 100  # Calculate the discount based on KPI
        return total_price + discount_amount
    
    def get_total_rental_price(self, obj):
        # Calculate the total rental price from lendings
        total_rental_price = obj.lendings.aggregate(total_rental_price=Sum('product__rental_price'))['total_rental_price'] or 0
        
        # Calculate the amount after applying the KPI percentage
        kpi_percentage = obj.KPI  # Assuming KPI is stored as a percentage (e.g., 20 for 20%)
        discount_amount = (total_rental_price * kpi_percentage) / 100  # Calculate the discount based on KPI
        return total_rental_price + discount_amount  # Return the total rental price after discount
    

class SaleProductDetailSerializer(serializers.ModelSerializer):
    category = serializers.CharField(source='category.name', read_only=True)  # Agar category ForeignKey bo'lsa

    class Meta:
        model = Product
        fields = ['id', 'name', 'category', 'img', 'price', 'status']  # 'category' ni qo'shing # Agar category bo'lmasa, None qaytaring

class SaleSerializer(serializers.ModelSerializer):
    product_detail = SaleProductDetailSerializer(source='product', read_only=True)
    # seller_username = serializers.CharField(source='seller.username', read_only=True)  # Read-only field for seller's username

    class Meta:
        model = Sale
        fields = ['id',"product", "product_detail", "buyer", "sale_price", "sale_date", "quantity", "status", 'product_weight', 'reason_cancelled']
    
    id = serializers.IntegerField(read_only=True)

    def create(self, validated_data):
        # Get the authenticated user from the request context
        request = self.context.get('request')
        seller = request.user if request else None

        if not seller:
            raise serializers.ValidationError("Seller information is missing.")

        # Get current time in Uzbekistan timezone
        uzbekistan_tz = pytz.timezone('Asia/Tashkent')
        current_time = timezone.now().astimezone(uzbekistan_tz)
        current_time = current_time.time()

        # Get director's working hours
        if seller.role == User.DIRECTOR:
            work_start = seller.work_start_time
            work_end = seller.work_end_time
        else:
            # If seller is ADMIN or SELLER, get their director's working hours
            director = seller.created_by
            work_start = director.work_start_time
            work_end = director.work_end_time

        # Check if current time is within working hours
        if not (work_start <= current_time <= work_end):
            raise serializers.ValidationError({
                "error": "Faqat belgilangan vaqtda sotishingiz kerak",
                "working_hours": f"{work_start} dan {work_end} gacha"
            }, code=status.HTTP_403_FORBIDDEN)

        # Create the Sale instance with the authenticated user as the seller
        sale = Sale.objects.create(seller=seller, **validated_data)
        sale.product.save()

        return sale


class UserImageSerializer(serializers.ModelSerializer):
    img = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'img']  # Include the fields you want to return

    def get_img(self, obj):
        # Return the full URL for the image
        request = self.context.get('request')
        if obj.img:
            return request.build_absolute_uri(obj.img.url)  # Construct the full URL
        return None  # Return None if there is no image

class StatisticsSerializer(serializers.Serializer):
    total_lendings = serializers.IntegerField()
    total_sales = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=10, decimal_places=2)


class VideoQollanmaSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoQollanma
        fields = ['id', 'title', 'youtube_link', 'youtube_link_img', 'img', 'role']


class TariffSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tariff
        fields = ['name', 'director_count', 'admin_count', 'seller_count', 'product_count','category_count', 'from_date', 'to_date', 'price', 'status']


class TariffDetailSerializer(serializers.ModelSerializer):
    seller_count_now = serializers.SerializerMethodField()
    admin_count_now = serializers.SerializerMethodField()
    product_count_now = serializers.SerializerMethodField()
    category_count_now = serializers.SerializerMethodField()
    class Meta:
        model = Tariff
        fields = ['id', 'name', 'director_count', 'admin_count', 'seller_count', 'product_count', 'category_count', 'from_date', 'to_date', 'price', 'status', 'admin_count_now', 'seller_count_now', 'product_count_now', 'category_count_now']
    
    def get_seller_count_now(self, obj):
        # Director tomonidan yaratilgan sellerlar sonini hisoblash
        return User.objects.filter(created_by=obj.user, role=User.SELLER).count()

    def get_admin_count_now(self, obj):
        # Director tomonidan yaratilgan adminlar sonini hisoblash
        return User.objects.filter(created_by=obj.user, role=User.ADMIN).count()

    def get_product_count_now(self, obj):
        # Director tomonidan yaratilgan mahsulotlar sonini hisoblash
        return Product.objects.filter(admin=obj.user).count()
    def get_category_count_now(self, obj):
        return Category.objects.filter(created_by=obj.user).count()



class CartItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_quantity = serializers.CharField(source='product.quantity', read_only=True)
    product_img = serializers.ImageField(source='product.img', read_only=True)
    product_category = serializers.CharField(source='product.category.name', read_only=True)
    product_price = serializers.DecimalField(source='product.price', max_digits=25, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = ['id', 'product', 'product_name', 'product_img', 'product_category', 'product_price', 'product_quantity', 'quantity']

class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ['id', 'seller', 'created_at', 'items', 'total_price']

    def get_total_price(self, obj):
        total = 0
        for item in obj.items.all():
            price = item.product.price if item.product.price is not None else 0
            total += price * item.quantity
        return total


class CashWithdrawalSerializer(serializers.ModelSerializer):
    class Meta:
        model = CashWithdrawal
        fields = ['id', 'seller', 'amount', 'comment', 'created_at']
        read_only_fields = ['id', 'seller', 'created_at']