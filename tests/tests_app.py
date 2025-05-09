# laticinios_armazem/tests/test_app.py

import unittest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app # Importa a instância da aplicação Flask
from models import db_areas_armazem, db_vendas_registradas, popular_dados_iniciais, get_area_por_id, ProdutoLacteo

class FlaskAppTests(unittest.TestCase):

    def setUp(self):
        """Configura o ambiente para cada teste."""
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False # Desabilita CSRF para testes de formulário
        app.config['SECRET_KEY'] = 'test_secret_key' # Necessário para session
        self.client = app.test_client() # Cliente de teste do Flask

        # Limpa e repopula dados para um estado conhecido, se necessário
        # ou crie dados de teste específicos aqui.
        # É importante que os testes sejam independentes.
        db_areas_armazem.clear()
        db_vendas_registradas.clear()

        # Adiciona áreas e produtos de teste básicos
        db_areas_armazem["TESTA"] = {"nome": "Área Teste A", "produtos": []}
        db_areas_armazem["TESTB"] = {"nome": "Área Teste B", "produtos": []}
        
        area_test_a = get_area_por_id("TESTA")
        if area_test_a:
            area_test_a.adicionar_produto(ProdutoLacteo("L001", "Leite Teste", 10, "2025-12-31", "LT01"))
            area_test_a.adicionar_produto(ProdutoLacteo("Q002", "Queijo Teste", 5, "2025-10-20", "QT01"))

        # Simular login de gerente para rotas protegidas
        with self.client.session_transaction() as sess:
            sess['username'] = 'gerente_teste'
            sess['user_funcao'] = 'gerente'
            sess['user_nome'] = 'Gerente de Testes'

    def tearDown(self):
        """Limpa após cada teste."""
        # Limpa a sessão se necessário, ou outras limpezas globais
        with self.client.session_transaction() as sess:
            sess.clear()
        
        db_areas_armazem.clear()
        db_vendas_registradas.clear()
        # Repopula com os dados padrão do sistema para não afetar outros módulos
        # se este arquivo fosse importado, por exemplo.
        # No entanto, para testes unitários, o estado deve ser controlado por teste.
        # popular_dados_iniciais() # Pode não ser ideal aqui, pois `models.py` já o faz na importação.


    def test_login_page_loads(self):
        """Testa se a página de login carrega."""
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Login do Sistema', response.data)

    def test_login_sucesso_e_redirecionamento(self):
        """Testa o login bem-sucedido e o redirecionamento."""
        # Para testar o login real, precisamos de usuários no db_usuarios
        from models import db_usuarios # Importa aqui para não afetar o escopo global sempre
        db_usuarios['testuser'] = {'senha': 'testpass', 'funcao': 'operador', 'nome': 'Test User'}
        
        response = self.client.post('/login', data={
            'username': 'testuser',
            'password': 'testpass'
        }, follow_redirects=True) # follow_redirects para pegar a página final
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Armaz\xc3\xa9m de Latic\xc3\xadnios', response.data) # Verifica se foi para o armazem
        self.assertIn(b'Login bem-sucedido!', response.data) # Verifica flash message
        
        # Limpa o usuário de teste
        del db_usuarios['testuser']

    def test_login_falha(self):
        response = self.client.post('/login', data={
            'username': 'usuarioerrado',
            'password': 'senhaerrada'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Usu\xc3\xa1rio ou senha inv\xc3\xa1lidos.', response.data) # Mensagem de erro

    def test_logout(self):
        # Primeiro, simula um login
        with self.client.session_transaction() as sess:
            sess['username'] = 'testuser'
            sess['user_funcao'] = 'operador'
        
        response = self.client.get('/logout', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Voc\xc3\xaa foi desconectado.', response.data)
        self.assertIn(b'Login do Sistema', response.data) # Deve voltar para a página de login
        
        with self.client.session_transaction() as sess: # Verifica se a sessão foi limpa
            self.assertNotIn('username', sess)


    def test_visualizar_armazem_requer_login(self):
        """Testa se /armazem redireciona para login se não estiver logado."""
        with self.client.session_transaction() as sess: # Garante que está deslogado
            sess.clear()
        response = self.client.get('/armazem', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Login do Sistema', response.data) # Verifica se redirecionou para login

    def test_visualizar_armazem_logado(self):
        """Testa se /armazem carrega com áreas quando logado."""
        # Login já simulado no setUp com 'gerente_teste'
        response = self.client.get('/armazem')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'\xc3\x81rea Teste A', response.data) # Verifica se a área de teste aparece
        self.assertIn(b'TESTA', response.data)

    def test_detalhes_area_logado(self):
        """Testa se os detalhes de uma área carregam corretamente."""
        response = self.client.get('/armazem/TESTA')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'\xc3\x81rea TESTA: \xc3\x81rea Teste A', response.data)
        self.assertIn(b'Leite Teste', response.data) # Produto adicionado no setUp
        self.assertIn(b'Lote: LT01', response.data)

    def test_detalhes_area_nao_existente(self):
        response = self.client.get('/armazem/NAOEXISTE', follow_redirects=True)
        self.assertEqual(response.status_code, 200) # Página do armazém geral
        self.assertIn(b'\xc3\x81rea NAOEXISTE n\xc3\xa3o encontrada.', response.data) # Flash message

    def test_adicionar_produto_area_como_gerente(self):
        # Login de gerente já está no setUp
        area_id = "TESTA"
        response = self.client.post(f'/armazem/{area_id}/adicionar_produto', data={
            'id_produto_catalogo': 'MAN004', # Manteiga do catálogo padrão
            'quantidade': '5',
            'data_validade': '2026-01-01',
            'lote': 'LOTEADDTEST'
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Produto \'Manteiga com Sal 200g\' adicionado/atualizado com sucesso', response.data)
        
        # Verifica se o produto foi realmente adicionado
        area_obj = get_area_por_id(area_id)
        produtos_na_area = area_obj.listar_produtos()
        produto_adicionado = next((p for p in produtos_na_area if p.lote == "LOTEADDTEST"), None)
        self.assertIsNotNone(produto_adicionado)
        self.assertEqual(produto_adicionado.quantidade, 5)

    def test_adicionar_produto_area_como_operador_falha(self):
        # Simula login de operador
        with self.client.session_transaction() as sess:
            sess['username'] = 'operador_teste'
            sess['user_funcao'] = 'operador'
            sess['user_nome'] = 'Operador de Testes'

        area_id = "TESTA"
        response = self.client.post(f'/armazem/{area_id}/adicionar_produto', data={
            'id_produto_catalogo': 'MAN004',
            'quantidade': '5',
            'data_validade': '2026-01-01',
            'lote': 'LOTEFAILTEST'
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200) # Volta para o index (armazem)
        self.assertIn(b'Voc\xc3\xaa n\xc3\xa3o tem permiss\xc3\xa3o para acessar esta funcionalidade.', response.data) # Flash de permissão
        
        # Verifica que o produto NÃO foi adicionado
        area_obj = get_area_por_id(area_id)
        produtos_na_area = area_obj.listar_produtos()
        produto_nao_adicionado = next((p for p in produtos_na_area if p.lote == "LOTEFAILTEST"), None)
        self.assertIsNone(produto_nao_adicionado)


    def test_vender_produto_sucesso(self):
        # Login de gerente (ou operador) já está no setUp
        area_id = "TESTA" # Tem "Leite Teste" (L001), Lote LT01, Qtd: 10
        
        response = self.client.post(f'/armazem/{area_id}/vender', data={
            'id_produto_catalogo_venda': 'L001',
            'lote_venda': 'LT01',
            'quantidade_venda': '3',
            'destino_venda': 'Cliente Teste Venda'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Venda de 3 unidade(s) de \'Leite Teste\' (Lote: LT01) registrada com sucesso!', response.data)

        # Verifica estoque restante
        area_obj = get_area_por_id(area_id)
        produto_vendido = next(p for p in area_obj.listar_produtos() if p.lote == "LT01")
        self.assertEqual(produto_vendido.quantidade, 7) # 10 - 3 = 7

        # Verifica registro da venda
        self.assertEqual(len(db_vendas_registradas), 1)
        venda_registrada = db_vendas_registradas[0]
        self.assertEqual(venda_registrada.id_produto_catalogo, 'L001')
        self.assertEqual(venda_registrada.quantidade_vendida, 3)
        self.assertEqual(venda_registrada.destino, 'Cliente Teste Venda')

    def test_vender_produto_quantidade_insuficiente(self):
        area_id = "TESTA" # Tem "Leite Teste" (L001), Lote LT01, Qtd: 10
        response = self.client.post(f'/armazem/{area_id}/vender', data={
            'id_produto_catalogo_venda': 'L001',
            'lote_venda': 'LT01',
            'quantidade_venda': '15', # Mais do que o disponível
            'destino_venda': 'Cliente Teste Qtd Insuficiente'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'N\xc3\xa3o foi poss\xc3\xadvel vender 15 unidade(s) de \'Leite Teste\' (Lote: LT01). Quantidade insuficiente', response.data)
        
        # Verifica que o estoque não mudou
        area_obj = get_area_por_id(area_id)
        produto = next(p for p in area_obj.listar_produtos() if p.lote == "LT01")
        self.assertEqual(produto.quantidade, 10)
        self.assertEqual(len(db_vendas_registradas), 0) # Nenhuma venda registrada


    def test_relatorios_acesso_gerente(self):
        # Login de gerente já está no setUp
        response = self.client.get('/relatorios')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Relat\xc3\xb3rios e Monitoramento', response.data)
        self.assertIn(b'Estoque Atual Agregado', response.data)
        self.assertIn(b'Leite Teste', response.data) # Produto do estoque
    
    def test_relatorios_acesso_negado_operador(self):
        # Simula login de operador
        with self.client.session_transaction() as sess:
            sess['username'] = 'operador_teste'
            sess['user_funcao'] = 'operador'
        
        response = self.client.get('/relatorios', follow_redirects=True)
        self.assertEqual(response.status_code, 200) # Redireciona para o armazem
        self.assertIn(b'Voc\xc3\xaa n\xc3\xa3o tem permiss\xc3\xa3o para acessar esta funcionalidade.', response.data)
        self.assertNotIn(b'Estoque Atual Agregado', response.data) # Conteúdo do relatório não deve estar lá


    def test_api_produtos_area(self):
        response = self.client.get('/api/armazem/TESTA/produtos')
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertEqual(json_data['id_area'], 'TESTA')
        self.assertEqual(len(json_data['produtos']), 2) # Leite e Queijo adicionados no setUp
        self.assertEqual(json_data['produtos'][0]['nome'], 'Leite Teste')

    def test_api_estoque_completo_gerente(self):
        response = self.client.get('/api/estoque_completo')
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertIn('TESTA', json_data)
        self.assertEqual(json_data['TESTA']['produtos'][0]['id_produto_catalogo'], 'L001')

    def test_api_estoque_completo_operador_negado(self):
        with self.client.session_transaction() as sess:
            sess['username'] = 'operador_api'
            sess['user_funcao'] = 'operador'
        
        response = self.client.get('/api/estoque_completo')
        self.assertEqual(response.status_code, 302) # Redireciona para o login ou index com flash

        # Para testar o flash, precisamos seguir o redirecionamento
        response_redirected = self.client.get('/api/estoque_completo', follow_redirects=True)
        self.assertIn(b'Voc\xc3\xaa n\xc3\xa3o tem permiss\xc3\xa3o para acessar esta funcionalidade.', response_redirected.data)


if __name__ == '__main__':
    # popular_dados_iniciais() # Garante que o catálogo de produtos esteja populado se não foi antes
    unittest.main()