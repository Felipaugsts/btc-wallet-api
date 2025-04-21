from bitcoinlib.wallets import Wallet as BitcoinlibWallet, wallet_exists
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
        self.service = Service(network='bitcoin', providers=['blockstream', 'blockcypher'])
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

    def get_wallet_balance(self, data):
        try:
            pub_key = data["pubKey"]
            wallet_id = data["wallet_id"]
            wallet_name = data["wallet_name"]
            wallet_name_full = f"watch_only_{wallet_id}"

            if not wallet_exists(wallet_name_full):
                BitcoinlibWallet.create(
                    name=wallet_name_full,
                    keys=pub_key,
                    network='bitcoin',
                    witness_type='segwit'
                )

            wallet = BitcoinlibWallet(wallet_name_full)
            wallet.utxos_update()
            balance = wallet.balance()

            return {
                "confirmed": balance,
                "total": balance
            }

        except Exception as e:
            logger.error(f"Erro ao obter saldo: {str(e)}")
            raise
