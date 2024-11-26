from rest_framework import serializers
from .models import User, Product, Lending, Category


class UserListSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "role"]

class UserSerializer(serializers.ModelSerializer):
    # admin = serializers.CharField(source='created_by.username', read_only=True)
    created_users = UserListSerializer(many=True, read_only=True)  # Users created by the director
    
    class Meta:
        model = User
        fields = ['id', 'username', 'password', 'role', 'created_users']
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
        if user.role != User.DIRECTOR:
            raise serializers.ValidationError("Only Director can create users")
        
        # Create the user and set the created_by field
        new_user = User.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password'],
            role=validated_data.get('role', User.SELLER),
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
                 'lend_count', 'seller', 'admin', 'created_at', 'category', 'category_name']
        read_only_fields = ['status', 'lend_count', 'created_at', 'seller', 'admin']

    def validate(self, attrs):
        user = self.context['request'].user
        if user.role not in [User.ADMIN, User.DIRECTOR]:
            raise serializers.ValidationError("Only Admin or Director can create products")
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

class LendingSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    
    class Meta:
        model = Lending
        fields = ['id', 'product', 'product_name', 'borrower_name', 
                 'borrow_date', 'return_date', 'actual_return_date', 'status']
        read_only_fields = ['status']

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['seller'] = user
        return super().create(validated_data) 