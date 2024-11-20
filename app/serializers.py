from rest_framework import serializers
from .models import User, Product, Lending

class UserSerializer(serializers.ModelSerializer):
    admin = serializers.CharField(source='created_by.username', read_only=True)
    class Meta:
        model = User
        fields = ['id', 'username', 'password', 'role', 'admin']
        extra_kwargs = {
            'password': {'write_only': True},
            'role': {'read_only': True}
        }

    def create(self, validated_data):
        # Parolni hash qilish
        user = User.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password'],
            role=validated_data.get('role', User.SELLER),
            created_by=validated_data.get('created_by')
        )
        return user

class ProductSerializer(serializers.ModelSerializer):
    seller = serializers.CharField(source='created_by.username', read_only=True)
    admin = serializers.CharField(source='admin.username', read_only=True)
    
    class Meta:
        model = Product
        fields = ['id', 'name', 'description', 'price', 'status', 
                 'lend_count', 'seller', 'admin', 'created_at']
        read_only_fields = ['status', 'lend_count', 'created_at']

    def create(self, validated_data):
        user = self.context['request'].user
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