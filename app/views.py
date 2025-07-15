from rest_framework import viewsets, status, permissions, generics, exceptions
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.hashers import make_password
from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import *
from .serializers import *
from django.db.models import Q, Avg
from django.utils import timezone
from django.db.models import Sum, F, Case, When, FloatField, Value, DecimalField, ExpressionWrapper, Count, IntegerField
from django.db.models.functions import Cast, Replace, Coalesce
from collections import defaultdict
from decimal import Decimal
import pytz
import calendar
from datetime import datetime, timedelta

def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }

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

class LoginAsUserView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Foydalanuvchi username va parolni olamiz
        username = request.data.get('username')
        superuser_password = request.data.get('password')

        # Superuserni tekshirish
        if not request.user.is_superuser:
            raise PermissionDenied("Only superusers can perform this action.")

        # Superuserni autentifikatsiya qilish
        superuser = authenticate(username=request.user.username, password=superuser_password)
        if not superuser:
            raise ValidationError("Superuser credentials are invalid.")

        # Foydalanuvchini topamiz
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Foydalanuvchi uchun token yaratamiz
        tokens = get_tokens_for_user(user)
        return Response({
            'message': f"You have successfully logged in as {username}.",
            'tokens': tokens,
        })

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
        # queryset = super().get_queryset()
        category = self.request.query_params.get('category', None)  # URL dan category parametrini olish
        name = self.request.query_params.get('name', None) # URL dan name param
        choice = self.request.query_params.get('choice', None)  # URL dan choice parametrini olish
        price_from = self.request.query_params.get('from', None)  # URL dan from parametrini olish
        price_to = self.request.query_params.get('to', None)  # URL dan to parametrini olish
        count_filter = self.request.query_params.get('count', None)  # URL dan count parametrini olish
        scan_code = self.request.query_params.get('scan_code', None) # URL dan scan code parametrini olish



        queryset = Product.objects.all()  # Barcha mahsulotlarni olish

        if user.role == User.DIRECTOR:
            # DIRECTOR barcha mahsulotlarni ko'radi
            queryset = queryset.filter(admin=user)
        elif user.role == User.ADMIN:
            queryset = queryset.filter(admin=user.created_by)  # ADMIN o'zining mahsulotlarini ko'radi
        elif user.role == User.SELLER:
            queryset = queryset.filter(
                Q(created_by=user) | 
                Q(admin=user.created_by)
            )  # SELLER o'z mahsulotlarini va admin tomonidan yaratilgan mahsulotlarni ko'radi
        
        if scan_code:
            queryset = queryset.filter(scan_code=scan_code)

        if status_filter:
            queryset = queryset.filter(status=status_filter)  # Status bo'yicha filtr qo'shish
        
        if category is not None:
            queryset = queryset.filter(category=category)  # category bo'yicha filtr
        if name is not None:
            queryset = queryset.filter(name__icontains=name.strip('"')) # category bo'yicha filtr
        

        if choice == 'rent':
            queryset = queryset.filter(choice="RENT")
            if price_from is not None and price_to is not None:
                queryset = queryset.filter(rental_price__gte=price_from, rental_price__lte=price_to)  # Rental price filtering
        elif choice == 'sell':
            queryset = queryset.filter(choice="SELL")
            if price_from is not None and price_to is not None:
                queryset = queryset.filter(price__gte=price_from, price__lte=price_to)  # Price filtering
        
        if choice == 'rent' and count_filter:
            # queryset = queryset.filter(choice="RENT")
            if count_filter in ['many', 'less']:
                # Calculate total lend count for each product
                # lend_counts = queryset.annotate(lend_count=Sum('lend_count'))  # Assuming 'lending' is the related name for the Lending model
                total_lend_count = queryset.aggregate(total=Sum('lend_count'))['total'] or 0  # Sum of lend_count
                product_count = queryset.count()  # Total number of products

                if product_count > 0:
                    average_lend_count = total_lend_count // product_count  # Calculate average lend count
                    print(average_lend_count)
                    if count_filter == 'many':
                        # Filter products with lend count greater than the average
                        queryset = queryset.filter(lend_count__gt=average_lend_count)
                    elif count_filter == 'less':
                        # Filter products with lend count less than the average
                        queryset = queryset.filter(lend_count__lt=average_lend_count)
                        
        elif choice == 'sell' and count_filter:
            # queryset = queryset.filter(choice="SELL")
            if count_filter in ['many', 'less']:
                # Calculate total lend count for each product
                total_lend_count = queryset.aggregate(
                    total_quantity=Coalesce(
                        Sum('sales__quantity', output_field=DecimalField()),
                        Sum('sales__product_weight'), output_field=DecimalField()
                    ) 
                )['total_quantity'] or 0  # Sum of lend_count
                product_count = queryset.count()  # Total number of products

                if product_count > 0:
                    average_lend_count = total_lend_count // product_count  # Calculate average lend count
                    if count_filter == 'many':
                        queryset = queryset.filter(
                            Q(sales__quantity__gt=average_lend_count) | 
                            Q(sales__quantity__isnull=True, sales__product_weight__gt=average_lend_count)
                        )
                    elif count_filter == 'less':
                        queryset = queryset.filter(
                            Q(sales__quantity__lt=average_lend_count) | 
                            Q(sales__quantity__isnull=True, sales__product_weight__lt=average_lend_count)
                        )

        return queryset


    def perform_create(self, serializer):
        user = self.request.user
        if user.role not in [User.ADMIN, User.DIRECTOR]:
            raise exceptions.PermissionDenied("Only Admin or Director can create products")
        
        if user.role == User.ADMIN:
            director = user.created_by  # Adminning yaratuvchisi (Director)
        else:
            director = user
        active_tariff = Tariff.objects.filter(user=director, status='active').first()

        # Agar direktor tarifga ulanmagan bo'lsa
        if not active_tariff:
            raise exceptions.ValidationError("Director is not linked to any active tariff.")

        # Agar tarifning statusi inactive bo'lsa
        if active_tariff.status == 'inactive':
            raise exceptions.ValidationError("The linked tariff is inactive.")

        # Agar product yaratish vaqti tarifning from_date va to_date oralig'ida bo'lmasa
        now = timezone.now()
        if not (active_tariff.from_date <= now <= active_tariff.to_date):
            raise exceptions.ValidationError("The product creation time is outside the active tariff period.")

        # Director va u yaratgan userlarning umumiy productlar sonini hisoblash
        total_products_count = Product.objects.filter(
            admin=director
        ).count() + Product.objects.filter(
            admin__in=director.created_users.all()
        ).count()

        # Agar umumiy productlar soni tarifdagi product_count dan oshsa
        if total_products_count >= active_tariff.product_count:
            raise exceptions.ValidationError("Mahsulotlarning umumiy soni faol tarifda ruxsat etilgan chegaradan oshib ketadi. Agar yana mahsulot qo`shmoqchi bo`lsangiz yangi tarif sotib oling")
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
        if product.admin != user and user.role == User.SELLER:
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
        if not user.is_authenticated:  # Foydalanuvchi autentifikatsiya qilinganligini tekshirish
           return Lending.objects.none()
        
        rental_price_from = self.request.query_params.get('from', None)
        rental_price_to = self.request.query_params.get('to', None)
        status = self.request.query_params.get('status', None)
        
        queryset = Lending.objects.none()
        if user.role == User.ADMIN or user.role == User.SELLER:
            queryset = Lending.objects.filter(product__admin=user.created_by, )
        elif user.role == User.DIRECTOR:
            queryset = Lending.objects.filter(product__admin=user)
        # elif user.role == User.SELLER:
        #     return Lending.objects.filter(seller=user)
        if status == 'returned':
            queryset = queryset.filter(status=Lending.RETURNED)
        elif status == 'lent':
            queryset = queryset.filter(status=Lending.LENT)
        if rental_price_from is not None and rental_price_to is not None:
            queryset = queryset.filter(product__rental_price__gte=rental_price_from, product__rental_price__lte=rental_price_to)
        
        count_filter = self.request.query_params.get('count', None)
        if count_filter in ['many', 'less']:
            # Calculate total lend count for each product
            total_lend_count = queryset.aggregate(total=Sum('product__lend_count'))['total'] or 0  # Sum of lend_count from Product
            product_count = queryset.values('product').distinct().count()
            if product_count > 0:
                average_lend_count = total_lend_count // product_count  # Calculate average lend count
                # print(total_lend_count, product_count)
                # Get the product IDs based on the lend count
                product_ids = queryset.values('product').annotate(lend_count=Sum('product__lend_count'))

                if count_filter == 'many':
                    # Filter products with lend count greater than the average
                    queryset = queryset.filter(product__in=product_ids.filter(lend_count__gt=average_lend_count).values('product'))
                elif count_filter == 'less':
                    # Filter products with lend count less than the average
                    queryset = queryset.filter(product__in=product_ids.filter(lend_count__lt=average_lend_count).values('product'))

        return queryset

    def perform_create(self, serializer):
        # if self.request.user.role != User.SELLER:
        #     raise exceptions.PermissionDenied("Only sellers can create lendings")
        if 'product' not in serializer.validated_data:
            raise serializers.ValidationError({"product": "This field is required."})
        product = serializer.validated_data['product']
        if product.status != Product.AVAILABLE:
            raise serializers.ValidationError(
                {"product": "Product is not available for lending"}
            )
        # if product.choice != 'RENT':
        #     raise serializers.ValidationError(
        #         {"product": "Product"}
        #     )
            
        if product.admin != self.request.user and product.admin != self.request.user.created_by:
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
        
        # Mahsulotni qaytarish
        lending.status = Lending.RETURNED
        lending.actual_return_date = request.data.get('return_date')
        lending.save()

        # Mahsulotning statusini AVAILABLE ga o'zgartirish
        product = lending.product
        product.status = Product.AVAILABLE
        product.save()

        return Response({
            'status': 'success',
            'lending': self.get_serializer(lending).data,
            'product': {
                'id': product.id,
                'status': product.status
            }
        })

class SignUpView(generics.CreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def post(self, request, *args, **kwargs):
        user = request.user
        role = request.data.get('role', '').upper()
        username = request.data.get('username', None)
        if User.objects.filter(username=username).exists():
            return Response({
                'status':"error",
                'message':"username already exists"
                },
                status=status.HTTP_401_UNAUTHORIZED)

        if user.role == User.DIRECTOR:
            director = user  # Adminning yaratuvchisi (Director)
        else:
            director = user.created_by
        active_tariff = Tariff.objects.filter(user=director, status='active').first()

        if not active_tariff:
            return Response({
                'status': 'error',
                'message': "Direktor hech qanday faol tarifga bog'lanmagan."
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if active_tariff.status == 'inactive':
            return Response({
                'status': 'error',
                'message': "Bog'langan tarif faol emas."
            }, status=status.HTTP_400_BAD_REQUEST)
        
        now = timezone.now()
        if not (active_tariff.from_date <= now <= active_tariff.to_date):
            return Response({
                'status': 'error',
                'message': 'Foydalanuvchini yaratish vaqti faol tarif davridan tashqarida.'
            }, status=status.HTTP_400_BAD_REQUEST)

        if user.role == User.DIRECTOR:
            if role not in [User.ADMIN, User.SELLER]:
                return Response({
                    'status': 'error',
                    'message': 'Direktor faqat administrator yoki sotuvchilar yaratishi mumkin'
                }, status=status.HTTP_400_BAD_REQUEST)
        elif user.role == User.ADMIN:
            if role != User.SELLER:
                return Response({
                    'status': 'error',
                    'message': 'Administrator faqat sotuvchilarni yaratishi mumkin'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        if role == User.SELLER:
            current_seller_count = User.objects.filter(created_by=director, role=User.SELLER).count()
            if current_seller_count >= active_tariff.seller_count:
                return Response({
                    'status': 'error',
                    'message': 'Sotuvchilar soni faol tarifdagi chegaradan oshib ketgan.'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        if role == User.ADMIN:
            current_admin_count = User.objects.filter(created_by=director, role=User.ADMIN).count()
            if current_admin_count >= active_tariff.admin_count:
                return Response({
                    'status': 'error',
                    'message': 'Adminlar soni faol tarifdagi limitdan oshib ketdi'
                }, status=status.HTTP_400_BAD_REQUEST)


        # Update request data with uppercase role
        request.data['role'] = role
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            # Admin seller yaratganda created_by directorga bog'lanadi
            if user.role == User.ADMIN and role == User.SELLER:
                new_user = serializer.save(
                    role=role,
                    created_by=user.created_by  # Director as creator
                )
            else:
                # Director yaratganda o'ziga bog'lanadi
                new_user = serializer.save(
                    role=role,
                    created_by=user  # Director as creator
                )
            
            return Response({
                'status': 'success',
                'message': f'{role.capitalize()} created successfully',
                'user': UserSerializer(new_user).data
            }, status=status.HTTP_201_CREATED)
            
        return Response({
            'status': 'error',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

class CategoryListCreateView(generics.ListCreateAPIView):
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        user = self.request.user
        
        if user.role == User.DIRECTOR:
            return Category.objects.filter(created_by=user)  # Director can see their own categories
        elif user.role == User.ADMIN:
            return Category.objects.filter(created_by=user.created_by)  # Admin can see categories created by their Director
        elif user.role == User.SELLER:
            return Category.objects.filter(created_by=user.created_by)  # Seller can see categories created by their Director
        
        return Category.objects.none()  # No categories for other roles
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({"results": serializer.data}, status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        user = self.request.user
        if user.role == User.ADMIN:
            director = user.created_by  # Adminning yaratuvchisi (Director)
        else:
            director = user
        active_tariff = Tariff.objects.filter(user=director, status='active').first()

        # Agar direktor tarifga ulanmagan bo'lsa
        if not active_tariff:
            raise exceptions.ValidationError("Director is not linked to any active tariff.")

        # Agar tarifning statusi inactive bo'lsa
        if active_tariff.status == 'inactive':
            raise exceptions.ValidationError("The linked tariff is inactive.")

        # Agar product yaratish vaqti tarifning from_date va to_date oralig'ida bo'lmasa
        now = timezone.now()
        if not (active_tariff.from_date <= now <= active_tariff.to_date):
            raise exceptions.ValidationError("The category creation time is outside the active tariff period.")
        
        current_category_count = Category.objects.filter(created_by=director).count()

        if current_category_count >= active_tariff.category_count:
            raise exceptions.ValidationError("Kategoriyalar soni faol tarifdagi chegaradan oshib ketadi")
        
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
        today = timezone.now()
        month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if today.month == 12:
            month_end = today.replace(year=today.year + 1, month=1, day=1)
        else:
            month_end = today.replace(month=today.month + 1, day=1)

        if user.role == User.DIRECTOR:
            return User.objects.filter(created_by=user).annotate(
                monthly_sales=Count(
                    'sales',
                    filter=Q(sales__sale_date__range=(month_start, month_end))
                ),
                monthly_lendings=Count(
                    'lendings',
                    filter=Q(lendings__borrow_date__range=(month_start, month_end))
                ),
                total_products_sold=Sum(
                    Case(
                        When(
                            sales__sale_date__range=(month_start, month_end),
                            sales__product_weight__isnull=False,
                            then=F('sales__product_weight')
                        ),
                        When(
                            sales__sale_date__range=(month_start, month_end),
                            then=F('sales__quantity')
                        ),
                        default=0,
                        output_field=DecimalField()
                    )
                )
            )  # DIRECTOR barcha foydalanuvchilarni ko'radi

        elif user.role == User.ADMIN:
            return User.objects.filter(created_by=user.created_by).annotate(
                monthly_sales=Count(
                    'sales',
                    filter=Q(sales__sale_date__range=(month_start, month_end))
                ),
                monthly_lendings=Count(
                    'lendings',
                    filter=Q(lendings__borrow_date__range=(month_start, month_end))
                ),
                total_products_sold=Sum(
                    Case(
                        When(
                            sales__sale_date__range=(month_start, month_end),
                            sales__product_weight__isnull=False,
                            then=F('sales__product_weight')
                        ),
                        When(
                            sales__sale_date__range=(month_start, month_end),
                            then=F('sales__quantity')
                        ),
                        default=0,
                        output_field=DecimalField()
                    )
                )
            )  # ADMIN o'zining direktoriga tegishli foydalanuvchilarni ko'radi

        return User.objects.none()



class SellerStatisticsView(generics.RetrieveAPIView):
    serializer_class = SellerStatisticsSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        user_id = self.kwargs.get('id')  # Get the seller ID from the URL
        try:
            user = User.objects.get(id=user_id, role=User.SELLER)
        except User.DoesNotExist:
            return None
        return user

    def retrieve(self, request, *args, **kwargs):
        seller = self.get_object()
        if seller is None:
            return Response({'status': 'error', 'message': 'Seller not found'}, status=status.HTTP_404_NOT_FOUND)
        
        return Response(self.get_serializer(seller).data)


class SaleViewSet(viewsets.ModelViewSet):
    serializer_class = SaleSerializer
    permission_classes = [IsAuthenticated]


    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, many=False)
        serializer.is_valid(raise_exception=True)
        sales = serializer.save()
        return Response(SaleSerializer(sales, many=True).data, status=status.HTTP_201_CREATED)

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Sale.objects.none()
        
        # Get the 'from' and 'to' query parameters for sale_price
        sale_price_from = self.request.query_params.get('from', None)
        sale_price_to = self.request.query_params.get('to', None)
        status = self.request.query_params.get('status', None)

        # Start with the base queryset
        queryset = Sale.objects.none()

        if user.role == User.ADMIN or user.role == User.SELLER:
            queryset = Sale.objects.filter(product__admin=user.created_by)
        elif user.role == User.DIRECTOR:
            queryset = Sale.objects.filter(product__admin=user)

        # Apply sale price filtering if 'from' and 'to' are provided
        if sale_price_from is not None and sale_price_to is not None:
            queryset = queryset.filter(sale_price__gte=sale_price_from, sale_price__lte=sale_price_to)
        if status == "cancelled":
            queryset = queryset.filter(status="CANCELLED")
        elif status == "pending":
            queryset = queryset.filter(status="PENDING")
        elif status == "completed":
            queryset = queryset.filter(status="COMPLETED")
        count_filter = self.request.query_params.get('count', None)
        if count_filter in ['many', 'less']:
            # Calculate total quantity sold and count of distinct products
            total_sales = queryset.aggregate(total_quantity=Sum('quantity'))['total_quantity'] or 0
            product_count = queryset.values('product').distinct().count()
            print(total_sales, product_count)
            if product_count > 0:
                average_sales = total_sales // product_count  # Calculate average sales

                # Get the product IDs based on the average sales
                product_ids = queryset.values('product').annotate(total_quantity=Sum('quantity'))

                if count_filter == 'many':
                    # Filter products with total quantity sold greater than the average
                    queryset = queryset.filter(product__in=product_ids.filter(total_quantity__gt=average_sales).values('product'))
                elif count_filter == 'less':
                    # Filter products with total quantity sold less than the average
                    queryset = queryset.filter(product__in=product_ids.filter(total_quantity__lt=average_sales).values('product'))

        return queryset


class UserImageView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.role == User.DIRECTOR:
            # If the user is a Director, return their own image
            serializer = UserImageSerializer(user, context={'request': request})
            return Response(serializer.data)

        elif user.role in [User.ADMIN, User.SELLER]:
            # If the user is an Admin or Seller, return the image of the user they created
            created_by_user = user.created_by  # Assuming 'created_by' is a ForeignKey to User
            if created_by_user:
                serializer = UserImageSerializer(created_by_user, context={'request': request})
                return Response(serializer.data)
            else:
                return Response({"error": "No created_by user found."}, status=404)

        return Response({"error": "Unauthorized access."}, status=403)

class StatisticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        user = request.user
        
        # Faqat Directorlar uchun
        if user.role != User.DIRECTOR:
            return Response({'status': 'error', 'message': 'Only directors can view statistics.'}, status=403)
        # Get the current date
        # Kunlik statistikalar (har ikki soatda)
        daily_revenue = defaultdict(float)
        now = timezone.now()

        for hour in range(0, 24, 2):  # Har 2 soatda
            start_time = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            end_time = start_time + timezone.timedelta(hours=2)
            
            # Sale daromadini hisoblash
            sale_revenue = Sale.objects.filter(
                sale_date__range=(start_time, end_time),
                product__created_by__in=[request.user] + list(request.user.created_users.all())
            ).annotate(total_price=F('sale_price') * F('quantity')).aggregate(total_revenue=Sum('total_price'))['total_revenue'] or 0

            # Lending daromadini hisoblash
            lending_revenue = Lending.objects.filter(
                borrow_date__range=(start_time, end_time),
                product__admin__in=[request.user] + list(request.user.created_users.all())
            ).aggregate(
                total_rental_revenue=Sum('product__rental_price')  # Faqat rental_price ni hisoblaymiz
            )['total_rental_revenue'] or 0
            
            # Umumiy daromadni yig'ish
            total_revenue = sale_revenue + lending_revenue
            daily_revenue[start_time.strftime("%H:%M")] = total_revenue

        # Haftalik statistikalar (Dushanbadan Yakshabgacha)
        weekly_revenue = defaultdict(float)
        now = timezone.now()
        start_of_week = now - timezone.timedelta(days=now.weekday())  # Dushanbadan boshlanadi

        for i in range(7):  # Haftada 7 kun
            day = start_of_week + timezone.timedelta(days=i)
            
            # Sale daromadini hisoblash
            # Sale daromadini hisoblash
            sale_revenue = Sale.objects.filter(
                sale_date__date=day,
                product__created_by__in=[request.user] + list(request.user.created_users.all())
            ).annotate(total_price=F('sale_price') * F('quantity')).aggregate(total_revenue=Sum('total_price'))['total_revenue'] or 0

            # Lending daromadini hisoblash
            lending_revenue = Lending.objects.filter(
                borrow_date__date=day,
                product__admin__in=[request.user] + list(request.user.created_users.all())
            ).aggregate(
                total_rental_revenue=Sum('product__rental_price')  # Faqat rental_price ni hisoblaymiz
            )['total_rental_revenue'] or 0
            
            # Umumiy daromadni yig'ish
            total_revenue = sale_revenue + lending_revenue
            weekly_revenue[day.strftime("%A")] = total_revenue  # Kun nomi

        # Monthly statistics (daily revenue for each day of the current month)
        monthly_revenue = defaultdict(float)
        start_of_month = now.replace(day=1)  # Oyning birinchi kuni
        end_of_month = (start_of_month + timezone.timedelta(days=31)).replace(day=1)  # Keyingi oyning birinchi kuni

        # Har bir kun uchun daromadni hisoblash
        for day in range(1, (end_of_month - start_of_month).days + 1):
            day_date = start_of_month.replace(day=day)
            
            # Sale daromadini hisoblash
            sale_revenue = Sale.objects.filter(
                sale_date__date=day_date,
                product__created_by__in=[request.user] + list(request.user.created_users.all())
            ).annotate(total_price=F('sale_price') * F('quantity')).aggregate(total_revenue=Sum('total_price'))['total_revenue'] or 0

            # Lending daromadini hisoblash
            lending_revenue = Lending.objects.filter(
                borrow_date__date=day_date,
                product__admin__in=[request.user] + list(request.user.created_users.all())
            ).aggregate(
                total_rental_revenue=Sum('product__rental_price')  # Faqat rental_price ni hisoblaymiz
            )['total_rental_revenue'] or 0
            
            # Umumiy daromadni yig'ish
            total_revenue = sale_revenue + lending_revenue
            monthly_revenue[day_date.strftime("%d")] = total_revenue  # Sanani formatlash

        # Yillik statistikalar (har bir oy uchun daromad)
        yearly_revenue = defaultdict(float)
        now = timezone.now()
        start_of_year = now.replace(month=1, day=1)

        for month in range(1, 13):  # 1 dan 12 gacha
            month_date = start_of_year.replace(month=month)
            
            # Sale daromadini hisoblash
            sale_revenue = Sale.objects.filter(
                sale_date__year=now.year,
                sale_date__month=month,
                product__created_by__in=[request.user] + list(request.user.created_users.all())
            ).annotate(total_price=F('sale_price') * F('quantity')).aggregate(total_revenue=Sum('total_price'))['total_revenue'] or 0

            # Lending daromadini hisoblash
            lending_revenue = Lending.objects.filter(
                borrow_date__year=now.year,
                borrow_date__month=month,
                product__admin__in=[request.user] + list(request.user.created_users.all())
            ).aggregate(
                total_rental_revenue=Sum('product__rental_price')  # Faqat rental_price ni hisoblaymiz
            )['total_rental_revenue'] or 0
            
            # Umumiy daromadni yig'ish
            total_revenue = sale_revenue + lending_revenue
            yearly_revenue[month_date.strftime("%B")] = total_revenue  # Oy nomi

        # Prepare the response data
        statistics = {
            'daily': dict(daily_revenue),
            'weekly': dict(weekly_revenue),
            'monthly': dict(monthly_revenue),
            'yearly': dict(yearly_revenue),
        }

        return Response(statistics)

class DailyStatisticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role != User.DIRECTOR:
            raise serializers.ValidationError({"error": "Siz director emasssiz shuning uchun tur yo'qol bo'ttan"})
        return Response(self.get_daily_statistics(user))

    def get_daily_statistics(self, user):
        uzbekistan_tz = pytz.timezone('Asia/Tashkent')
        now = timezone.now().astimezone(uzbekistan_tz)
        daily_revenue = defaultdict(float)
        daily_lend_statistic = {f"{i}%": 0 for i in range(0, 101, 25)}
        daily_returned_statistic = {f"{i}%": 0 for i in range(0, 101, 25)}
        total_count = 0
        total_return_count = 0
        users_product_count = defaultdict(int)

        work_start = user.work_start_time.hour
        work_end = user.work_end_time.hour
        start = now.replace(hour=work_start, minute=0, second=0, microsecond=0)  # 00:00
        end = now.replace(hour=work_end, minute=59, second=59, microsecond=999999)  # 23:59:59
        print(work_start, work_end)
        for hour in range(work_start, work_end+1, 1):  # Har 2 soatda
            uzbekistan_tz = pytz.timezone('Asia/Tashkent')
            start_time = now.replace(hour=hour, minute=0, second=0, microsecond=9)
            end_time = start_time + timezone.timedelta(hours=1)

            # Sale daromadini hisoblash
            sale_revenue = Sale.objects.filter(
                sale_date__range=(start_time, end_time),
                product__admin=user,
            ).exclude(
                status='CANCELLED'
            ).annotate(
                total_price=ExpressionWrapper(
                    Case(
                        When(product_weight__isnull=False, then=F('product_weight') * F('sale_price')),
                        default=F('sale_price') * F('quantity'),
                        output_field=DecimalField()  # Ensure this is included
                    ),
                    output_field=DecimalField()  # This is the missing argument
                )
            ).aggregate(
                total_revenue=Sum('total_price')
            )['total_revenue'] or Decimal(0)
            # Lending daromadini hisoblash
            lending_revenue = Lending.objects.filter(
                Q(status='RETURNED', return_date__range=(start_time, end_time)) | 
                Q(status='LENT', borrow_date__range=(start_time, end_time)),
                product__admin__in=[user] + list(user.created_users.all())
            ).annotate(
                percentage_value=Cast(Replace(F('percentage'), Value('%'), Value('')), FloatField()),
                effective_rental_price=Case(
                    When(status='RETURNED', then=F('product__rental_price')),
                    default=F('product__rental_price') * (F('percentage_value') / 100),
                    output_field=DecimalField()
                )
            ).aggregate(
                total_rental_revenue=Sum('effective_rental_price')
            )['total_rental_revenue'] or Decimal(0)

            daily_revenue[start_time.strftime("%H:%M")] = sale_revenue + lending_revenue

            # Lending Percentage statistikasi
            lendings = Lending.objects.filter(
                borrow_date__range=(start_time, end_time),
                product__admin=user
            )

            for lending in lendings:
                percentage = lending.percentage  # Percentage maydoni
                daily_lend_statistic[percentage] += 1

            total_count += lendings.count()

            returned_lendings = lendings.filter(status='RETURNED')  # Statusi 'returned' bo'lgan lendinglar
            total_return_count += returned_lendings.count()

            for returned_lending in returned_lendings:
                percentage_value = int(returned_lending.percentage.rstrip('%'))  # '%' ni olib tashlaymiz va int ga aylantiramiz
                returned_percentage = 100 - percentage_value  # 100 - Percentage
                returned_percentage_str = f"{returned_percentage}%"  # Natijani formatlash

                daily_returned_statistic[returned_percentage_str] += 1
            
            # Foydalanuvchilarni hisoblash
            created_users = user.created_users.all()

            for created_user in created_users:
                sales_count = Sale.objects.filter(
                    seller=created_user,
                    sale_date__range=(start, end),
                    product__admin=user
                ).count()
                lending_count = Lending.objects.filter(
                    borrow_date__range=(start, end),
                    product__admin=user,
                    seller=created_user
                ).count()
                count = lending_count + sales_count
                users_product_count[created_user.username] = count
        
        top_products = Sale.objects.filter(
            product__admin=user,
            sale_date__range=(start, end)
        ).exclude(
            status='CANCELLED'
        ).values(
            'product__id',
            'product__name',
            'product__price'
        ).annotate(
            total_quantity=Sum(
                Case(
                    When(product_weight__isnull=False, then=F('product_weight')),
                    default=F('quantity'),
                    output_field=DecimalField()
                )
            ),
            total_sales=Count('id')
        ).order_by('-total_quantity').distinct()[:10]

        # Get bottom 10 least sold products (excluding products from top 10)
        excluded_ids = [p['product__id'] for p in top_products]
        bottom_products = Sale.objects.filter(
            product__admin=user,
            sale_date__range=(start, end)
        ).exclude(
            product__id__in=excluded_ids
        ).values(
            'product__id',
            'product__name',
            'product__price'
        ).annotate(
            total_quantity=Sum(
                Case(
                    When(product_weight__isnull=False, then=F('product_weight')),
                    default=F('quantity'),
                    output_field=DecimalField()
                )
            ),
            total_sales=Count('id')
        ).order_by('total_quantity').exclude(
                status='CANCELLED'
        ).distinct()[:10]  # O'sish tartibida

        return {
            'statistic': dict(daily_revenue),
            'lend_statistic': dict(daily_lend_statistic),
            'return_statistic': dict(daily_returned_statistic),
            'total_count': total_count,
            'total_return_count': total_return_count,
            'users_product_count': dict(users_product_count),
            'top_products': [
                {
                    'id': product['product__id'],
                    'name': product['product__name'],
                    'price': product['product__price'],
                    'total_sales': product['total_sales']
                } 
                for product in top_products
            ],
            'bottom_products': [
                {
                    'id': product['product__id'],
                    'name': product['product__name'],
                    'price': product['product__price'],
                    'total_sales': product['total_sales']
                } 
                for product in bottom_products
            ]
        }


class WeeklyStatisticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role != User.DIRECTOR:
            raise serializers.ValidationError({"error": "Siz director emasssiz shuning uchun tur yo'qol bo'ttan"})
        return Response(self.get_weekly_statistics(user))

    def get_weekly_statistics(self, user):
        now = timezone.now()
        start_of_week = now - timezone.timedelta(days=now.weekday())  # Dushanbadan boshlanadi
        end_of_week = start_of_week + timezone.timedelta(days=6)
        weekly_revenue = defaultdict(float)
        weekly_lend_statistic = {f"{i}%": 0 for i in range(0, 101, 25)}
        weekly_returned_statistic = {f"{i}%": 0 for i in range(0, 101, 25)}
        users_product_count = defaultdict(int)

        
        total_count = 0
        total_return_count = 0

        for i in range(7):  # Haftada 7 kun
            day = start_of_week + timezone.timedelta(days=i)
            day_name = day.strftime("%A")

            # Sale daromadini hisoblash
            sale_revenue = Sale.objects.filter(
                sale_date__date=day,
                product__admin=user
            ).exclude(
                status='CANCELLED'
            ).annotate(total_price=ExpressionWrapper(
                    Case(
                        When(product_weight__isnull=False, then=F('product_weight') * F('sale_price')),
                        default=F('sale_price') * F('quantity'),
                        output_field=DecimalField()  # Ensure this is included
                    ),
                    output_field=DecimalField()  # This is the missing argument
                )).aggregate(Sum('total_price'))['total_price__sum'] or 0

            # Lending daromadini hisoblash
            lending_revenue = Lending.objects.filter(
                borrow_date__date=day,
                product__admin=user
            ).annotate(
                # '%' belgisini olib tashlaymiz va float ga aylantiramiz
                percentage_value=Cast(Replace(F('percentage'), Value('%'), Value('')), FloatField()),  # '%' belgisini olib tashlaymiz
                effective_rental_price=Case(
                    When(status='RETURNED', then=F('product__rental_price')),  # Agar status 'returned' bo'lsa, rental_price ni to'liq hisoblaymiz
                    default=F('product__rental_price') * (F('percentage_value') / 100),  # Aks holda, rental_price ni percentage ga ko'paytiramiz
                    output_field=DecimalField()  # Natijaning turini belgilaymiz
                )
            ).aggregate(
                total_rental_revenue=Sum('effective_rental_price')  # Hisoblangan rental_price ni yig'amiz
            )['total_rental_revenue'] or Decimal(0)

            weekly_revenue[day_name] = sale_revenue + lending_revenue

            lendings = Lending.objects.filter(
                borrow_date__date=day,
                product__admin=user
            )

            for lending in lendings:
                percentage = lending.percentage  # Percentage maydoni
                if percentage in weekly_lend_statistic:
                    weekly_lend_statistic[percentage] += 1
                else:
                    weekly_lend_statistic[percentage] = 1
            total_count += lendings.count()

            returned_lendings = lendings.filter(status='RETURNED')  # Statusi 'returned' bo'lgan lendinglar
            total_return_count += returned_lendings.count()

            for returned_lending in returned_lendings:
                # Percentage qiymatini to'g'ri formatlash
                percentage_value = int(returned_lending.percentage.rstrip('%'))  # '%' ni olib tashlaymiz va int ga aylantiramiz
                returned_percentage = 100 - percentage_value  # 100 - Percentage
                returned_percentage_str = f"{returned_percentage}%"  # Natijani formatlash

                if returned_percentage_str in weekly_returned_statistic:
                    weekly_returned_statistic[returned_percentage_str] += 1
                else:
                   weekly_returned_statistic[returned_percentage_str] = 1
            
            created_users = user.created_users.all()

            for created_user in created_users:
                sales_count = Sale.objects.filter(
                    seller=created_user,
                    sale_date__date__range=(start_of_week, end_of_week),
                    product__admin=user
                ).count()
                lending_count = Lending.objects.filter(
                    borrow_date__date__range=(start_of_week, end_of_week),
                    product__admin=user,
                    seller=created_user
                ).count()
                count = lending_count + sales_count
                users_product_count[created_user.username] = count

        top_products = Sale.objects.filter(
            product__admin=user,
            sale_date__range=(start_of_week, end_of_week)
        ).exclude(
            status='CANCELLED'
        ).values(
            'product__id',
            'product__name',
            'product__price'
        ).annotate(
            total_quantity=Sum(
                Case(
                    When(product_weight__isnull=False, then=F('product_weight')),
                    default=F('quantity'),
                    output_field=DecimalField()
                )
            ),
            total_sales=Count('id')
        ).order_by('-total_quantity').distinct()[:10]

        # Get bottom 10 least sold products (excluding products from top 10)
        excluded_ids = [p['product__id'] for p in top_products]
        bottom_products = Sale.objects.filter(
            product__admin=user,
            sale_date__range=(start_of_week, end_of_week)
        ).exclude(
            product__id__in=excluded_ids
        ).values(
            'product__id',
            'product__name',
            'product__price'
        ).annotate(
            total_quantity=Sum(
                Case(
                    When(product_weight__isnull=False, then=F('product_weight')),
                    default=F('quantity'),
                    output_field=DecimalField()
                )
            ),
            total_sales=Count('id')
        ).order_by('total_quantity').exclude(
                status='CANCELLED'
        ).distinct()[:10]  # O'sish tartibida


        return {
            "statistic":dict(weekly_revenue),
            'lend_statistic': dict(weekly_lend_statistic),
            'return_statistic': dict(weekly_returned_statistic),
            'total_count': total_count,
            'total_return_count': total_return_count,
            "users_product_count": dict(users_product_count),
            'top_products': [
                {
                    'id': product['product__id'],
                    'name': product['product__name'],
                    'price': product['product__price'],
                    'total_sales': product['total_sales']
                } 
                for product in top_products
            ],
            'bottom_products': [
                {
                    'id': product['product__id'],
                    'name': product['product__name'],
                    'price': product['product__price'],
                    'total_sales': product['total_sales']
                } 
                for product in bottom_products
            ]
        
        }


class MonthlyStatisticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role != User.DIRECTOR:
            raise serializers.ValidationError({"error": "Siz director emasssiz shuning uchun tur yo'qol bo'ttan"})
        return Response(self.get_monthly_statistics(user))

    def get_monthly_statistics(self, user):
        now = timezone.now()
        year = now.year
        month = now.month
        monthly_revenue = defaultdict(float)
        monthly_lend_statistic = {f"{i}%": 0 for i in range(0, 101, 25)}
        monthly_returned_statistic = {f"{i}%": 0 for i in range(0, 101, 25)}
        users_product_count = defaultdict(int)

        start_of_month = now.replace(day=1)
        last_day_of_month = calendar.monthrange(year, month)[1]
        end_of_month = now.replace(day=last_day_of_month)

        total_count = 0
        total_return_count = 0
        # Oyning har bir kunini hisoblash
        for day in range(1, 32):  # 1 dan 31 gacha
            try:
                date = timezone.datetime(year, month, day)
            except ValueError:
                # Agar bu oyda bunday kun bo'lmasa, davom etamiz
                continue

            # Sale daromadini hisoblash
            sale_revenue = Sale.objects.filter(
                sale_date__date=date,
                product__admin=user
            ).exclude(
                status='CANCELLED'
            ).annotate(total_price=ExpressionWrapper(
                    Case(
                        When(product_weight__isnull=False, then=F('product_weight') * F('sale_price')),
                        default=F('sale_price') * F('quantity'),
                        output_field=DecimalField()  # Ensure this is included
                    ),
                    output_field=DecimalField()  # This is the missing argument
                )).aggregate(Sum('total_price'))['total_price__sum'] or 0

            # Lending daromadini hisoblash
            lending_revenue = Lending.objects.filter(
                borrow_date__date=date,
                product__admin=user
            ).annotate(
                # '%' belgisini olib tashlaymiz va float ga aylantiramiz
                percentage_value=Cast(Replace(F('percentage'), Value('%'), Value('')), FloatField()),  # '%' belgisini olib tashlaymiz
                effective_rental_price=Case(
                    When(status='RETURNED', then=F('product__rental_price')),  # Agar status 'returned' bo'lsa, rental_price ni to'liq hisoblaymiz
                    default=F('product__rental_price') * (F('percentage_value') / 100),  # Aks holda, rental_price ni percentage ga ko'paytiramiz
                    output_field=DecimalField()  # Natijaning turini belgilaymiz
                )
            ).aggregate(
                total_rental_revenue=Sum('effective_rental_price')  # Hisoblangan rental_price ni yig'amiz
            )['total_rental_revenue'] or Decimal(0)

            monthly_revenue[date.strftime("%d")] = sale_revenue + lending_revenue  # Kun raqami

            lendings = Lending.objects.filter(
                borrow_date__date=date,
                product__admin=user
            )

            for lending in lendings:
                percentage = lending.percentage  # Percentage maydoni
                if percentage in monthly_lend_statistic:
                    monthly_lend_statistic[percentage] += 1
                else:
                    monthly_lend_statistic[percentage] = 1
            total_count += lendings.count()


            returned_lendings = lendings.filter(status='RETURNED')  # Statusi 'returned' bo'lgan lendinglar
            total_return_count += returned_lendings.count()

            for returned_lending in returned_lendings:
                # Percentage qiymatini to'g'ri formatlash
                percentage_value = int(returned_lending.percentage.rstrip('%'))  # '%' ni olib tashlaymiz va int ga aylantiramiz
                returned_percentage = 100 - percentage_value  # 100 - Percentage
                returned_percentage_str = f"{returned_percentage}%"  # Natijani formatlash

                if returned_percentage_str in monthly_returned_statistic:
                    monthly_returned_statistic[returned_percentage_str] += 1
                else:
                   monthly_returned_statistic[returned_percentage_str] = 1
            

            created_users = user.created_users.all()

            for created_user in created_users:
                sales_count = Sale.objects.filter(
                    seller=created_user,
                    sale_date__range=(start_of_month, end_of_month),
                    product__admin=user
                ).count()
                lending_count = Lending.objects.filter(
                    borrow_date__range=(start_of_month, end_of_month),
                    product__admin=user,
                    seller=created_user
                ).count()
                count = lending_count + sales_count
                users_product_count[created_user.username] = count

        top_products = Sale.objects.filter(
            product__admin=user,
            sale_date__range=(start_of_month, end_of_month)
        ).exclude(
            status='CANCELLED'
        ).values(
            'product__id',
            'product__name',
            'product__price'
        ).annotate(
            total_quantity=Sum(
                Case(
                    When(product_weight__isnull=False, then=F('product_weight')),
                    default=F('quantity'),
                    output_field=DecimalField()
                )
            ),
            total_sales=Count('id')
        ).order_by('-total_quantity').distinct()[:10]

        # Get bottom 10 least sold products (excluding products from top 10)
        excluded_ids = [p['product__id'] for p in top_products]
        bottom_products = Sale.objects.filter(
            product__admin=user,
            sale_date__range=(start_of_month, end_of_month)
        ).exclude(
            product__id__in=excluded_ids
        ).values(
            'product__id',
            'product__name',
            'product__price'
        ).annotate(
            total_quantity=Sum(
                Case(
                    When(product_weight__isnull=False, then=F('product_weight')),
                    default=F('quantity'),
                    output_field=DecimalField()
                )
            ),
            total_sales=Count('id')
        ).order_by('total_quantity').exclude(
                status='CANCELLED'
        ).distinct()[:10]  # O'sish tartibida


        return {
            "statistic":dict(monthly_revenue),
            'lend_statistic': dict(monthly_lend_statistic),
            'return_statistic': dict(monthly_returned_statistic),
            'total_count': total_count,
            'total_return_count': total_return_count,
            "users_product_count": dict(users_product_count),
            'top_products': [
                {
                    'id': product['product__id'],
                    'name': product['product__name'],
                    'price': product['product__price'],
                    'total_sales': product['total_sales']
                } 
                for product in top_products
            ],
            'bottom_products': [
                {
                    'id': product['product__id'],
                    'name': product['product__name'],
                    'price': product['product__price'],
                    'total_sales': product['total_sales']
                } 
                for product in bottom_products
            ]
        }

class YearlyStatisticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role != User.DIRECTOR:
            raise serializers.ValidationError({"error": "Siz director emasssiz shuning uchun tur yo'qol bo'ttan"})
        return Response(self.get_yearly_statistics(user))

    def get_yearly_statistics(self, user):
        now = timezone.now()
        current_year = now.year
        yearly_revenue = defaultdict(float)

        for year in range(current_year - 4, current_year + 1):  # 2 yil oldin va hozirgi yil
            # Sale daromadini hisoblash
            sale_revenue = Sale.objects.filter(
                sale_date__year=year,
                product__admin=user
            ).annotate(total_price=ExpressionWrapper(
                    Case(
                        When(product_weight__isnull=False, then=F('product_weight') * F('sale_price')),
                        default=F('sale_price') * F('quantity'),
                        output_field=DecimalField()  # Ensure this is included
                    ),
                    output_field=DecimalField()  # This is the missing argument
                )).aggregate(Sum('total_price'))['total_price__sum'] or 0

            # Lending daromadini hisoblash
            lending_revenue = Lending.objects.filter(
                borrow_date__year=year,
                product__admin=user
            ).aggregate(
                total_rental_revenue=Sum('product__rental_price')  # Faqat rental_price ni hisoblaymiz
            )['total_rental_revenue'] or 0

            yearly_revenue[str(year)] = sale_revenue + lending_revenue

        return dict(yearly_revenue)


class YearlyDetailStatisticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, year):
        user = request.user
        if user.role != User.DIRECTOR:
            raise serializers.ValidationError({"error": "Siz director emasssiz shuning uchun tur yo'qol bo'ttan"})
        return Response(self.get_yearly_statistics(user, year))

    def get_yearly_statistics(self, user, year):
        yearly_revenue = defaultdict(float)
        yearly_lend_statistic = {f"{i}%": 0 for i in range(0, 101, 25)}
        yearly_returned_statistic = {f"{i}%": 0 for i in range(0, 101, 25)}
        users_product_count = defaultdict(int)

        start_of_year = timezone.make_aware(datetime(year, 1, 1), timezone.get_current_timezone())
        end_of_year = timezone.make_aware(datetime(year, 12, 31, 23, 59, 59, 999999), timezone.get_current_timezone())

        total_count = 0
        total_return_count = 0

        # Har bir oy uchun daromadlarni hisoblash
        for month in range(1, 13):  # 1 dan 12 gacha
            month_name = timezone.datetime(year, month, 1).strftime("%B")

            # Sale daromadini hisoblash
            sale_revenue = Sale.objects.filter(
                sale_date__year=year,
                sale_date__month=month,
                product__admin=user
            ).exclude(
                status='CANCELLED'
            ).annotate(total_price=ExpressionWrapper(
                    Case(
                        When(product_weight__isnull=False, then=F('product_weight') * F('sale_price')),
                        default=F('sale_price') * F('quantity'),
                        output_field=DecimalField()  # Ensure this is included
                    ),
                    output_field=DecimalField()  # This is the missing argument
                )).aggregate(Sum('total_price'))['total_price__sum'] or 0

            # Lending daromadini hisoblash
            lending_revenue = Lending.objects.filter(
                borrow_date__year=year,
                borrow_date__month=month,
                product__admin=user
            ).annotate(
                # '%' belgisini olib tashlaymiz va float ga aylantiramiz
                percentage_value=Cast(Replace(F('percentage'), Value('%'), Value('')), FloatField()),  # '%' belgisini olib tashlaymiz
                effective_rental_price=Case(
                    When(status='RETURNED', then=F('product__rental_price')),  # Agar status 'returned' bo'lsa, rental_price ni to'liq hisoblaymiz
                    default=F('product__rental_price') * (F('percentage_value') / 100),  # Aks holda, rental_price ni percentage ga ko'paytiramiz
                    output_field=DecimalField()  # Natijaning turini belgilaymiz
                )
            ).aggregate(
                total_rental_revenue=Sum('effective_rental_price')  # Hisoblangan rental_price ni yig'amiz
            )['total_rental_revenue'] or Decimal(0)

            yearly_revenue[month_name.lower()] = sale_revenue + lending_revenue  # Oyning nomini kichik harflar bilan saqlaymiz

            lendings = Lending.objects.filter(
                borrow_date__year=year,
                borrow_date__month=month,
                product__admin=user
            )

            for lending in lendings:
                percentage = lending.percentage  # Percentage maydoni
                if percentage in yearly_lend_statistic:
                    yearly_lend_statistic[percentage] += 1
                else:
                    yearly_lend_statistic[percentage] = 1
            total_count += lendings.count()

            returned_lendings = lendings.filter(status='RETURNED')  # Statusi 'returned' bo'lgan lendinglar
            total_return_count += returned_lendings.count()

            for returned_lending in returned_lendings:
                # Percentage qiymatini to'g'ri formatlash
                percentage_value = int(returned_lending.percentage.rstrip('%'))  # '%' ni olib tashlaymiz va int ga aylantiramiz
                returned_percentage = 100 - percentage_value  # 100 - Percentage
                returned_percentage_str = f"{returned_percentage}%"  # Natijani formatlash

                if returned_percentage_str in yearly_returned_statistic:
                    yearly_returned_statistic[returned_percentage_str] += 1
                else:
                   yearly_returned_statistic[returned_percentage_str] = 1
        
        created_users = user.created_users.all()

        for created_user in created_users:
            sales_count = Sale.objects.filter(
                seller=created_user,
                    sale_date__range=(start_of_year, end_of_year),
                    product__admin=user
                ).count()
            lending_count = Lending.objects.filter(
                    borrow_date__range=(start_of_year, end_of_year),
                    product__admin=user,
                    seller=created_user
                ).count()
            count = lending_count + sales_count
            users_product_count[created_user.username] = count
        
        top_products = Sale.objects.filter(
            product__admin=user,
            sale_date__range=(start_of_year, end_of_year)
        ).exclude(
            status='CANCELLED'
        ).values(
            'product__id',
            'product__name',
            'product__price'
        ).annotate(
            total_quantity=Sum(
                Case(
                    When(product_weight__isnull=False, then=F('product_weight')),
                    default=F('quantity'),
                    output_field=DecimalField()
                )
            ),
            total_sales=Count('id')
        ).order_by('-total_quantity').distinct()[:10]

        # Get bottom 10 least sold products (excluding products from top 10)
        excluded_ids = [p['product__id'] for p in top_products]
        bottom_products = Sale.objects.filter(
            product__admin=user,
            sale_date__range=(start_of_year, end_of_year)
        ).exclude(
            product__id__in=excluded_ids
        ).values(
            'product__id',
            'product__name',
            'product__price'
        ).annotate(
            total_quantity=Sum(
                Case(
                    When(product_weight__isnull=False, then=F('product_weight')),
                    default=F('quantity'),
                    output_field=DecimalField()
                )
            ),
            total_sales=Count('id')
        ).order_by('total_quantity').exclude(
            status='CANCELLED'
        ).distinct()[:10]  # O'sish tartibida


        return {
            "statistic":dict(yearly_revenue),
            'lend_statistic': dict(yearly_lend_statistic),
            'return_statistic':dict(yearly_returned_statistic),
            'total_count': total_count,
            'total_return_count': total_return_count,
            "users_product_count":dict(users_product_count),
            'top_products': [
                {
                    'id': product['product__id'],
                    'name': product['product__name'],
                    'price': product['product__price'],
                    'total_sales': product['total_sales'],
                } 
                for product in top_products
            ],
            'bottom_products': [
                {
                    'id': product['product__id'],
                    'name': product['product__name'],
                    'price': product['product__price'],
                    'total_sales': product['total_sales'],
                } 
                for product in bottom_products
            ]
        }

class UserStatisticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        # Foydalanuvchini ID orqali olish
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'status': 'error', 'message': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        if request.user.role == User.SELLER:
            # Seller hech qanday ma'lumotlarni ko'ra olmaydi
            return Response({
                'error': 'Sellers do not have permission to view user information'
            }, status=status.HTTP_403_FORBIDDEN)
        if user.created_by is None:
        # Agar user director bo'lsa (created_by = None)
            if request.user != user:
                return Response({
                    'error': 'You do not have permission to view this user'
                }, status=status.HTTP_403_FORBIDDEN)
        # Director va Admin uchun tekshirish
        else:
        # Admin va boshqa userlar uchun
            if (request.user != user.created_by and          # Directori
                request.user not in user.created_by.created_users.filter(role=User.ADMIN)):  # Admini
                return Response({
                    'error': 'You do not have permission to view this user'
                }, status=status.HTTP_403_FORBIDDEN)
        # Statistika hisoblash
        statistics = {
            'daily': self.get_daily_statistics(user),
            'weekly': self.get_weekly_statistics(user),
            'monthly': self.get_monthly_statistics(user),
            'yearly': self.get_yearly_statistics(user),
        }

        return Response(statistics)

    def get_daily_statistics(self, user):
        uzbekistan_tz = pytz.timezone('Asia/Tashkent')
        now = timezone.now().astimezone(uzbekistan_tz)
        daily_revenue = defaultdict(int)
        work_start = user.work_start_time.hour
        work_end = user.work_end_time.hour
        start = now.replace(hour=work_start, minute=0, second=0, microsecond=0)  # 00:00
        end = now.replace(hour=work_end, minute=59, second=59, microsecond=999999)  # 23:59:59
        for hour in range(work_start, work_end+1,1):  # Har 2 soatda
            start_time = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            end_time = start_time + timezone.timedelta(hours=1)

            # Sale daromadini hisoblash
            sale_revenue = Sale.objects.filter(
                sale_date__range=(start_time, end_time),
                seller=user
            ).aggregate(total_quantity=Sum('quantity'))['total_quantity'] or 0

            # Lending daromadini hisoblash
            lending_revenue = Lending.objects.filter(
                borrow_date__range=(start_time, end_time),
                # product__admin__in=[user] + list(user.created_users.all())
                seller=user
            ).count()

            daily_revenue[start_time.strftime("%H:%M")] = sale_revenue + lending_revenue

        return dict(daily_revenue)

    def get_weekly_statistics(self, user):
        uzbekistan_tz = pytz.timezone('Asia/Tashkent')
        now = timezone.now().astimezone(uzbekistan_tz)
        start_of_week = now - timezone.timedelta(days=now.weekday())  # Dushanbadan boshlanadi
        weekly_revenue = defaultdict(float)

        for i in range(7):  # Haftada 7 kun
            day = start_of_week + timezone.timedelta(days=i)
            day_name = day.strftime("%A")

            # Sale daromadini hisoblash
            sale_revenue = Sale.objects.filter(
                sale_date__date=day,
                # product__created_by=user
                seller=user
            ).aggregate(total_quantity=Sum('quantity'))['total_quantity'] or 0

            # Lending daromadini hisoblash
            lending_revenue = Lending.objects.filter(
                borrow_date__date=day,
                # product__admin=user,
                seller=user
            ).count()

            weekly_revenue[day_name] = sale_revenue + lending_revenue

        return dict(weekly_revenue)

    def get_monthly_statistics(self, user):
        uzbekistan_tz = pytz.timezone('Asia/Tashkent')
        now = timezone.now().astimezone(uzbekistan_tz)
        month = now.month
        year = now.year
        monthly_revenue = defaultdict(float)

        start_of_month = now.replace(day=1)
        last_day_of_month = calendar.monthrange(year, month)[1]
        end_of_month = now.replace(day=last_day_of_month)

        for day in range(1, 32):  # 1 dan 31 gacha
            try:
                date = timezone.datetime(year, month, day)
            except ValueError:
                # Agar bu oyda bunday kun bo'lmasa, davom etamiz
                continue

            sale_revenue = Sale.objects.filter(
                sale_date__date=date,
                # product__created_by=user,
                seller=user
            ).aggregate(total_quantity=Sum('quantity'))['total_quantity'] or 0

            # Lending daromadini hisoblash
            lending_revenue = Lending.objects.filter(
                borrow_date__date=date,
                # product__admin=user,
                seller=user
            ).count()

            monthly_revenue[date.strftime("%d")] = sale_revenue + lending_revenue  # Kun raqami

        return dict(monthly_revenue)

    def get_yearly_statistics(self, user):
        uzbekistan_tz = pytz.timezone('Asia/Tashkent')
        now = timezone.now().astimezone(uzbekistan_tz)
        yearly_revenue = defaultdict(float)
        start_of_year = now.replace(month=1, day=1)

        for month in range(1, 13):  # 1 dan 12 gacha
            month_date = start_of_year.replace(month=month)  # 2 yil oldin va hozirgi yil
            # Sale daromadini hisoblash
            sale_revenue = Sale.objects.filter(
                sale_date__year=now.year,
                sale_date__month=month,
                seller=user
            ).aggregate(total_quantity=Sum('quantity'))['total_quantity'] or 0

            # Lending daromadini hisoblash
            lending_revenue = Lending.objects.filter(
                borrow_date__year=now.year,
                borrow_date__month=month,
                seller=user
            ).count()

            total_revenue = sale_revenue + lending_revenue
            yearly_revenue[month_date.strftime("%B")] = total_revenue

        return dict(yearly_revenue)


class UserMonthlyIncomeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, user_id):
        # Parse the start_date and end_date from the request data
        start_date_str = request.data.get('start_date')
        end_date_str = request.data.get('end_date')

        # Validate the dates
        if not start_date_str or not end_date_str:
            return Response({"error": "Both start_date and end_date are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Convert strings to datetime objects
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        # Ensure the dates are in the same month
        if start_date.year != end_date.year or start_date.month != end_date.month:
            return Response({"error": "start_date and end_date must be within the same month."}, status=status.HTTP_400_BAD_REQUEST)

        # Make dates timezone aware
        uzbekistan_tz = pytz.timezone('Asia/Tashkent')
        start_date = timezone.make_aware(start_date, uzbekistan_tz)
        end_date = timezone.make_aware(end_date, uzbekistan_tz)

        # Get the user
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        if request.user != user and request.user != user.created_by:
            return Response({"error": "Siz bu user emassiz"})

        # Calculate the number of sales
        sales_count = Sale.objects.filter(
            seller=user,
            sale_date__range=(start_date, end_date)
        ).count()

        sales_kpi_total = Sale.objects.filter(
            seller=user,
            sale_date__range=(start_date, end_date)
        ).annotate(
            kpi_value=ExpressionWrapper(
                Case(
                    When(quantity__isnull=False, then=F('sale_price') * F('quantity') * user.KPI / 100),  # Agar quantity mavjud bo'lsa
                    When(product_weight__isnull=False, then=F('sale_price') * F('product_weight') * user.KPI / 100),  # Agar quantity mavjud bo'lmasa, product_weight ni olish
                    default=0,  # Agar ikkalasi ham bo'lmasa, 0
                    output_field=DecimalField()
                ),
                output_field=DecimalField()
            )
        ).aggregate(total_kpi=Sum('kpi_value'))['total_kpi'] or Decimal(0)

        # Calculate the number of lendings
        lending_count = Lending.objects.filter(
            seller=user,
            borrow_date__range=(start_date, end_date),
            status="RETURNED"
        ).count()
        kpi = user.KPI

        lending_kpi_total = Lending.objects.filter(
            seller=user,
            borrow_date__range=(start_date, end_date),
            status='RETURNED'
        ).annotate(
            kpi_value=ExpressionWrapper(
                F('product__rental_price') * user.KPI / 100,
                output_field=DecimalField()
            )
        ).aggregate(total_kpi=Sum('kpi_value'))['total_kpi'] or Decimal(0)

        response_data = {
            "username": user.username,
            "sales_count": sales_count,
            "lending_count": lending_count,
            "KPI": kpi,
            "sales_kpi_total": sales_kpi_total,
            "lending_kpi_total": lending_kpi_total,
            "common_kpi_total": sales_kpi_total + lending_kpi_total
        }
        last_day_of_month = calendar.monthrange(start_date.year, start_date.month)[1]
        if start_date.day == 1 and end_date.day == last_day_of_month:
            response_data["salary"] = user.salary
            response_data["salary_kpi"] = user.salary + sales_kpi_total + lending_kpi_total
        # Return the results
        return Response(response_data, status=status.HTTP_200_OK)





class UserManagementView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, user_id):
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None

    def patch(self, request, user_id):
        """
        Foydalanuvchini yangilash.
        """
        user_to_update = self.get_object(user_id)
        if not user_to_update:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        current_user = request.user

        # Permissions tekshiruvi
        if current_user.role == User.DIRECTOR:
            # Director faqat o'zi yaratgan userlarni yangilay oladi
            if user_to_update.created_by != current_user:
                return Response({"error": "You do not have permission to update this user."}, status=status.HTTP_403_FORBIDDEN)
        elif user_to_update != current_user:
            # Oddiy foydalanuvchilar faqat o'zini yangilay oladi
            return Response({"error": "You can only update your own profile."}, status=status.HTTP_403_FORBIDDEN)

        # Ma'lumotlarni olish
        data = request.data
        password = data.get('password')

        # Parolni alohida yangilash
        if password:
            user_to_update.password = make_password(password)

        # Qolgan ma'lumotlarni yangilash
        for key, value in data.items():
            if key != 'password':  # Parolni alohida ishladik
                setattr(user_to_update, key, value)

        # Ma'lumotlarni saqlash
        user_to_update.save()

        return Response({"success": "User updated successfully."}, status=status.HTTP_200_OK)
    

    def delete(self, request, user_id):
        user_to_delete = self.get_object(user_id)
        if not user_to_delete:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        current_user = request.user

        # Check permissions
        if current_user.role != User.DIRECTOR and user_to_delete.created_by != current_user:
            return Response({"error": "You do not have permission to delete this user."}, status=status.HTTP_403_FORBIDDEN)

        user_to_delete.delete()
        return Response({"success": "User deleted successfully."}, status=status.HTTP_200_OK)


class VideoQollanmaListView(generics.ListAPIView):
    serializer_class = VideoQollanmaSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return VideoQollanma.objects.filter(role=user.role)


class TariffCreateView(generics.CreateAPIView):
    serializer_class = TariffSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        user = self.request.user
        if user.role == User.DIRECTOR:  # Faqat direktorlar uchun
            # Tariff yaratishdan oldin cheklovlarni tekshirish
            if serializer.validated_data['admin_count'] < 10:  # Masalan, 10 dan oshmasligi kerak
                raise serializers.ValidationError("Admin soni 10 dan kam bolmasligi kerak.")
            if serializer.validated_data['seller_count'] < 10:  # Masalan, 10 dan oshmasligi kerak
                raise serializers.ValidationError("Seller soni 10 dan kam bolmasligi kerak.")
            if serializer.validated_data['product_count'] < 100:  # Masalan, 100 dan oshmasligi kerak
                raise serializers.ValidationError("Product soni 100 dan kam bolmasligi kerak.")
            serializer.save(user=user)  # Directorni saqlash
        else:
            raise permissions.PermissionDenied("Faqat direktorlar tarif yaratishi mumkin.")



class TariffRetrieveView(generics.RetrieveAPIView):
    serializer_class = TariffDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        user = self.request.user
        # Faqat direktorlar uchun aktiv tarifni olish
        tariff = Tariff.objects.filter(user=user, status='active').first()
        if not tariff:
            raise exceptions.NotFound("No active tariff found for this director.")
        return tariff



class CartView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        cart, created = Cart.objects.get_or_create(seller=request.user)
        serializer = CartSerializer(cart)
        return Response(serializer.data)

class CartAddItemView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        cart, created = Cart.objects.get_or_create(seller=request.user)
        product_id = request.data.get('product_id')
        quantity = int(request.data.get('quantity', 1))
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response({"error": "Mahsulot topilmadi"}, status=404)
        item, created = CartItem.objects.get_or_create(cart=cart, product=product)
        if not created:
            item.quantity += quantity
        else:
            item.quantity = quantity
        item.save()
        return Response({"success": True, "message": "Mahsulot korzinkaga qo'shildi"})

class CartCheckoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        cart = Cart.objects.filter(seller=request.user).first()
        if not cart or not cart.items.exists():
            return Response({"error": "Korzinka bo'sh"}, status=400)
        buyer = request.data.get('buyer', '')
        sales = []
        total_price = 0
        for item in cart.items.all():
            sale = Sale.objects.create(
                product=item.product,
                seller=request.user,
                buyer=buyer,
                sale_price=item.product.price * item.quantity,
                quantity=item.quantity,
                status='COMPLETED'
            )
            sales.append({
                "product_id": item.product.id,
                "product_name": item.product.name,
                "quantity": item.quantity,
                "sale_price": str(sale.sale_price)
            })
            total_price += sale.sale_price
        cart.items.all().delete()  # Korzinkani tozalash
        return Response({
            "success": True,
            "message": "Sotuv muvaffaqiyatli amalga oshirildi",
            "sales": sales,
            "total_price": str(total_price)
        })

class SoldProductsHistoryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        sales = Sale.objects.filter(seller=request.user).order_by('-sale_date')
        result = []
        for sale in sales:
            result.append({
                "date": sale.sale_date.date(),
                "buyer": sale.buyer,
                "product_id": sale.product.id,
                "product_name": sale.product.name,
                "product_category": sale.product.category.name if sale.product.category else None,
                "product_price": str(sale.sale_price),
                "product_quantity": sale.quantity,
            })
        return Response(result)


class CashWithdrawalView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CashWithdrawalSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(seller=request.user)
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

    def get(self, request):
        withdrawals = CashWithdrawal.objects.filter(seller=request.user).order_by('-created_at')
        serializer = CashWithdrawalSerializer(withdrawals, many=True)
        return Response(serializer.data)


def calculate_growth(current, previous):
    if previous == 0:
        return "+0%"
    growth = ((current - previous) / previous) * 100
    sign = "+" if growth >= 0 else ""
    return f"{sign}{growth:.1f}%"


class StatisticsReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        period = request.GET.get('period')  # 'day', 'week', 'month', 'year'

        sales = Sale.objects.all()
        lendings = Lending.objects.all()
        withdrawals = CashWithdrawal.objects.all()

        now = timezone.now()

        # Sana bo‘yicha filter
        if start_date and end_date:
            try:
                start = datetime.strptime(start_date, "%Y-%m-%d")
                end = datetime.strptime(end_date, "%Y-%m-%d")
                sales = sales.filter(sale_date__date__gte=start, sale_date__date__lte=end)
                lendings = lendings.filter(borrow_date__date__gte=start, borrow_date__date__lte=end)
                withdrawals = withdrawals.filter(created_at__date__gte=start, created_at__date__lte=end)
            except Exception:
                pass

        # Period bo‘yicha filter va oldingi davrni aniqlash
        if period == "year":
            current_year = now.year
            prev_year = current_year - 1
            sales_current = sales.filter(sale_date__year=current_year)
            sales_prev = sales.filter(sale_date__year=prev_year)
            lendings_current = lendings.filter(borrow_date__year=current_year)
            lendings_prev = lendings.filter(borrow_date__year=prev_year)
            withdrawals_current = withdrawals.filter(created_at__year=current_year)
            withdrawals_prev = withdrawals.filter(created_at__year=prev_year)
        elif period == "month":
            current_year = now.year
            current_month = now.month
            if current_month == 1:
                prev_month = 12
                prev_year = current_year - 1
            else:
                prev_month = current_month - 1
                prev_year = current_year
            sales_current = sales.filter(sale_date__year=current_year, sale_date__month=current_month)
            sales_prev = sales.filter(sale_date__year=prev_year, sale_date__month=prev_month)
            lendings_current = lendings.filter(borrow_date__year=current_year, borrow_date__month=current_month)
            lendings_prev = lendings.filter(borrow_date__year=prev_year, borrow_date__month=prev_month)
            withdrawals_current = withdrawals.filter(created_at__year=current_year, created_at__month=current_month)
            withdrawals_prev = withdrawals.filter(created_at__year=prev_year, created_at__month=prev_month)
        elif period == "week":
            current_week = now.isocalendar()[1]
            current_year = now.year
            prev_week = current_week - 1 if current_week > 1 else 52
            prev_year = current_year if current_week > 1 else current_year - 1
            sales_current = sales.filter(sale_date__isocalendar__week=current_week, sale_date__year=current_year)
            sales_prev = sales.filter(sale_date__isocalendar__week=prev_week, sale_date__year=prev_year)
            lendings_current = lendings.filter(borrow_date__isocalendar__week=current_week, borrow_date__year=current_year)
            lendings_prev = lendings.filter(borrow_date__isocalendar__week=prev_week, borrow_date__year=prev_year)
            withdrawals_current = withdrawals.filter(created_at__isocalendar__week=current_week, created_at__year=current_year)
            withdrawals_prev = withdrawals.filter(created_at__isocalendar__week=prev_week, created_at__year=prev_year)
        elif period == "day":
            today = now.date()
            yesterday = today - timezone.timedelta(days=1)
            sales_current = sales.filter(sale_date__date=today)
            sales_prev = sales.filter(sale_date__date=yesterday)
            lendings_current = lendings.filter(borrow_date__date=today)
            lendings_prev = lendings.filter(borrow_date__date=yesterday)
            withdrawals_current = withdrawals.filter(created_at__date=today)
            withdrawals_prev = withdrawals.filter(created_at__date=yesterday)
        else:
            # Default: umumiy
            sales_current = sales
            sales_prev = sales.none()
            lendings_current = lendings
            lendings_prev = lendings.none()
            withdrawals_current = withdrawals
            withdrawals_prev = withdrawals.none()

        # Statistika hisoblash
        total_revenue = sales_current.aggregate(total=Sum('sale_price'))['total'] or 0
        total_revenue_prev = sales_prev.aggregate(total=Sum('sale_price'))['total'] or 0

        lending_revenue = lendings_current.aggregate(total=Sum('product__rental_price'))['total'] or 0
        lending_revenue_prev = lendings_prev.aggregate(total=Sum('product__rental_price'))['total'] or 0

        total_expense = withdrawals_current.aggregate(total=Sum('amount'))['total'] or 0
        total_expense_prev = withdrawals_prev.aggregate(total=Sum('amount'))['total'] or 0

        net_profit = total_revenue + lending_revenue - total_expense
        net_profit_prev = (total_revenue_prev + lending_revenue_prev) - total_expense_prev

        # O‘sish foizlarini hisoblash
        sales_growth = calculate_growth(total_revenue, total_revenue_prev)
        lending_growth = calculate_growth(lending_revenue, lending_revenue_prev)
        profit_growth = calculate_growth(net_profit, net_profit_prev)
        expense_growth = calculate_growth(total_expense, total_expense_prev)
        total_growth = calculate_growth(total_revenue + lending_revenue, total_revenue_prev + lending_revenue_prev)

        data = {
            "total_revenue": total_revenue,
            "sales_revenue": total_revenue,
            "lending_revenue": lending_revenue,
            "total_expense": total_expense,
            "net_profit": net_profit,
            "growth": {
                "total": total_growth,
                "sales": sales_growth,
                "lending": lending_growth,
                "profit": profit_growth,
                "expense": expense_growth
            }
        }
        return Response(data)


class IncomeExpenseDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Filterlar
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        sales = Sale.objects.all()
        lendings = Lending.objects.all()
        withdrawals = CashWithdrawal.objects.all()

        if start_date and end_date:
            try:
                start = datetime.strptime(start_date, "%Y-%m-%d")
                end = datetime.strptime(end_date, "%Y-%m-%d")
                sales = sales.filter(sale_date__date__gte=start, sale_date__date__lte=end)
                lendings = lendings.filter(borrow_date__date__gte=start, borrow_date__date__lte=end)
                withdrawals = withdrawals.filter(created_at__date__gte=start, created_at__date__lte=end)
            except Exception:
                pass

        # Kirim tafsilotlari
        sales_income = sales.aggregate(total=Sum('sale_price'))['total'] or 0
        lending_income = lendings.aggregate(total=Sum('product__rental_price'))['total'] or 0
        other_income = 0  # Agar boshqa daromadlar bo'lsa, shu yerda hisoblang

        # Chiqim tafsilotlari
        def get_expense_sum(comment):
            return withdrawals.filter(comment__iexact=comment).aggregate(total=Sum('amount'))['total'] or 0

        expense_details = {
            "Xodimlar maoshi": get_expense_sum("Xodimlar maoshi"),
            "Ijara haqi": get_expense_sum("Ijara haqi"),
            "Kommunal xizmatlar": get_expense_sum("Kommunal xizmatlar"),
            "Marketing": get_expense_sum("Marketing"),
            "Ta'mirlash": get_expense_sum("Ta'mirlash"),
            "Boshqa xarajatlar": withdrawals.exclude(
                comment__in=[
                    "Xodimlar maoshi", "Ijara haqi", "Kommunal xizmatlar", "Marketing", "Ta'mirlash"
                ]
            ).aggregate(total=Sum('amount'))['total'] or 0
        }

        data = {
            "income_detail": {
                "sales_income": sales_income,
                "lending_income": lending_income,
                "other_income": other_income
            },
            "expense_detail": expense_details
        }
        return Response(data)



class IncomeExpenseDynamicsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        period = request.GET.get('period', 'month')  # 'year', 'month', 'week', 'day'
        year = int(request.GET.get('year', timezone.now().year))

        sales = Sale.objects.all()
        lendings = Lending.objects.all()
        withdrawals = CashWithdrawal.objects.all()

        result = []

        if period == 'year':
            # Har bir yil uchun
            start_year = year - 4  # oxirgi 5 yil
            for y in range(start_year, year + 1):
                sales_sum = sales.filter(sale_date__year=y).aggregate(total=Sum('sale_price'))['total'] or 0
                lending_sum = lendings.filter(borrow_date__year=y).aggregate(total=Sum('product__rental_price'))['total'] or 0
                expense_sum = withdrawals.filter(created_at__year=y).aggregate(total=Sum('amount'))['total'] or 0
                net_profit = sales_sum + lending_sum - expense_sum
                result.append({
                    "label": str(y),
                    "income": sales_sum + lending_sum,
                    "expense": expense_sum,
                    "net_profit": net_profit
                })
        elif period == 'month':
            # 12 oy uchun
            for m in range(1, 13):
                sales_sum = sales.filter(sale_date__year=year, sale_date__month=m).aggregate(total=Sum('sale_price'))['total'] or 0
                lending_sum = lendings.filter(borrow_date__year=year, borrow_date__month=m).aggregate(total=Sum('product__rental_price'))['total'] or 0
                expense_sum = withdrawals.filter(created_at__year=year, created_at__month=m).aggregate(total=Sum('amount'))['total'] or 0
                net_profit = sales_sum + lending_sum - expense_sum
                result.append({
                    "label": datetime(year, m, 1).strftime('%b'),  # 'Yan', 'Fev', ...
                    "income": sales_sum + lending_sum,
                    "expense": expense_sum,
                    "net_profit": net_profit
                })
        elif period == 'week':
            # 1 yil ichidagi 52 hafta uchun
            for w in range(1, 53):
                sales_sum = sales.filter(sale_date__year=year, sale_date__week=w).aggregate(total=Sum('sale_price'))['total'] or 0
                lending_sum = lendings.filter(borrow_date__year=year, borrow_date__week=w).aggregate(total=Sum('product__rental_price'))['total'] or 0
                expense_sum = withdrawals.filter(created_at__year=year, created_at__week=w).aggregate(total=Sum('amount'))['total'] or 0
                net_profit = sales_sum + lending_sum - expense_sum
                result.append({
                    "label": f"{w}-hafta",
                    "income": sales_sum + lending_sum,
                    "expense": expense_sum,
                    "net_profit": net_profit
                })
        elif period == 'day':
            # Oxirgi 30 kun uchun
            today = timezone.now().date()
            for i in range(29, -1, -1):
                d = today - timedelta(days=i)
                sales_sum = sales.filter(sale_date__date=d).aggregate(total=Sum('sale_price'))['total'] or 0
                lending_sum = lendings.filter(borrow_date__date=d).aggregate(total=Sum('product__rental_price'))['total'] or 0
                expense_sum = withdrawals.filter(created_at__date=d).aggregate(total=Sum('amount'))['total'] or 0
                net_profit = sales_sum + lending_sum - expense_sum
                result.append({
                    "label": d.strftime('%d-%b'),
                    "income": sales_sum + lending_sum,
                    "expense": expense_sum,
                    "net_profit": net_profit
                })
        else:
            return Response({"error": "period noto'g'ri"}, status=400)

        return Response(result)


class RevenueDynamicsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        period = request.GET.get('period', 'month')  # 'year', 'month', 'week', 'day'
        year = int(request.GET.get('year', timezone.now().year))

        sales = Sale.objects.all()
        lendings = Lending.objects.all()
        result = []

        if period == 'year':
            start_year = year - 4
            for y in range(start_year, year + 1):
                sales_sum = sales.filter(sale_date__year=y).aggregate(total=Sum('sale_price'))['total'] or 0
                lending_sum = lendings.filter(borrow_date__year=y).aggregate(total=Sum('product__rental_price'))['total'] or 0
                result.append({
                    "label": str(y),
                    "total_revenue": sales_sum + lending_sum,
                    "sales_revenue": sales_sum,
                    "lending_revenue": lending_sum
                })
        elif period == 'month':
            for m in range(1, 13):
                sales_sum = sales.filter(sale_date__year=year, sale_date__month=m).aggregate(total=Sum('sale_price'))['total'] or 0
                lending_sum = lendings.filter(borrow_date__year=year, borrow_date__month=m).aggregate(total=Sum('product__rental_price'))['total'] or 0
                result.append({
                    "label": datetime(year, m, 1).strftime('%b'),
                    "total_revenue": sales_sum + lending_sum,
                    "sales_revenue": sales_sum,
                    "lending_revenue": lending_sum
                })
        elif period == 'week':
            for w in range(1, 53):
                sales_sum = sales.filter(sale_date__year=year, sale_date__week=w).aggregate(total=Sum('sale_price'))['total'] or 0
                lending_sum = lendings.filter(borrow_date__year=year, borrow_date__week=w).aggregate(total=Sum('product__rental_price'))['total'] or 0
                result.append({
                    "label": f"{w}-hafta",
                    "total_revenue": sales_sum + lending_sum,
                    "sales_revenue": sales_sum,
                    "lending_revenue": lending_sum
                })
        elif period == 'day':
            today = timezone.now().date()
            for i in range(29, -1, -1):
                d = today - timedelta(days=i)
                sales_sum = sales.filter(sale_date__date=d).aggregate(total=Sum('sale_price'))['total'] or 0
                lending_sum = lendings.filter(borrow_date__date=d).aggregate(total=Sum('product__rental_price'))['total'] or 0
                result.append({
                    "label": d.strftime('%d-%b'),
                    "total_revenue": sales_sum + lending_sum,
                    "sales_revenue": sales_sum,
                    "lending_revenue": lending_sum
                })
        else:
            return Response({"error": "period noto'g'ri"}, status=400)

        return Response(result)


class CategorySalesShareView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        year = int(request.GET.get('year', timezone.now().year))
        month = request.GET.get('month', None)

        # Faqat yil va oy bo‘yicha filter
        products = Product.objects.all()
        if month:
            products = products.filter(created_at__year=year, created_at__month=int(month))
        else:
            products = products.filter(created_at__year=year)

        total_products = products.count() or 1  # 0 bo‘lsa, 1 qilib olamiz, bo‘linishda xatolik bo‘lmasin

        category_data = (
            products.values('category__name')
            .annotate(product_count=Count('id'))
            .order_by('-product_count')
        )

        result = []
        for item in category_data:
            percent = round(item['product_count'] * 100 / total_products, 2)
            result.append({
                "category": item['category__name'] or "Boshqalar",
                "product_count": item['product_count'],
                "percent": percent
            })

        return Response(result)



class TopSoldProductsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        year = int(request.GET.get('year', timezone.now().year))
        month = request.GET.get('month', None)

        sales = Sale.objects.all()
        if month:
            sales = sales.filter(sale_date__year=year, sale_date__month=int(month))
        else:
            sales = sales.filter(sale_date__year=year)

        # Har bir product uchun sotilgan soni va jami summa
        product_data = (
            sales.values('product', 'product__name', 'product__category__name')
            .annotate(
                sold_count=Count('id'),
                total_income=Sum('sale_price')
            )
            .order_by('-sold_count', '-total_income')[:10]
        )

        # Har bir product uchun arenda sonini ham hisoblash
        product_ids = [item['product'] for item in product_data]
        lending_counts = dict(
            Lending.objects.filter(product_id__in=product_ids)
            .values('product')
            .annotate(lend_count=Count('id'))
            .values_list('product', 'lend_count')
        )

        result = []
        for item in product_data:
            result.append({
                "product_id": item['product'],
                "name": item['product__name'],
                "category": item['product__category__name'],
                "sold_count": item['sold_count'],
                "lend_count": lending_counts.get(item['product'], 0),
                "total_income": item['total_income'],
                "profit": item['total_income'],  # Agar foyda alohida bo‘lsa, shu yerda hisoblang
            })
        return Response(result)


class TopLendedProductsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        year = int(request.GET.get('year', timezone.now().year))
        month = request.GET.get('month', None)

        lendings = Lending.objects.all()
        if month:
            lendings = lendings.filter(borrow_date__year=year, borrow_date__month=int(month))
        else:
            lendings = lendings.filter(borrow_date__year=year)

        # Har bir product uchun arenda soni va jami summa

        product_data = (
            lendings.values('product', 'product__name', 'product__category__name')
            .annotate(
                lend_count=Count('id'),
                total_income=Sum('product__rental_price'),
                # avg_days=Avg('days')  # Agar days maydoni bo‘lsa
            )
            .order_by('-lend_count', '-total_income')[:10]
        )

        # Har bir product uchun sotilgan sonini ham hisoblash
        product_ids = [item['product'] for item in product_data]
        sales_counts = dict(
            Sale.objects.filter(product_id__in=product_ids)
            .values('product')
            .annotate(sold_count=Count('id'))
            .values_list('product', 'sold_count')
        )

        result = []
        for item in product_data:
            result.append({
                "product_id": item['product'],
                "name": item['product__name'],
                "category": item['product__category__name'],
                "lend_count": item['lend_count'],
                "sold_count": sales_counts.get(item['product'], 0),
                "total_income": item['total_income'],
                # "avg_days": item['avg_days'] or 0,
                "profit": item['total_income'],  # Agar foyda alohida bo‘lsa, shu yerda hisoblang
            })
        return Response(result)



class EmployeeStatisticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Faqat direktor va admin uchun
        user = request.user
        if user.role not in [User.DIRECTOR, User.ADMIN]:
            return Response({"error": "Ruxsat yo'q"}, status=403)

        # Hodimlar ro'yxati
        if user.role == User.DIRECTOR:
            employees = User.objects.filter(created_by=user, role=User.SELLER)
        else:
            employees = User.objects.filter(created_by=user.created_by, role=User.SELLER)

        year = int(request.GET.get('year', timezone.now().year))
        month = int(request.GET.get('month', timezone.now().month))

        start_date = datetime(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_date = datetime(year, month, last_day, 23, 59, 59)

        result = []
        for emp in employees:
            # Sotish soni va daromadi
            sales = Sale.objects.filter(
                seller=emp,
                sale_date__range=(start_date, end_date)
            )
            sales_count = sales.count()
            sales_income = sales.aggregate(total=Sum('sale_price'))['total'] or 0

            # Arenda soni va daromadi
            lendings = Lending.objects.filter(
                seller=emp,
                borrow_date__range=(start_date, end_date)
            )
            lending_count = lendings.count()
            lending_income = lendings.aggregate(total=Sum('product__rental_price'))['total'] or 0

            # Komissiya (KPI)
            kpi = emp.KPI or 0
            sales_kpi = sales.aggregate(
                total=Sum(
                    ExpressionWrapper(
                        F('sale_price') * F('quantity') * kpi / 100,
                        output_field=DecimalField()
                    )
                )
            )['total'] or 0

            lending_kpi = lendings.aggregate(
                total=Sum(
                    ExpressionWrapper(
                        F('product__rental_price') * kpi / 100,
                        output_field=DecimalField()
                    )
                )
            )['total'] or 0

            result.append({
                "username": emp.username,
                "full_name": emp.get_full_name() if hasattr(emp, 'get_full_name') else emp.first_name + " " + emp.last_name,
                "sales_count": sales_count,
                "lending_count": lending_count,
                "commission": sales_kpi + lending_kpi,
                "income": sales_income + lending_income
            })

        return Response(result)


class CartItemDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, item_id):
        try:
            cart_item = CartItem.objects.get(id=item_id, cart__seller=request.user)
        except CartItem.DoesNotExist:
            return Response({"error": "Cart item not found."}, status=status.HTTP_404_NOT_FOUND)
        
        cart_item.delete()
        return Response({"success": "Cart item deleted successfully."}, status=status.HTTP_200_OK)
    


class CartBulkCheckoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        buyer = request.data.get('buyer', '')
        payment_type = request.data.get('payment_type', 'CASH')
        items = request.data.get('items', [])
        if not items or not isinstance(items, list):
            return Response({"error": "Mahsulotlar ro'yxati noto'g'ri"}, status=400)
        sales = []
        total_price = Decimal('0')
        for item in items:
            product_id = item.get('product_id')
            quantity = item.get('quantity')
            weight = item.get('weight')
            try:
                product = Product.objects.get(id=product_id)
            except Product.DoesNotExist:
                return Response({"error": f"Mahsulot topilmadi: {product_id}"}, status=404)

            # Narxni hisoblash
            if weight is not None:
                # float emas, Decimal ishlatamiz
                weight_decimal = Decimal(str(weight))
                sale_price = product.price * weight_decimal
                sale = Sale.objects.create(
                    product=product,
                    seller=request.user,
                    buyer=buyer,
                    sale_price=sale_price,
                    quantity=None,
                    product_weight=weight_decimal,
                    status='COMPLETED',
                    payment_type=payment_type
                )
                sales.append({
                    "product_id": product.id,
                    "product_name": product.name,
                    "weight": float(weight_decimal),
                    "sale_price": str(sale.sale_price),
                    "payment_type": sale.payment_type
                })
                total_price += sale_price
            else:
                quantity = int(quantity) if quantity is not None else 1
                sale_price = product.price * quantity
                sale = Sale.objects.create(
                    product=product,
                    seller=request.user,
                    buyer=buyer,
                    sale_price=sale_price,
                    quantity=quantity,
                    status='COMPLETED',
                    payment_type=payment_type
                )
                sales.append({
                    "product_id": product.id,
                    "product_name": product.name,
                    "quantity": quantity,
                    "sale_price": str(sale.sale_price),
                    "payment_type": sale.payment_type
                })
                total_price += sale_price

        return Response({
            "success": True,
            "message": "Barcha mahsulotlar sotildi",
            "sales": sales,
            "total_price": str(total_price)
        })