from django.contrib.auth import authenticate, login, logout, get_user_model
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny

from .serializers import RegisterSerializer, LoginSerializer

User = get_user_model()


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()
        return Response(
            {"message": "Registration submitted. Awaiting admin approval."},
            status=status.HTTP_201_CREATED,
        )


from django.db.models import Q


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        raw_identifier = str(serializer.validated_data["email"]).strip()
        password = serializer.validated_data["password"]

        # Check if user exists (case-insensitive email or username match)
        user_obj = User.objects.filter(
            Q(email__iexact=raw_identifier) | Q(username__iexact=raw_identifier)
        ).first()

        if not user_obj:
            return Response(
                {"error": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Staff, superusers, and administrators are never blocked by student PENDING status
        is_admin_account = bool(
            user_obj.is_staff or user_obj.is_superuser or user_obj.role == User.Role.ADMIN
        )

        if user_obj.status == User.AccountStatus.PENDING and not is_admin_account:
            return Response(
                {"error": "pending", "message": "Your registration is awaiting approval."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if user_obj.status == User.AccountStatus.REJECTED and not is_admin_account:
            return Response(
                {"error": "rejected", "message": "Your registration request has been declined."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Authenticate using canonical email then username fallback
        user = authenticate(request, username=user_obj.email, password=password)
        if user is None and user_obj.username and user_obj.username != user_obj.email:
            user = authenticate(request, username=user_obj.username, password=password)

        if user is None:
            return Response(
                {"error": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        login(request, user)

        # Ensure session is committed and has key
        if not request.session.session_key:
            request.session.save()

        session_key = request.session.session_key

        return Response(
            {
                "message": "Login successful.",
                "session_key": session_key,
                "user": {
                    "email": user.email,
                    "name": user.first_name or user.username or "Administrator",
                    "role": user.role,
                    "status": user.status,
                    "is_staff": user.is_staff,
                    "is_superuser": user.is_superuser,
                },
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response({"message": "Logged out."}, status=status.HTTP_200_OK)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response(
            {
                "email": user.email,
                "name": user.first_name or user.username or "User",
                "role": user.role,
                "status": user.status,
                "is_staff": user.is_staff,
                "is_superuser": user.is_superuser,
            }
        )
