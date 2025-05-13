# laticinios_armazem/models.py

import sqlite3
from datetime import datetime, date
from typing import Optional, List, Dict, Any

# Define o caminho para o arquivo do banco de dados SQLite.
DATABASE_PATH = 'data/laticinios.db'

def get_db_connection() -> sqlite3.Connection:
    """Estabelece e retorna uma conexão com o banco de dados SQLite.

    A conexão é configurada para retornar linhas como objetos sqlite3.Row,
    o que permite o acesso às colunas por nome.

    Returns:
        sqlite3.Connection: Objeto de conexão com o banco de dados.
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Permite acessar colunas por nome
    return conn

def init_db() -> None:
    """Inicializa o banco de dados criando as tabelas a partir do schema.sql.

    Lê o arquivo schema.sql e executa os comandos SQL para criar a estrutura
    do banco de dados, caso ela ainda não exista.
    """
    # Garante que o schema.sql seja lido do diretório correto onde o models.py está
    import os
    dir_path = os.path.dirname(os.path.realpath(__file__))
    schema_file_path = os.path.join(dir_path, 'schema.sql')
    try:
        with open(schema_file_path, 'r') as f:
            schema = f.read()
        conn = get_db_connection()
        conn.executescript(schema)
        conn.commit()
        conn.close()
    except FileNotFoundError:
        print(f"Erro: O arquivo schema.sql não foi encontrado em {schema_file_path}. O banco de dados pode não ser inicializado corretamente.")
    except Exception as e:
        print(f"Erro ao inicializar o banco de dados: {e}")

class Usuario:
    """Representa um usuário do sistema."""
    def __init__(self, username: str, funcao: str, nome: str):
        self.username = username
        self.funcao = funcao
        self.nome = nome

    @staticmethod
    def verificar_senha(username: str, senha: str) -> Optional['Usuario']:
        """Verifica se o nome de usuário e a senha correspondem a um usuário no banco de dados."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM usuarios WHERE username = ? AND senha = ?', (username, senha))
        user_data = cursor.fetchone()
        conn.close()
        if user_data:
            return Usuario(user_data['username'], user_data['funcao'], user_data['nome'])
        return None

    def tem_permissao(self, permissao: str) -> bool:
        """Verifica se o usuário tem uma determinada permissão com base em sua função."""
        permissoes_por_funcao = {
            'gerente': ['visualizar_armazem', 'detalhes_area', 'gerente', 'registrar_venda',
                        'gerenciar_areas', 'gerenciar_catalogo_produtos', 'gerenciar_produtos_em_areas'],
            'operador': ['visualizar_armazem', 'detalhes_area', 'registrar_venda']
        }
        # Gerente tem todas as permissões listadas para gerente.
        if self.funcao == 'gerente':
            return permissao in permissoes_por_funcao.get(self.funcao, [])
        # Operador tem apenas as permissões listadas para operador.
        return permissao in permissoes_por_funcao.get(self.funcao, [])

class ProdutoCatalogo:
    """Representa um item no catálogo de produtos."""
    def __init__(self, id_produto: str, nome: str):
        self.id_produto = id_produto
        self.nome = nome

    @staticmethod
    def criar(id_produto: str, nome: str) -> Optional['ProdutoCatalogo']:
        """Cria um novo produto no catálogo."""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                'INSERT INTO produtos_catalogo (id_produto, nome) VALUES (?, ?)',
                (id_produto, nome)
            )
            conn.commit()
            return ProdutoCatalogo(id_produto, nome)
        except sqlite3.IntegrityError: # ID do produto já existe
            return None
        finally:
            conn.close()

    def atualizar(self, novo_nome: str) -> bool:
        """Atualiza o nome deste produto no catálogo e em todas as instâncias em produtos_areas."""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # Atualiza na tabela produtos_catalogo
            cursor.execute(
                'UPDATE produtos_catalogo SET nome = ? WHERE id_produto = ?',
                (novo_nome, self.id_produto)
            )
            # Atualiza o nome nas instâncias da tabela produtos_areas
            cursor.execute(
                'UPDATE produtos_areas SET nome = ? WHERE id_catalogo_produto = ?',
                (novo_nome, self.id_produto)
            )            
            conn.commit()
            self.nome = novo_nome # Atualiza o objeto em memória
            return True
        except Exception:
            # Em um cenário real, seria bom logar o erro específico.
            return False
        finally:
            conn.close()

    def deletar(self) -> tuple[bool, str]:
        """Deleta este produto do catálogo.
        Retorna uma tupla (sucesso, mensagem).
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # Verifica se o produto está em uso na tabela produtos_areas
            cursor.execute('SELECT COUNT(*) FROM produtos_areas WHERE id_catalogo_produto = ?', (self.id_produto,))
            if cursor.fetchone()['COUNT(*)'] > 0:
                return False, f"Não é possível excluir o produto '{self.nome}' ({self.id_produto}) pois ele está registrado em uma ou mais áreas."
            
            # Verifica se o produto está em uso na tabela vendas
            cursor.execute('SELECT COUNT(*) FROM vendas WHERE id_catalogo_produto = ?', (self.id_produto,))
            if cursor.fetchone()['COUNT(*)'] > 0:
                 return False, f"Não é possível excluir o produto '{self.nome}' ({self.id_produto}) pois ele possui registros de vendas associados."

            cursor.execute('DELETE FROM produtos_catalogo WHERE id_produto = ?', (self.id_produto,))
            conn.commit()
            return True, f"Produto '{self.nome}' ({self.id_produto}) excluído do catálogo com sucesso."
        except Exception as e:
            return False, f"Erro ao excluir produto do catálogo: {e}"
        finally:
            conn.close()

    @staticmethod
    def buscar_por_id(id_produto: str) -> Optional['ProdutoCatalogo']:
        """Busca um produto no catálogo pelo seu ID."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM produtos_catalogo WHERE id_produto = ?', (id_produto,))
        produto_data = cursor.fetchone()
        conn.close()
        if produto_data:
            return ProdutoCatalogo(produto_data['id_produto'], produto_data['nome'])
        return None

    @staticmethod
    def listar_todos() -> List['ProdutoCatalogo']:
        """Lista todos os produtos cadastrados no catálogo."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM produtos_catalogo ORDER BY nome')
        produtos_data = cursor.fetchall()
        conn.close()
        return [ProdutoCatalogo(row['id_produto'], row['nome']) for row in produtos_data]
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte o objeto ProdutoCatalogo para um dicionário."""
        return {
            'id_produto': self.id_produto,
            'nome': self.nome
        }

class ProdutoLacteo:
    """Representa um produto lácteo específico em estoque (uma instância em produtos_areas)."""
    def __init__(self, id_catalogo_produto: str, nome: str, quantidade: int, data_validade_str: str, lote: str, id_instancia: Optional[int] = None):
        # 'id_instancia' é a chave primária da tabela produtos_areas, que no schema.sql é 'id'
        self.id = id_instancia 
        self.id_catalogo_produto = id_catalogo_produto
        self.nome = nome
        self.quantidade = quantidade
        try:
            self.data_validade = datetime.strptime(data_validade_str, '%Y-%m-%d').date()
        except ValueError:
            raise ValueError(f"Formato de data inválido para '{data_validade_str}'. Use AAAA-MM-DD.")
        self.lote = lote

    @staticmethod
    def buscar_instancia_por_id(id_instancia: int) -> Optional['ProdutoLacteo']:
        """Busca uma instância específica de produto em uma área pelo seu ID (chave primária de produtos_areas)."""
        conn = get_db_connection()
        cursor = conn.cursor()
        # A coluna primária em produtos_areas é 'id'
        cursor.execute(
            'SELECT id, id_catalogo_produto, nome, quantidade, data_validade, lote FROM produtos_areas WHERE id = ?',
            (id_instancia,)
        )
        data = cursor.fetchone()
        conn.close()
        if data:
            return ProdutoLacteo(
                id_catalogo_produto=data['id_catalogo_produto'],
                nome=data['nome'],
                quantidade=data['quantidade'],
                data_validade_str=data['data_validade'],
                lote=data['lote'],
                id_instancia=data['id'] # Passa o 'id' como id_instancia
            )
        return None

    def atualizar_instancia(self, nova_quantidade: int, nova_data_validade_str: str, novo_lote: str) -> bool:
        """Atualiza os detalhes desta instância de produto na tabela produtos_areas."""
        if self.id is None:
            return False # Não pode atualizar uma instância sem ID
        
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            nova_data_validade = datetime.strptime(nova_data_validade_str, '%Y-%m-%d').date()
            # A coluna primária em produtos_areas é 'id'
            cursor.execute(
                'UPDATE produtos_areas SET quantidade = ?, data_validade = ?, lote = ? WHERE id = ?',
                (nova_quantidade, nova_data_validade.strftime('%Y-%m-%d'), novo_lote, self.id)
            )
            conn.commit()
            # Atualiza o objeto em memória
            self.quantidade = nova_quantidade
            self.data_validade = nova_data_validade
            self.lote = novo_lote
            return True
        except ValueError: # Erro na conversão da data
            return False
        except Exception: # Considerar logar o erro específico
            return False
        finally:
            conn.close()

    def deletar_instancia(self) -> bool:
        """Deleta esta instância de produto da tabela produtos_areas."""
        if self.id is None:
            return False
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # A coluna primária em produtos_areas é 'id'
            cursor.execute('DELETE FROM produtos_areas WHERE id = ?', (self.id,))
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

    def to_dict(self) -> Dict[str, Any]:
        """Converte o objeto ProdutoLacteo para um dicionário."""
        return {
            'id': self.id, # Retorna 'id' como a chave da instância
            'id_catalogo_produto': self.id_catalogo_produto,
            'nome': self.nome,
            'quantidade': self.quantidade,
            'data_validade': self.data_validade.strftime('%Y-%m-%d'),
            'lote': self.lote
        }

class AreaArmazem:
    """Representa uma área de armazenamento no sistema."""
    def __init__(self, id_area: str, nome: str, tipo_armazenamento: str):
        self.id_area = id_area
        self.nome = nome
        self.tipo_armazenamento = tipo_armazenamento

    @staticmethod
    def criar(id_area: str, nome: str, tipo_armazenamento: str) -> Optional['AreaArmazem']:
        """Cria uma nova área de armazenamento no banco de dados."""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                'INSERT INTO areas_armazem (id_area, nome, tipo_armazenamento) VALUES (?, ?, ?)',
                (id_area, nome, tipo_armazenamento)
            )
            conn.commit()
            return AreaArmazem(id_area, nome, tipo_armazenamento)
        except sqlite3.IntegrityError: # ID da área já existe
            return None
        finally:
            conn.close()

    def atualizar(self, novo_nome: str, novo_tipo_armazenamento: str) -> bool:
        """Atualiza o nome e o tipo de armazenamento desta área no banco de dados."""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                'UPDATE areas_armazem SET nome = ?, tipo_armazenamento = ? WHERE id_area = ?',
                (novo_nome, novo_tipo_armazenamento, self.id_area)
            )
            conn.commit()
            self.nome = novo_nome
            self.tipo_armazenamento = novo_tipo_armazenamento
            return True
        except Exception:
            return False
        finally:
            conn.close()

    def deletar(self) -> tuple[bool, str]:
        """Deleta esta área de armazenamento do banco de dados.
        Retorna uma tupla (sucesso, mensagem).
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # Verifica se a área contém produtos
            cursor.execute('SELECT COUNT(*) FROM produtos_areas WHERE id_area = ?', (self.id_area,))
            if cursor.fetchone()['COUNT(*)'] > 0:
                return False, "Não é possível excluir a área pois ela contém produtos. Remova os produtos primeiro."
            
            cursor.execute('DELETE FROM areas_armazem WHERE id_area = ?', (self.id_area,))
            conn.commit()
            return True, f"Área '{self.nome}' ({self.id_area}) excluída com sucesso."
        except Exception as e:
            return False, f"Erro ao excluir área: {e}"
        finally:
            conn.close()

    @staticmethod
    def buscar_por_id(id_area: str) -> Optional['AreaArmazem']:
        """Busca uma área de armazenamento pelo seu ID no banco de dados."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM areas_armazem WHERE id_area = ?', (id_area,))
        area_data = cursor.fetchone()
        conn.close()
        if area_data:
            return AreaArmazem(area_data['id_area'], area_data['nome'], area_data['tipo_armazenamento'])
        return None

    @staticmethod
    def listar_todas() -> List['AreaArmazem']:
        """Lista todas as áreas de armazenamento cadastradas no banco de dados."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM areas_armazem ORDER BY nome')
        areas_data = cursor.fetchall()
        conn.close()
        return [AreaArmazem(row['id_area'], row['nome'], row['tipo_armazenamento']) for row in areas_data]

    def adicionar_produto(self, produto: ProdutoLacteo) -> None:
        """Adiciona um produto (ou atualiza sua quantidade) a esta área de armazenamento."""
        conn = get_db_connection()
        cursor = conn.cursor()
        # Verifica se já existe um produto com o mesmo id_catalogo_produto e lote na área
        cursor.execute(
            'SELECT id, quantidade FROM produtos_areas WHERE id_area = ? AND id_catalogo_produto = ? AND lote = ?',
            (self.id_area, produto.id_catalogo_produto, produto.lote)
        )
        existing_product = cursor.fetchone()

        if existing_product:
            # Se existe, atualiza a quantidade
            new_quantidade = existing_product['quantidade'] + produto.quantidade
            cursor.execute(
                'UPDATE produtos_areas SET quantidade = ? WHERE id = ?',
                (new_quantidade, existing_product['id'])
            )
        else:
            # Se não existe, insere um novo registro
            cursor.execute(
                'INSERT INTO produtos_areas (id_area, id_catalogo_produto, nome, quantidade, data_validade, lote) VALUES (?, ?, ?, ?, ?, ?)',
                (self.id_area, produto.id_catalogo_produto, produto.nome, produto.quantidade,
                 produto.data_validade.strftime('%Y-%m-%d'), produto.lote)
            )
        conn.commit()
        conn.close()

    def listar_produtos(self) -> List[ProdutoLacteo]:
        """Lista todos os produtos contidos nesta área de armazenamento."""
        conn = get_db_connection()
        cursor = conn.cursor()
        # A coluna primária em produtos_areas é 'id'
        cursor.execute(
            'SELECT id, id_catalogo_produto, nome, quantidade, data_validade, lote FROM produtos_areas WHERE id_area = ? ORDER BY data_validade ASC',
            (self.id_area,)
        )
        produtos_data = cursor.fetchall()
        conn.close()
        return [ProdutoLacteo(row['id_catalogo_produto'], row['nome'], row['quantidade'],
                                  row['data_validade'], row['lote'], row['id']) for row in produtos_data]

    def remover_produto(self, id_instancia_produto: int, quantidade_a_remover: int) -> bool:
        """Remove uma certa quantidade de um produto específico desta área.
        Se a quantidade a ser removida for igual ou maior que a existente, o produto é totalmente removido.
        O id_instancia_produto refere-se à coluna 'id' da tabela produtos_areas.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT quantidade FROM produtos_areas WHERE id = ?', (id_instancia_produto,))
        produto_atual = cursor.fetchone()

        if not produto_atual:
            conn.close()
            return False # Produto não encontrado

        quantidade_existente = produto_atual['quantidade']

        if quantidade_a_remover >= quantidade_existente:
            # Remove completamente o produto da área
            cursor.execute('DELETE FROM produtos_areas WHERE id = ?', (id_instancia_produto,))
        else:
            # Atualiza a quantidade do produto na área
            nova_quantidade = quantidade_existente - quantidade_a_remover
            cursor.execute('UPDATE produtos_areas SET quantidade = ? WHERE id = ?', (nova_quantidade, id_instancia_produto))
        
        conn.commit()
        conn.close()
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Converte o objeto AreaArmazem para um dicionário, incluindo seus produtos."""
        return {
            'id_area': self.id_area,
            'nome': self.nome,
            'tipo_armazenamento': self.tipo_armazenamento,
            'produtos': [p.to_dict() for p in self.listar_produtos()]
        }

class Venda:
    """Representa uma venda registrada no sistema."""
    def __init__(self, id_catalogo_produto: str, nome: str, lote: str, data_validade_produto: str, 
                 quantidade_vendida: int, destino: str, area_origem_id: str, usuario_responsavel: str, 
                 data_hora: Optional[datetime] = None, id_venda: Optional[int] = None):
        self.id_venda = id_venda # Chave primária da tabela vendas
        self.id_catalogo_produto = id_catalogo_produto
        self.nome = nome
        self.lote = lote
        self.data_validade_produto = data_validade_produto # String no formato AAAA-MM-DD
        self.quantidade_vendida = quantidade_vendida
        self.destino = destino
        self.area_origem_id = area_origem_id
        self.usuario_responsavel = usuario_responsavel
        self.data_hora = data_hora if data_hora else datetime.now()

    @staticmethod
    def registrar(venda: 'Venda') -> None:
        """Registra uma nova venda no banco de dados."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO vendas (id_catalogo_produto, nome, lote, data_validade_produto, 
                                quantidade_vendida, destino, area_origem_id, usuario_responsavel, data_hora) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (venda.id_catalogo_produto, venda.nome, venda.lote, venda.data_validade_produto,
             venda.quantidade_vendida, venda.destino, venda.area_origem_id, venda.usuario_responsavel, 
             venda.data_hora.strftime('%Y-%m-%d %H:%M:%S'))
        )
        conn.commit()
        conn.close()

    @staticmethod
    def listar_todas() -> List['Venda']:
        """Lista todas as vendas registradas no banco de dados."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM vendas ORDER BY data_hora DESC')
        vendas_data = cursor.fetchall()
        conn.close()
        return [
            Venda(
                id_catalogo_produto=row['id_catalogo_produto'],
                nome=row['nome'],
                lote=row['lote'],
                data_validade_produto=row['data_validade_produto'],
                quantidade_vendida=row['quantidade_vendida'],
                destino=row['destino'],
                area_origem_id=row['area_origem_id'],
                usuario_responsavel=row['usuario_responsavel'],
                data_hora=datetime.strptime(row['data_hora'], '%Y-%m-%d %H:%M:%S'),
                id_venda=row['id']
            ) for row in vendas_data
        ]

    def to_dict(self) -> Dict[str, Any]:
        """Converte o objeto Venda para um dicionário."""
        return {
            'id_venda': self.id_venda,
            'id_catalogo_produto': self.id_catalogo_produto,
            'nome': self.nome,
            'lote': self.lote,
            'data_validade_produto': self.data_validade_produto,
            'quantidade_vendida': self.quantidade_vendida,
            'destino': self.destino,
            'area_origem_id': self.area_origem_id,
            'usuario_responsavel': self.usuario_responsavel,
            'data_hora': self.data_hora.strftime('%d/%m/%Y %H:%M:%S')
        }

def popular_dados_iniciais() -> None:
    """Popula o banco de dados com dados iniciais se as tabelas estiverem vazias."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Verifica se a tabela usuarios está vazia
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    if cursor.fetchone()["COUNT(*)"] == 0:
        # Insere usuários padrão
        usuarios_iniciais = [
            ("admin", "admin123", "gerente", "Administrador do Sistema"),
            ("joao.silva", "operador123", "operador", "João Silva"),
            ("maria.santos", "operador456", "operador", "Maria Santos")
        ]
        cursor.executemany("INSERT INTO usuarios (username, senha, funcao, nome) VALUES (?, ?, ?, ?)", usuarios_iniciais)
        print("Usuários iniciais inseridos.")

    # Verifica se a tabela produtos_catalogo está vazia
    cursor.execute("SELECT COUNT(*) FROM produtos_catalogo")
    if cursor.fetchone()["COUNT(*)"] == 0:
        # Insere produtos no catálogo
        catalogo_inicial = [
            ("QUEIJO001", "Queijo Mussarela Peça 1kg"),
            ("QUEIJO002", "Queijo Prato Fatiado 200g"),
            ("IOGUR001", "Iogurte Natural Integral 170g"),
            ("IOGUR002", "Iogurte Grego Morango 100g"),
            ("LEITE001", "Leite UHT Integral 1L"),
            ("MANTE001", "Manteiga com Sal 200g")
        ]
        cursor.executemany("INSERT INTO produtos_catalogo (id_produto, nome) VALUES (?, ?)", catalogo_inicial)
        print("Produtos iniciais do catálogo inseridos.")

    # Verifica se a tabela areas_armazem está vazia
    cursor.execute("SELECT COUNT(*) FROM areas_armazem")
    if cursor.fetchone()["COUNT(*)"] == 0:
        # Insere áreas de armazém
        areas_iniciais = [
            ("REF01", "Câmara Fria Principal", "refrigerado"),
            ("CONG01", "Congelador Estoque", "congelado"),
            ("SECO01", "Depósito Seco A", "seco")
        ]
        cursor.executemany("INSERT INTO areas_armazem (id_area, nome, tipo_armazenamento) VALUES (?, ?, ?)", areas_iniciais)
        print("Áreas de armazém iniciais inseridas.")

    # Verifica se a tabela produtos_areas está vazia (exemplo de população)
    cursor.execute("SELECT COUNT(*) FROM produtos_areas")
    if cursor.fetchone()["COUNT(*)"] == 0:
        # Adiciona alguns produtos às áreas
        produtos_em_areas_inicial = [
            ("REF01", "QUEIJO001", "Queijo Mussarela Peça 1kg", 50, (date.today() + timedelta(days=30)).strftime('%Y-%m-%d'), "LOTE2025A"),
            ("REF01", "IOGUR001", "Iogurte Natural Integral 170g", 100, (date.today() + timedelta(days=15)).strftime('%Y-%m-%d'), "LOTE2025B"),
            ("CONG01", "MANTE001", "Manteiga com Sal 200g", 70, (date.today() + timedelta(days=90)).strftime('%Y-%m-%d'), "LOTE2025C"),
            ("SECO01", "LEITE001", "Leite UHT Integral 1L", 200, (date.today() + timedelta(days=60)).strftime('%Y-%m-%d'), "LOTE2025D")
        ]
        cursor.executemany("INSERT INTO produtos_areas (id_area, id_catalogo_produto, nome, quantidade, data_validade, lote) VALUES (?, ?, ?, ?, ?, ?)", produtos_em_areas_inicial)
        print("Produtos iniciais nas áreas inseridos.")

    conn.commit()
    conn.close()

# Para testar a inicialização e população (opcional, pode ser removido ou comentado)
if __name__ == '__main__':
    print("Inicializando e populando o banco de dados...")
    # Garante que o diretório data exista
    import os
    if not os.path.exists(DATABASE_PATH.split('/')[0]):
        os.makedirs(DATABASE_PATH.split('/')[0])
    init_db()
    popular_dados_iniciais()
    print("Banco de dados pronto.")

