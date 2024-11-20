from rest_framework import serializers
from .models import User, Product, Lending

class UserSerializer(serializers.ModelSerializer):
    admin = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'password', 'role', 'admin']
        extra_kwargs = {
            'password': {'write_only': True},
        }

    def validate(self, attrs):
        request = self.context.get('request')
        if not request or not request.user:
            raise serializers.ValidationError("Authentication required")

        # Faqat director user yarata oladi
        if request.user.role != User.DIRECTOR:
            raise serializers.ValidationError("Only Director can create users")

        role = attrs.get('role', '').upper()
        if role not in [User.ADMIN, User.SELLER]:
            raise serializers.ValidationError("Invalid role. Must be ADMIN or SELLER")

        attrs['role'] = role
        return attrs

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password'],
            role=validated_data['role'],
            created_by=validated_data['created_by']
        )
        return user

class ProductSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source='created_by.username', read_only=True)
    admin = serializers.CharField(source='admin.username', read_only=True)
    
    class Meta:
        model = Product
        fields = ['id', 'name', 'description', 'price', 'status', 
                 'lend_count', 'created_by', 'admin', 'created_at']
        read_only_fields = ['status', 'lend_count', 'created_at', 'created_by', 'admin']

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['created_by'] = user
        
        if user.role == User.ADMIN:
            validated_data['admin'] = user
        else:  # SELLER
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