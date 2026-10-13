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


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data["email"].lower()
        password = serializer.validated_data["password"]

        # Check if user exists first (to give specific status messages)
        try:
            user_obj = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"error": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Check status before attempting authentication
        if user_obj.status == User.AccountStatus.PENDING:
            return Response(
                {"error": "pending", "message": "Your registration is awaiting approval."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if user_obj.status == User.AccountStatus.REJECTED:
            return Response(
                {"error": "rejected", "message": "Your registration request has been declined."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Authenticate only if ACTIVE
        user = authenticate(request, username=email, password=password)
        if user is None:
            return Response(
                {"error": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        login(request, user)
        return Response(
            {
                "message": "Login successful.",
                "user": {
                    "email": user.email,
                    "name": user.first_name,
                    "role": user.role,
                    "status": user.status,
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
                "name": user.first_name,
                "role": user.role,
                "status": user.status,
            }
        )
