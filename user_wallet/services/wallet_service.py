from bitcoinlib.wallets import Wallet as BitcoinlibWallet, wallet_exists
from bitcoinlib.keys import HDKey
from bitcoinlib.services.services import Service
from ..models import Wallet, Address, Transaction
import logging
from django.core.exceptions import ObjectDoesNotExist
import requests
from datetime import datetime

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
            wallet_name_full = f"watch_only_{wallet_id}"

            if not wallet_exists(wallet_name_full):
                BitcoinlibWallet.create(
                    name=wallet_name_full,
                    keys=pub_key,
                    network='bitcoin',
                    witness_type='segwit'
                )

            wallet = BitcoinlibWallet(wallet_name_full)
            balance = wallet.balance()
            transactions = wallet.transactions_full()
            pub_key = wallet.wif()
        

            return {
                "total": balance,
                "transactions": len(transactions),
                "address": pub_key
            }

        except Exception as e:
            logger.error(f"Erro ao obter saldo: {str(e)}")
            raise



    def get_user_transactions(self, user):
        try:
            result = []
            wallets = Wallet.objects.filter(user=user)

            print("user wallets", wallets)
            for wallet in wallets:
                wallet_name = f"watch_only_{wallet.id}"
                print(f"Inicializando carteira com o nome: {wallet_name}")

                btc_wallet = BitcoinlibWallet(wallet_name)

                transactions = btc_wallet.transactions()

                for tx in transactions:
                    print(f"Transação {tx.txid}, Status: {tx.status}, Confirmations: {tx.confirmations}")

                    # Acessando a data da transação
                    tx_date = getattr(tx, "date", None)
                    if tx_date:
                        tx_date = tx_date.strftime('%Y-%m-%d %H:%M:%S')  # Formato legível

                    # Acessando os inputs e outputs para verificar o valor
                    total_value = 0
                    for output in tx.outputs:
                        total_value += output.value

                    # Verificando se a transação foi enviada ou recebida
                    user_address = "seu_endereco_aqui"  # Endereço do usuário
                    is_sent = False
                    is_received = False

                    for input_tx in tx.inputs:
                        if input_tx.address == user_address:
                            is_sent = True

                    for output_tx in tx.outputs:
                        if output_tx.address == user_address:
                            is_received = True

                    transaction_type = "sent" if is_sent else "received" if is_received else "unknown"

                    # Adicionando as informações ao resultado
                    result.append({
                        "network": str(tx.network) if tx.network else "",
                        "confirmations": tx.confirmations,
                        "status": tx.status,
                        "date": tx_date,
                        "value": total_value,
                        "transaction_type": transaction_type,
                    })

            return result

        except Exception as e:
            logger.error(f"Erro ao obter transações do usuário: {str(e)}")
            raise


    def get_all_wallets(self, wallets):
        try:
            from bitcoinlib.wallets import Wallet as BitcoinlibWallet
            import requests

            result = []

            # Obtém os dados básicos das carteiras do usuário
            wallets_data = list(wallets.values_list('id', 'name'))
            print("user wallets:", wallets_data)

            # Consulta o valor atual do BTC em BRL
            response = requests.get(
                "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=brl"
            )
            btc_to_brl = response.json().get("bitcoin", {}).get("brl", 0)

            if response.status_code == 200:
                print("fetched BTC sussesfully")
            

            for wallet_id, wallet_name in wallets_data:
                watch_wallet_name = f"watch_only_{wallet_id}"

                # Verifica se a carteira existe
                if not wallet_exists(watch_wallet_name):
                    logger.info(f"Carteira {watch_wallet_name} não encontrada. Pulando...")
                    continue

                try:
                    print("watch_wallet_name 123", watch_wallet_name)
                    btc_wallet = BitcoinlibWallet(watch_wallet_name)

                    # Obtém saldo e transações
                    balance_satoshi = btc_wallet.balance()
                    transactions = btc_wallet.transactions_full()

                    # Conversões
                    btc_value = balance_satoshi / 100_000_000
                    fiat_value = round(btc_value * btc_to_brl, 2)

                    result.append({
                        "id": wallet_id,
                        "name": wallet_name,
                        "balanceSatoshi": balance_satoshi,
                        "btcValue": f"{btc_value:.8f}",
                        "fiatValue": f"{fiat_value:.2f}",
                        "address": btc_wallet.get_key().address,
                        "transactions": len(transactions),
                        "color": '#F7931A',
                        "change": 3.12  # Valor mockado; pode ser dinâmico se desejar
                    })

                except Exception as inner_e:
                    logger.warning(f"Erro ao processar carteira {wallet_id}: {inner_e}")
                    continue

            print("wallets results:", result)
            return result

        except Exception as e:
            logger.error(f"Erro ao obter carteiras do usuário: {str(e)}")
            raise
