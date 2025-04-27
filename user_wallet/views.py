from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import BitcoinPriceCache, Wallet, Address, Transaction
from .serializers import (
    WalletSerializer, WalletCreateSerializer, AddressSerializer,
    TransactionSerializer, TransactionCreateSerializer, BroadcastTransactionSerializer
)
from .services.wallet_service import WalletService
import logging
import requests
import datetime

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

    @action(detail=False, methods=['get'], url_path='all-balances')
    def all_balances(self, request):
        wallet_service = WalletService()
        wallets = Wallet.objects.filter(user=request.user)
        result = wallet_service.get_all_wallets(wallets=wallets)
        return Response(result)
    
    @action(detail=False, methods=['get'], url_path='all-transactions')
    def all_transactions(self, request):
        wallet_service = WalletService()
        transactions = wallet_service.get_user_transactions(user=request.user)
        return Response(transactions)

    @action(detail=True, methods=['post']) 
    def balance(self, request, pk=None):
        wallet_service = WalletService()

        pub_key = request.data.get("pubKey")
        wallet_id = pk  
        wallet_name = request.data.get("wallet_name", f"watch_only_{wallet_id}")

        if not pub_key:
            return Response(
                {"error": "Campo 'pubKey' é obrigatório"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        btc_to_brl = wallet_service._get_btc_price()

        try:
            balance = wallet_service.get_wallet_balance({
                "pubKey": pub_key,
                "wallet_id": wallet_id,
                "wallet_name": wallet_name
            })

            total_btc = balance.get("total", 0) / 100_000_000
            fiat_value = round(total_btc * btc_to_brl, 2)

            balance["btcPriceBrl"] = btc_to_brl
            balance["fiatValue"] = fiat_value
            balance["id"] = wallet_id
            balance["btcValue"] = total_btc
            balance["color"] = '#F7931A'
            balance["name"] = wallet_name
            balance["change"] = 123
            
            return Response(balance)

        except Exception as e:
            logger.error(f"Erro ao obter saldo da carteira: {str(e)}")
            return Response(
                {"error": f"Falha ao obter saldo da carteira: {str(e)}"},
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
        
    @action(detail=False, methods=['get'], url_path='btc-price')
    def bitcoin_price(self, request):
        wallet_service = WalletService()
        wallet_service._get_btc_price()
        cache = BitcoinPriceCache.get_cached_price()
        result = {
                "currentPrice": cache.price,
                "change24h": cache.change24h,
                "low24h": cache.low24h,
                "high24h": cache.high24h
            }
        
        return Response(result, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'], url_path='price-history')
    def price_history(self, request):
        period = request.data.get('period', '1m')  # '24h', '7d', '1m', '6m', '1y'

        period_map = {
            '24h': (1, 'hourly'),
            '7d': (7, 'daily'),
            '1m': (30, 'daily'),
            '6m': (180, 'daily'),
            '1a': (365, 'daily')
        }

        if period not in period_map:
            return Response(
                {"error": "Período inválido. Use: 24h, 7d, 1m, 6m ou 1y"},
                status=status.HTTP_400_BAD_REQUEST
            )

        days, interval = period_map[period]

        try:
            url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
            params = {
                "vs_currency": "brl",
                "days": days,
                "interval": interval
            }

            response = requests.get(url, params=params)
            data = response.json()

            prices = data.get("prices", [])

            labels = []
            values = []

            for timestamp, price in prices:
                dt = datetime.datetime.fromtimestamp(timestamp / 1000)
                if period == '24h':
                    labels.append(dt.strftime('%H:%M'))  # Hora
                elif period in ['7d', '1m']:
                    labels.append(dt.strftime('%d/%m'))  # Dia/Mês
                else:
                    labels.append(dt.strftime('%b/%Y'))  # Mês/Ano

                values.append(round(price, 2))

            chart_data = {
                "labels": labels,
                "datasets": [
                    {
                        "label": "Preço BTC (R$)",
                        "data": values,
                        "borderColor": "#F7931A",
                        "backgroundColor": "rgba(247, 147, 26, 0.1)",
                        "tension": 0.4,
                        "fill": True
                    }
                ]
            }

            return Response(chart_data)

        except Exception as e:
            logger.error(f"Erro ao buscar histórico de preço: {str(e)}")
            return Response({"error": "Falha ao obter dados de preço do Bitcoin"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

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