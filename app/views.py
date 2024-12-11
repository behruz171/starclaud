from rest_framework import viewsets, status, permissions, generics, exceptions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from .models import *
from .serializers import *
from django.db.models import Q

class LoginView(TokenObtainPairView):
    permission_classes = []
    serializer_class = UserSerializer

    def post(self, request, *args, **kwargs):
        username = request.data.get('username')
        password = request.data.get('password')
        
        if not username or not password:
            return Response({
                'status': 'error',
                'message': 'Username and password are required'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            refresh = RefreshToken.for_user(user)
            serializer = self.get_serializer(user)
            
            return Response({
                'status': 'success',
                'user': serializer.data,
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                }
            })
        
        return Response({
            'status': 'error',
            'message': 'Invalid credentials'
        }, status=status.HTTP_401_UNAUTHORIZED)

class DashboardView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user

    def retrieve(self, request, *args, **kwargs):
        user = self.get_object()
        response_data = {
            'user': self.get_serializer(user).data
        }
        
        if user.role == User.DIRECTOR:
            admins = User.objects.filter(role=User.ADMIN)
            sellers = User.objects.filter(role=User.SELLER)
            products = Product.objects.all()
            
            response_data.update({
                'admins': UserSerializer(admins, many=True).data,
                'sellers': UserSerializer(sellers, many=True).data,
                'products': ProductSerializer(products, many=True).data
            })
            
        elif user.role == User.ADMIN:
            sellers = user.created_users.all()
            products = Product.objects.filter(admin=user)
            
            response_data.update({
                'sellers': UserSerializer(sellers, many=True).data,
                'products': ProductSerializer(products, many=True).data
            })
            
        elif user.role == User.SELLER:
            own_products = Product.objects.filter(created_by=user)
            admin_products = Product.objects.filter(admin=user.created_by)
            lendings = Lending.objects.filter(seller=user)
            
            response_data.update({
                'own_products': ProductSerializer(own_products, many=True).data,
                'admin_products': ProductSerializer(admin_products, many=True).data,
                'lendings': LendingSerializer(lendings, many=True).data
            })
        
        return Response(response_data)

class ProductListCreateView(generics.ListCreateAPIView):
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        status_filter = self.request.query_params.get('status', None)  # URL dan status parametrini olish

        queryset = Product.objects.all()  # Barcha mahsulotlarni olish

        if user.role == User.DIRECTOR:
            # DIRECTOR barcha mahsulotlarni ko'radi
            pass
        elif user.role == User.ADMIN:
            queryset = queryset.filter(admin=user)  # ADMIN o'zining mahsulotlarini ko'radi
        elif user.role == User.SELLER:
            queryset = queryset.filter(
                Q(created_by=user) | 
                Q(admin=user.created_by)
            )  # SELLER o'z mahsulotlarini va admin tomonidan yaratilgan mahsulotlarni ko'radi

        if status_filter:
            queryset = queryset.filter(status=status_filter)  # Status bo'yicha filtr qo'shish

        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        if user.role not in [User.ADMIN, User.DIRECTOR]:
            raise exceptions.PermissionDenied("Only Admin or Director can create products")
        serializer.save()

class ProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == User.DIRECTOR:
            return Product.objects.all()
        if user.role == User.ADMIN:
            return Product.objects.all()
        elif user.role == User.SELLER:
            return Product.objects.all()
        return Product.objects.none()

    def perform_update(self, serializer):
        user = self.request.user
        product = self.get_object()

        # Only creator can update their products
        if product.created_by != user:
            raise exceptions.PermissionDenied(
                "You can only update your own products"
            )
        
        serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user
        
        # Only creator can delete their products
        if instance.created_by != user:
            raise exceptions.PermissionDenied(
                "You can only delete your own products"
            )
        
        instance.delete()

class ProductStatusUpdateView(generics.UpdateAPIView):
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Product.objects.filter(created_by=self.request.user)

    def patch(self, request, *args, **kwargs):
        product = self.get_object()
        new_status = request.data.get('status')
        
        if not new_status:
            return Response({
                'status': 'error',
                'message': 'Status is required'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        if new_status not in [choice[0] for choice in Product.STATUS_CHOICES]:
            return Response({
                'status': 'error',
                'message': 'Invalid status'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        product.status = new_status
        product.save()
        
        return Response({
            'status': 'success',
            'product': self.get_serializer(product).data
        })

class LendingViewSet(viewsets.ModelViewSet):
    serializer_class = LendingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == User.ADMIN or user.role == User.DIRECTOR:
            return Lending.objects.filter(product__admin=user)
        elif user.role == User.SELLER:
            return Lending.objects.filter(seller=user)
        return Lending.objects.none()

    def perform_create(self, serializer):
        # if self.request.user.role != User.SELLER:
        #     raise exceptions.PermissionDenied("Only sellers can create lendings")
            
        product = serializer.validated_data['product']
        if product.status != Product.AVAILABLE:
            raise serializers.ValidationError(
                {"product": "Product is not available for lending"}
            )
            
        if product.created_by != self.request.user and product.created_by.created_by != self.request.user:
            raise exceptions.PermissionDenied(
                "You can only lend your own products"
            )
            
        serializer.save()
    
    def perform_update(self, serializer):
        # Statusni yangilash uchun qo'shimcha tekshirishlar
        lending = self.get_object()
        if lending.status == Lending.RETURNED:
            raise exceptions.PermissionDenied("Cannot update a returned lending")
        
        serializer.save()

    @action(detail=True, methods=['post'])
    def return_product(self, request, pk=None):
        lending = self.get_object()
        if lending.status == Lending.RETURNED:
            return Response({
                'status': 'error',
                'message': 'Product is already returned'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        lending.status = Lending.RETURNED
        lending.actual_return_date = request.data.get('return_date')
        lending.save()
        
        return Response({
            'status': 'success',
            'lending': self.get_serializer(lending).data
        })

class SignUpView(generics.CreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def post(self, request, *args, **kwargs):
        user = request.user
        role = request.data.get('role', '').upper()

        # Faqat director user yarata oladi
        if user.role != User.DIRECTOR:
            return Response({
                'status': 'error',
                'message': 'Only Director can create users'
            }, status=status.HTTP_403_FORBIDDEN)

        # Director faqat ADMIN yoki SELLER yarata oladi
        if role not in [User.ADMIN, User.SELLER]:
            return Response({
                'status': 'error',
                'message': 'Director can only create admins or sellers'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Update request data with uppercase role
        request.data['role'] = role
        print(request.data)
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            # Har doim created_by = director
            new_user = serializer.save(
                role=role,
                created_by=request.user  # Director as creator
            )
            
            return Response({
                'status': 'success',
                'message': f'{role.capitalize()} created successfully',
                'user': UserSerializer(new_user).data
            }, status=status.HTTP_201_CREATED)
            
        return Response({
            'status': 'errorrr',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

class CategoryListCreateView(generics.ListCreateAPIView):
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        
        if user.role == User.DIRECTOR:
            return Category.objects.filter(created_by=user)  # Director can see their own categories
        elif user.role == User.ADMIN:
            return Category.objects.filter(created_by=user.created_by)  # Admin can see categories created by their Director
        elif user.role == User.SELLER:
            return Category.objects.filter(created_by=user.created_by)  # Seller can see categories created by their Director
        
        return Category.objects.none()  # No categories for other roles

    def perform_create(self, serializer):
        serializer.save()

class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer

    def get_queryset(self):
        user = self.request.user
        if user.role == User.DIRECTOR:
            return Category.objects.all()  # Directors can see all categories
        elif user.role == User.ADMIN:
            return Category.objects.filter(created_by=user.created_by)  # Admins see categories created by their director
        elif user.role == User.SELLER:
            return Category.objects.filter(created_by=user.created_by)  # Sellers see categories created by their director
        return Category.objects.none()  # No categories for other roles

class UserDetailView(generics.RetrieveAPIView):
    serializer_class = UserDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        user_id = self.kwargs.get('id')  # URL dan id ni olish
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None
        
        # Foydalanuvchining roliga qarab, kerakli foydalanuvchini qaytarish
        if user.role == User.SELLER:
            # Agar seller bo'lsa, o'zini, uni yaratgan direktor va direktor yaratgan adminlarni ko'rsatadi
            if user.created_by == self.request.user or user.created_by == self.request.user.created_by or user == self.request.user:
                return user  # O'zini yoki uni yaratgan direktor/adminni ko'rsatadi
        elif user.role == User.ADMIN:
            # Agar admin bo'lsa, faqat o'zining direktorini ko'rsatadi
            if user.created_by == self.request.user or user == self.request.user:
                return user
        elif user.role == User.DIRECTOR:
            # Agar director bo'lsa, faqat o'zini ko'rsatadi
            if user == self.request.user:
                return user
        
        return None  # Boshqa hollarda None qaytarish

    def retrieve(self, request, *args, **kwargs):
        user = self.get_object()
        if user is None:
            return Response({'status': 'error', 'message': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        
        return Response(self.get_serializer(user).data)

class UserListView(generics.ListAPIView):
    serializer_class = UserListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == User.DIRECTOR:
            return User.objects.filter(created_by=user)  # DIRECTOR barcha foydalanuvchilarni ko'radi
        elif user.role == User.ADMIN:
            return User.objects.filter(created_by=user.created_by)  # ADMIN o'zining direktoriga tegishli foydalanuvchilarni ko'radi
        return User.objects.none()  # Boshqa rollar uchun hech narsa ko'rsatilmaydi