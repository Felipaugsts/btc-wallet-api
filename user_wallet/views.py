from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Wallet, Address, Transaction
from .serializers import (
    WalletSerializer, WalletCreateSerializer, AddressSerializer,
    TransactionSerializer, TransactionCreateSerializer, BroadcastTransactionSerializer
)
from .services.wallet_service import WalletService
import logging
import requests
import decimal

logger = logging.getLogger(__name__)

class WalletViewSet(viewsets.ModelViewSet):
    """
    API endpoint para gerenciar carteiras Bitcoin
    """
    serializer_class = WalletSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """
        Retorna apenas as carteiras do usuário autenticado
        """
        return Wallet.objects.filter(user=self.request.user)
    
    def get_serializer_class(self):
        """
        Retorna o serializador apropriado com base na ação
        """
        if self.action == 'create':
            return WalletCreateSerializer
        return WalletSerializer
    
    def perform_create(self, serializer):
        """
        Cria uma nova carteira
        """
        wallet_service = WalletService()
        
        wallet_type = serializer.validated_data['wallet_type']
        name = serializer.validated_data['name']
        
        if wallet_type == 'watch-only':
            xpub = serializer.validated_data.get('xpub')
            if not xpub:
                return Response(
                    {"error": "xpub é obrigatório para carteiras watch-only"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                wallet = wallet_service.create_watch_only_wallet(name, xpub, self.request.user)
                return Response(WalletSerializer(wallet).data, status=status.HTTP_201_CREATED)
            except Exception as e:
                logger.error(f"Erro ao criar carteira watch-only: {str(e)}")
                return Response(
                    {"error": f"Falha ao criar carteira watch-only: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        else:
            # Implementação para outros tipos de carteira
            return Response(
                {"error": "Tipo de carteira não suportado"},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def balance(self, request, pk=None):
        """
        Obtém o saldo de uma carteira
        """
        wallet = self.get_object()
        wallet_service = WalletService()

        response = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=brl"
        )
        btc_to_brl = response.json().get("bitcoin", {}).get("brl", 0)

        try:
            balance = wallet_service.get_wallet_balance(wallet.id)
            total_btc = balance.get("total", 0) / 100_000_000
            total_brl = round(total_btc * btc_to_brl, 2)

            balance["btcPriceBRL"] = btc_to_brl  
            balance["walletTotalBRL"] = total_brl
            balance["walletID"] = wallet.id
            return Response(balance)
        except Exception as e:
            logger.error(f"Erro ao obter saldo da carteira: {str(e)}")
            return Response(
                {"error": f"Falha ao obter saldo da carteira: {str(e)}, id: {wallet.id}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
    @action(detail=True, methods=['post'])
    def delete(self, request, pk=None): 
        wallet = self.get_object()
        wallet_service = WalletService()

        try:
            response = wallet_service.delete_wallet(wallet.id)
            return Response(response, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Erro ao deletar carteira: {str(e)}")
            return Response(
                {"error": f"Erro ao deletar carteira: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def create_transaction(self, request, pk=None):
        """
        Cria uma transação não assinada
        """
        wallet = self.get_object()
        serializer = TransactionCreateSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        wallet_service = WalletService()
        
        try:
            tx_hex = wallet_service.create_transaction(
                wallet.id,
                serializer.validated_data['to_address'],
                serializer.validated_data['amount'],
                serializer.validated_data.get('fee_rate')
            )
            
            return Response({"tx_hex": tx_hex})
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Erro ao criar transação: {str(e)}")
            return Response(
                {"error": f"Falha ao criar transação: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def generate_address(self, request, pk=None):
        """
        Gera um novo endereço de recebimento
        """
        wallet = self.get_object()
        wallet_service = WalletService()
        
        try:
            address = wallet_service.generate_receive_address(wallet.id)
            return Response({"address": address})
        except Exception as e:
            logger.error(f"Erro ao gerar endereço: {str(e)}")
            return Response(
                {"error": f"Falha ao gerar endereço: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class TransactionViewSet(viewsets.GenericViewSet):
    """
    API endpoint para gerenciar transações Bitcoin
    """
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def broadcast(self, request):
        """
        Transmite uma transação assinada
        """
        serializer = BroadcastTransactionSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        wallet_service = WalletService()
        
        try:
            txid = wallet_service.broadcast_transaction(serializer.validated_data['tx_hex'])
            return Response({"txid": txid})
        except Exception as e:
            logger.error(f"Erro ao transmitir transação: {str(e)}")
            return Response(
                {"error": f"Falha ao transmitir transação: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
