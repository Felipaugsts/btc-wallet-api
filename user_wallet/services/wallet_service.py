from bitcoinlib.wallets import Wallet as BitcoinlibWallet, wallet_exists
from bitcoinlib.keys import HDKey
from bitcoinlib.services.services import Service
from ..models import Wallet, Address, Transaction
import logging
from django.core.exceptions import ObjectDoesNotExist
import requests
from datetime import datetime
from ..models import BitcoinPriceCache
from django.utils import timezone
from django.db import transaction


logger = logging.getLogger(__name__)

class WalletService:
    """
    Serviço para gerenciar carteiras Bitcoin usando bitcoinlib
    """
    
    def __init__(self):
        self.service = Service(network='bitcoin', providers=['blockstream', 'blockcypher'])
    ## MARK: Watch only
    def create_watch_only_wallet(self, name, xpub, user):
        try:
            # Cria a carteira no banco de dados
            wallet = Wallet.objects.create(
                name=name,
                wallet_type='watch-only',
                xpub=xpub,
                user=user
            )
            
            # Cria a carteira na bitcoinlib
            bitcoinlib_wallet = BitcoinlibWallet.create(
                name=f"watch_only_{wallet.id}",
                keys=xpub,
                network='bitcoin',
                purpose=44,  # Use 44 para BIP44, 49 para P2SH-SegWit, ou 84 para SegWit nativo
                witness_type='segwit',  # ou 'p2sh-segwit' ou None para legacy
                scheme='account'
            )
            
            # Gera alguns endereços iniciais
            self._generate_addresses(wallet, bitcoinlib_wallet, 5)
            
            return wallet
        except Exception as e:
            logger.error(f"Erro ao criar carteira watch-only: {str(e)}")
            raise
    ## MARK: Address

    def _generate_addresses(self, wallet, bitcoinlib_wallet, count=1, is_change=False):
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
                
                # Derive o endereço usando o método get_key
                key = bitcoinlib_wallet.get_key(account_id=account, change=change, address_index=i)
                address_str = key.address
                
                # Constrói o caminho para salvar no banco de dados
                path = f"m/{bitcoinlib_wallet.purpose}'/{bitcoinlib_wallet.network.bip44_cointype}'/{account}'/{change}/{i}"
                
                # Salva o endereço no banco de dados
                address = Address.objects.create(
                    wallet=wallet,
                    address=address_str,
                    path=path,
                    is_change=is_change,
                    index=i
                )
                
                addresses.append(address)
                logger.info(f"Gerado endereço: {address_str} com caminho: {path}")
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

            logger.info(f"Número de carteiras encontradas para o usuário {user.id}: {wallets.count()}")

            for wallet in wallets:
                wallet_name = f"watch_only_{wallet.id}"
                logger.info(f"Inicializando carteira com o nome: {wallet_name}")
                logger.info(f"Dados da carteira: {wallet.__dict__}")

                try:
                    btc_wallet = BitcoinlibWallet(wallet_name)
                    logger.info(f"Carteira {wallet_name} inicializada com sucesso")
                except Exception as e:
                    logger.error(f"Erro ao inicializar a carteira {wallet_name}: {str(e)}")
                    continue

                try:
                    transactions = btc_wallet.transactions()
                    logger.info(f"Número de transações encontradas para {wallet_name}: {len(transactions)}")
                except Exception as e:
                    logger.error(f"Erro ao obter transações para {wallet_name}: {str(e)}")
                    continue

                for tx in transactions:
                    logger.info(f"Processando transação {tx.txid}")
                    logger.info(f"Transação {tx.txid}, Status: {tx.status}, Confirmations: {tx.confirmations}")

                    # Acessando a data da transação
                    tx_date = getattr(tx, "date", None)
                    if tx_date:
                        tx_date = tx_date.strftime('%Y-%m-%d %H:%M:%S')  # Formato legível

                    # Acessando os inputs e outputs para verificar o valor
                    total_value = 0
                    for output in tx.outputs:
                        total_value += output.value

                    # Verificando se a transação foi enviada ou recebida
                    user_address = wallet.address  # Usando o endereço da carteira do usuário
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

                    logger.info(f"Transação {tx.txid} processada com sucesso")

            logger.info(f"Total de transações processadas para o usuário {user.id}: {len(result)}")
            return result

        except Exception as e:
            logger.error(f"Erro geral ao obter transações do usuário {user.id}: {str(e)}")
            raise

    def get_all_wallets(self, wallets):
        """
        Obtém dados de todas as carteiras com tratamento robusto de erros
        Mantém a mesma interface pública com melhorias internas
        """
        result = []
        btc_to_brl = self._get_btc_price()  # Valor padrão caso a API falhe
        try:
            # 1. Otimiza a obtenção dos dados das carteiras
            wallets_data = wallets.values_list('id', 'name', named=True)
            logger.debug(f"Iniciando processamento de {len(wallets_data)} carteiras")

            # 3. Processa cada carteira individualmente
            for wallet_info in wallets_data:
                wallet_id, wallet_name = wallet_info.id, wallet_info.name
                wallet_entry = {
                    "id": wallet_id,
                    "name": wallet_name,
                    "error": None,
                    "balanceSatoshi": 0,
                    "btcValue": "0.00000000",
                    "fiatValue": "0.00",
                    "address": "N/A",
                    "transactions": 0,
                    "color": '#F7931A',
                    "change": 3.12
                }

                try:
                    watch_wallet_name = f"watch_only_{wallet_id}"
                    
                    # 4. Verifica existência da carteira de forma mais eficiente
                    if not wallet_exists(watch_wallet_name):
                        logger.warning(f"Carteira {watch_wallet_name} não encontrada")
                        wallet_entry["error"] = "Carteira não configurada"
                        result.append(wallet_entry)
                        continue

                    # 5. Processamento principal com tratamento granular
                    with BitcoinlibWallet(watch_wallet_name) as btc_wallet:
                        balance = btc_wallet.balance()
                        transactions = btc_wallet.transactions_full()
                        
                        # 6. Cálculos seguros
                        try:
                            btc_value = balance / 100_000_000
                            fiat_value = btc_value * btc_to_brl
                        except ZeroDivisionError:
                            btc_value = 0
                            fiat_value = 0

                        # 7. Atualiza os dados formatados
                        wallet_entry.update({
                            "balanceSatoshi": balance,
                            "btcValue": f"{btc_value:.8f}",
                            "fiatValue": f"{fiat_value:.2f}",
                            "address": btc_wallet.get_key().address,
                            "transactions": len(transactions)
                        })
                        
                        result.append(wallet_entry)
                        logger.debug(f"Carteira {wallet_id} processada com sucesso")

                except Exception as inner_e:
                    logger.error(f"Erro na carteira {wallet_id}: {str(inner_e)}", exc_info=True)
                    wallet_entry["error"] = "Erro ao processar carteira"
                    result.append(wallet_entry)
                    continue

        except Exception as global_error:
            logger.critical(f"Erro crítico no processamento: {str(global_error)}", exc_info=True)
            raise WalletServiceError("Falha ao recuperar dados das carteiras")

        logger.info(f"Processamento concluído. {len(result)} carteiras retornadas")
        return result

    def _get_btc_price(self):
        """Obtém o preço do BTC com cache de 1 hora ou se o preço atual for zero"""
        try:
            cache = BitcoinPriceCache.get_cached_price()

            # Calcula o tempo desde a última atualização (em segundos)
            time_since_update = (timezone.now() - cache.last_updated).total_seconds()

            # Verifica se precisa atualizar: cache expirado (mais de 1 hora) ou preço zero
            if time_since_update > 3600 or cache.price == 0.0:
                try:
                    # Chama a API para obter o preço atual do BTC apenas quando necessário
                    print("calling coingecko API", time_since_update > 3600, time_since_update)

                    url = "https://api.coingecko.com/api/v3/coins/markets"
                    params = {
                        "vs_currency": "brl",
                        "ids": "bitcoin"
                    }

                    result = requests.get(url, params=params)
                    result.raise_for_status()

                    # O retorno da API é uma lista, então acessamos o primeiro item
                    bitcoin_data = result.json()

                    # Verifique se a lista está vazia, e se não, pegue o primeiro item
                    if bitcoin_data:
                        bitcoin_info = bitcoin_data[0]  # Acessa o primeiro item da lista
                        new_price = bitcoin_info.get("current_price", 0.0)
                        change24h = bitcoin_info.get("price_change_percentage_24h", 0.0)
                        low24h = bitcoin_info.get("low_24h", 0.0)
                        high24h = bitcoin_info.get("high_24h", 0.0)

                        print("change24h", change24h)

                        # Só atualiza se o novo preço for válido e diferente de zero
                        if new_price and new_price != 0.0:
                            with transaction.atomic():
                                cache.price = new_price
                                cache.change24h = change24h
                                cache.low24h = low24h
                                cache.high24h = high24h
                                cache.last_updated = timezone.now()
                                cache.save()
                                print("salvo 123", cache)
                                logger.info(f"Preço do BTC atualizado com sucesso: {new_price}")
                        else:
                            logger.warning("Preço retornado pela API é zero ou inválido, mantendo o cache atual")
                            return cache.price
                    else:
                        logger.warning("A resposta da API não contém dados válidos para o Bitcoin.")
                        return cache.price  # Retorna o preço do cache se a resposta estiver vazia

                except requests.RequestException as api_error:
                    logger.error(f"Erro ao chamar API para obter o preço do BTC: {str(api_error)}")
                    # Mantém o cache existente em caso de erro de API

            # Retorna o preço atual do cache, a menos que seja zero
            if cache.price == 0.0:
                logger.warning("Preço do BTC ainda está zero no cache.")
                return -100

            logger.info(f"USING CACHED BTC PRICE {cache.price}")
            return cache.price  # Retorna o preço do cache caso não precise atualizar

        except Exception as e:
            logger.error(f"Erro ao obter ou atualizar preço do BTC: {str(e)}")
            return 0  # Retorna 0 em caso de erro geral
