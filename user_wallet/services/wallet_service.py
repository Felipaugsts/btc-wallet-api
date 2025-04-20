from bitcoinlib.wallets import Wallet as BitcoinlibWallet
from bitcoinlib.keys import HDKey
from bitcoinlib.services.services import Service
from ..models import Wallet, Address, Transaction
import logging
from django.core.exceptions import ObjectDoesNotExist

logger = logging.getLogger(__name__)

class WalletService:
    """
    Serviço para gerenciar carteiras Bitcoin usando bitcoinlib
    """
    
    def __init__(self):
        self.service = Service()
    ## MARK: Watch only
    def create_watch_only_wallet(self, name, xpub, user):
        """
        Cria uma carteira watch-only a partir de um xpub
        
        Args:
            name (str): Nome da carteira
            xpub (str): Chave pública estendida (xpub, ypub ou zpub)
            user (User): Usuário proprietário da carteira
            
        Returns:
            Wallet: Objeto da carteira criada
        """
        try:
            # Cria a carteira no banco de dados
            wallet = Wallet.objects.create(
                name=name,
                wallet_type='watch-only',
                xpub=xpub,
                user=user
            )
            
            # Cria a carteira na bitcoinlib
            # Usamos o modo 'single' para criar uma carteira somente com a chave pública
            bitcoinlib_wallet = BitcoinlibWallet.create(
                name=f"watch_only_{wallet.id}",
                keys=xpub,
                network='bitcoin',
                witness_type='segwit'  # Usar SegWit por padrão
            )
            
            # Gera alguns endereços iniciais
            self._generate_addresses(wallet, bitcoinlib_wallet, 5)
            
            return wallet
        except Exception as e:
            logger.error(f"Erro ao criar carteira watch-only: {str(e)}")
            raise
    
    ## MARK: Address

    def _generate_addresses(self, wallet, bitcoinlib_wallet, count=1, is_change=False):
        """
        Gera endereços para uma carteira
        
        Args:
            wallet (Wallet): Objeto da carteira no banco de dados
            bitcoinlib_wallet (BitcoinlibWallet): Objeto da carteira na bitcoinlib
            count (int): Número de endereços a gerar
            is_change (bool): Se são endereços de troco (True) ou recebimento (False)
            
        Returns:
            list: Lista de endereços gerados
        """
        addresses = []
        
        try:
            # Determina o índice inicial
            last_address = Address.objects.filter(
                wallet=wallet,
                is_change=is_change
            ).order_by('-index').first()
            
            start_index = 0 if last_address is None else last_address.index + 1
            
            # Gera os endereços
            for i in range(start_index, start_index + count):
                # Determina o caminho de derivação
                account = 0  # Usamos a conta 0 por padrão
                change = 1 if is_change else 0
                path = f"m/44'/0'/{account}'/{change}/{i}"
                
                # Deriva o endereço
                key = bitcoinlib_wallet.key_for_path(path)
                address_str = key.address()
                
                # Salva o endereço no banco de dados
                address = Address.objects.create(
                    wallet=wallet,
                    address=address_str,
                    path=path,
                    is_change=is_change,
                    index=i
                )
                
                addresses.append(address)
        except Exception as e:
            logger.error(f"Erro ao gerar endereços: {str(e)}")
            raise
        
        return addresses

    ## MARK: Delete wallet

    def delete_wallet(self, wallet_id):
        try:
            wallet = Wallet.objects.get(id=wallet_id)
            wallet.delete()
            return {'message': 'Wallet deleted successfully'}
        except ObjectDoesNotExist:
            return {'error': 'Wallet not found'}
        except Exception as e:
            logger.error(f"Erro ao deletar wallet {wallet_id}: {str(e)}")
            return {'error': 'Erro interno ao deletar a wallet'}
        
    ## MARK: Balance

    def get_wallet_balance(self, wallet_id):
        """
        Obtém o saldo de uma carteira
        
        Args:
            wallet_id (int): ID da carteira
            
        Returns:
            dict: Saldo da carteira em satoshis
        """
        try:
            wallet = Wallet.objects.get(id=1)
            bitcoinlib_wallet = BitcoinlibWallet(f"watch_only_1")
            balance = bitcoinlib_wallet.balance()
            return { 'satoshi': balance }
        
        except Exception as e:
            logger.error(f"Erro ao obter saldo da carteira: {str(e)}")
            raise
    
    ## MARK: Transaction
     
    def create_transaction(self, wallet_id, to_address, amount, fee_rate=None):
        """
        Cria uma transação não assinada (PSBT) para uso com hardware wallet
        
        Args:
            wallet_id (int): ID da carteira
            to_address (str): Endereço de destino
            amount (int): Valor a enviar em satoshis
            fee_rate (int, optional): Taxa em satoshis por byte
            
        Returns:
            str: PSBT em formato base64
        """
        try:
            wallet = Wallet.objects.get(id=wallet_id)
            
            # Verifica se é uma carteira watch-only
            if wallet.wallet_type != 'watch-only':
                raise ValueError("Apenas carteiras watch-only são suportadas para esta operação")
            
            # Abre a carteira na bitcoinlib
            bitcoinlib_wallet = BitcoinlibWallet(f"watch_only_{wallet.id}")
            
            # Atualiza os UTXOs da carteira
            bitcoinlib_wallet.utxos_update()
            
            # Verifica se há saldo suficiente
            if bitcoinlib_wallet.balance() < amount:
                raise ValueError("Saldo insuficiente")
            
            # Cria a transação
            # Nota: bitcoinlib não suporta diretamente a criação de PSBT para carteiras watch-only
            # Esta é uma implementação simplificada
            tx = bitcoinlib_wallet.transaction_create(
                [to_address],
                [amount],
                fee=fee_rate,
                offline=True  # Não transmite a transação
            )
            
            # Retorna a transação em formato serializado
            return tx.serialize()
        except Exception as e:
            logger.error(f"Erro ao criar transação: {str(e)}")
            raise
    
    def broadcast_transaction(self, tx_hex):
        """
        Transmite uma transação assinada para a rede Bitcoin
        
        Args:
            tx_hex (str): Transação assinada em formato hexadecimal
            
        Returns:
            str: TXID da transação
        """
        try:
            # Usa o serviço para transmitir a transação
            txid = self.service.sendrawtransaction(tx_hex)
            
            return txid
        except Exception as e:
            logger.error(f"Erro ao transmitir transação: {str(e)}")
            raise
    
    def generate_receive_address(self, wallet_id):
        """
        Gera um novo endereço de recebimento para uma carteira
        
        Args:
            wallet_id (int): ID da carteira
            
        Returns:
            str: Endereço de recebimento
        """
        try:
            wallet = Wallet.objects.get(id=wallet_id)
            
            # Abre a carteira na bitcoinlib
            bitcoinlib_wallet = BitcoinlibWallet(f"watch_only_{wallet.id}")
            
            # Gera um novo endereço
            addresses = self._generate_addresses(wallet, bitcoinlib_wallet, 1, False)
            
            return addresses[0].address
        except Exception as e:
            logger.error(f"Erro ao gerar endereço de recebimento: {str(e)}")
            raise
