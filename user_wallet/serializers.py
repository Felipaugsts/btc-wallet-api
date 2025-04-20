from rest_framework import serializers
from .models import Wallet, Address, Transaction
from django.contrib.auth.models import User

class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ['id', 'address', 'path', 'is_change', 'index', 'created_at']

class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ['id', 'txid', 'amount', 'fee', 'status', 'created_at', 'updated_at']

class WalletSerializer(serializers.ModelSerializer):
    addresses = AddressSerializer(many=True, read_only=True)
    
    class Meta:
        model = Wallet
        fields = ['id', 'name', 'wallet_type', 'xpub', 'created_at', 'updated_at', 'addresses']
        extra_kwargs = {
            'xpub': {'write_only': True}  # Não expõe o xpub nas respostas
        }

class WalletCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ['name', 'wallet_type', 'xpub']
        
    def validate(self, data):
        # Verifica se o tipo de carteira é válido
        if data['wallet_type'] == 'watch-only' and not data.get('xpub'):
            raise serializers.ValidationError("xpub é obrigatório para carteiras watch-only")
        return data

class TransactionCreateSerializer(serializers.Serializer):
    to_address = serializers.CharField(max_length=100)
    amount = serializers.IntegerField(min_value=546)  # 546 satoshis é o dust limit
    fee_rate = serializers.IntegerField(required=False)

class BroadcastTransactionSerializer(serializers.Serializer):
    tx_hex = serializers.CharField()
