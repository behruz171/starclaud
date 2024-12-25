from rest_framework import serializers
from decimal import Decimal
from .models import *
from django.db.models import Sum


class UserListSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id","img","first_name" ,"username", "role", "KPI", "salary"]

class UserDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'role', 'img', 'age', 'gender', 
                  'work_start_time', 'work_end_time', 'AD', 'JSHSHR', 
                  'city', 'district', 'neighborhood', 'street', 
                  'salary', 'KPI']
        read_only_fields = fields

class UserSerializer(serializers.ModelSerializer):
    # admin = serializers.CharField(source='created_by.username', read_only=True)
    created_users = UserListSerializer(many=True, read_only=True)  # Users created by the director
    
    class Meta:
        model = User
        fields = ['id', 'username', 'password', 'role', 'img', 'age', 'gender', 
                  'work_start_time', 'work_end_time', 'AD', 'JSHSHR', 
                  'city', 'district', 'neighborhood', 'street', 
                  'salary', 'KPI', 'created_users']
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

        # Faqat director user yarata oladi
        if request.user.role != User.DIRECTOR:
            raise serializers.ValidationError("Only Director can create users")
        print(attrs)
        role = attrs.get('role', '').upper()
        print(f"bu role - {role}")
        if role not in [User.ADMIN, User.SELLER]:
            raise serializers.ValidationError("Invalid role. Must be ADMIN or SELLER")

        attrs['role'] = role
        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        # Ensure the user is a director to create other users
        print(validated_data)
        if user.role != User.DIRECTOR:
            raise serializers.ValidationError("Only Director can create users")
        
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
            age=validated_data.get('age', 0),
            AD=validated_data.get('AD',''),
            JSHSHR=validated_data.get('JSHSHR', ''),
            city=validated_data.get('city', ''),
            district=validated_data.get('district', ''),
            neighborhood=validated_data.get('neighborhood', ''),
            street=validated_data.get('street', ''),
            salary=validated_data.get('salary',0),
            KPI=validated_data.get("KPI", 0),

            created_by=user  # Set the creator as the director
        )
        return new_user

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
                  'rental_price', 'location', 'quantity']
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
    category = serializers.CharField(source="category.name")
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
    category = serializers.CharField(source="category.name")

    class Meta:
        model = Product
        fields = ['id', 'name', 'img', 'category', 'rental_price', 'status']

class SaleSerializer(serializers.ModelSerializer):
    product_detail = SaleProductDetailSerializer(source='product', read_only=True)
    # seller_username = serializers.CharField(source='seller.username', read_only=True)  # Read-only field for seller's username

    class Meta:
        model = Sale
        fields = ["product", "product_detail", "buyer", "sale_price", "sale_date", "quantity", "status"]

    def create(self, validated_data):
        # Get the authenticated user from the request context
        request = self.context.get('request')
        seller = request.user if request else None

        if not seller:
            raise serializers.ValidationError("Seller information is missing.")

        # Create the Sale instance with the authenticated user as the seller
        sale = Sale.objects.create(seller=seller, **validated_data)

        # Update product quantity after sale creation
        sale.product.quantity -= sale.quantity
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