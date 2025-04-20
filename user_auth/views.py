from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import AllowAny
from rest_framework import status
from .UserSerializer import UserSerializer
from rest_framework_simplejwt.tokens import RefreshToken

class Home(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        content = { "response": "endpoint disponivel"}
        return Response(content, status=status.HTTP_200_OK)
    
class CreateUserView(APIView):
    permission_classes = [AllowAny]  

    def post(self, request, *args, **kwargs):
        serializer = UserSerializer(data=request.data) 
        if serializer.is_valid(): 
            user = serializer.save() 
            return Response(serializer.data, status=status.HTTP_201_CREATED) 
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST) 