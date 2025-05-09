# laticinios_armazem/tests/test_app.py

import unittest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from models import db_areas_armazem, db_vendas_registradas, popular_dados_iniciais, AreaArmazem, ProdutoLacteo

class FlaskAppTests(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SECRET_KEY'] = 'test_secret_key'
        self.client = app.test_client()

        db_areas_armazem.clear()
        db_vendas_registradas.clear()

        db_areas_armazem["TESTA"] = {"nome": "Área Teste A", "produtos": []}
        db_areas_armazem["TESTB"] = {"nome": "Área Teste B", "produtos": []}
        
        area_test_a = AreaArmazem.buscar_por_id("TESTA")
        if area_test_a:
            area_test_a.adicionar_produto(ProdutoLacteo("L001", "Leite Teste", 10, "2025-12-31", "LT01"))
            area_test_a.adicionar_produto(ProdutoLacteo("Q002", "Queijo Teste", 5, "2025-10-20", "QT01"))

        with self.client.session_transaction() as sess:
            sess['username'] = 'gerente_teste'
            sess['user_funcao'] = 'gerente'
            sess['user_nome'] = 'Gerente de Testes'

    def tearDown(self):
        with self.client.session_transaction() as sess:
            sess.clear()
        db_areas_armazem.clear()
        db_vendas_registradas.clear()
        popular_dados_iniciais()

    def test_login_page_loads(self):
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Login do Sistema', response.data)

    def test_login_sucesso_e_redirecionamento(self):
        from models import db_usuarios
        db_usuarios['testuser'] = {'senha': 'testpass', 'funcao': 'operador', 'nome': 'Test User'}
        
        response = self.client.post('/login', data={
            'username': 'testuser',
            'password': 'testpass'
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Armaz\xc3\xa9m de Latic\xc3\xadnios', response.data)
        self.assertIn(b'Login bem-sucedido!', response.data)
        
        del db_usuarios['testuser']

    def test_login_falha(self):
        response = self.client.post('/login', data={
            'username': 'usuarioerrado',
            'password': 'senhaerrada'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Usu\xc3\xa1rio ou senha inv\xc3\xa1lidos.', response.data)

    def test_logout(self):
        with self.client.session_transaction() as sess:
            sess['username'] = 'testuser'
            sess['user_funcao'] = 'operador'
        
        response = self.client.get('/logout', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Voc\xc3\xaa foi desconectado.', response.data)
        self.assertIn(b'Login do Sistema', response.data)
        
        with self.client.session_transaction() as sess:
            self.assertNotIn('username', sess)

    def test_visualizar_armazem_requer_login(self):
        with self.client.session_transaction() as sess:
            sess.clear()
        response = self.client.get('/armazem', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Login do Sistema', response.data)

    def test_visualizar_armazem_logado(self):
        response = self.client.get('/armazem')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'\xc3\x81rea Teste A', response.data)
        self.assertIn(b'TESTA', response.data)

    def test_detalhes_area_logado(self):
        response = self.client.get('/armazem/TESTA')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'\xc3\x81rea TESTA: \xc3\x81rea Teste A', response.data)
        self.assertIn(b'Leite Teste', response.data)
        self.assertIn(b'Lote: LT01', response.data)

    def test_detalhes_area_nao_existente(self):
        response = self.client.get('/armazem/NAOEXISTE', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'\xc3\x81rea com ID \'NAOEXISTE\' n\xc3\xa3o encontrada.', response.data)

    def test_adicionar_produto_area_como_gerente(self):
        area_id = "TESTA"
        response = self.client.post(f'/armazem/{area_id}/adicionar_produto', data={
            'id_produto_catalogo': 'MAN004',
            'quantidade': '5',
            'data_validade': '2026-01-01',
            'lote': 'LOTEADDTEST'
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Produto \'Manteiga com Sal 200g\' adicionado/atualizado com sucesso', response.data)
        
        area_obj = AreaArmazem.buscar_por_id(area_id)
        produtos_na_area = area_obj.listar_produtos()
        produto_adicionado = next((p for p in produtos_na_area if p.lote == "LOTEADDTEST"), None)
        self.assertIsNotNone(produto_adicionado)
        self.assertEqual(produto_adicionado.quantidade, 5)

    def test_adicionar_produto_area_como_operador_falha(self):
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
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Voc\xc3\xaa n\xc3\xa3o tem permiss\xc3\xa3o para realizar esta a\xc3\xa7\xc3\xa3o', response.data)
        
        area_obj = AreaArmazem.buscar_por_id(area_id)
        produtos_na_area = area_obj.listar_produtos()
        produto_nao_adicionado = next((p for p in produtos_na_area if p.lote == "LOTEFAILTEST"), None)
        self.assertIsNone(produto_nao_adicionado)

    def test_vender_produto_sucesso(self):
        area_id = "TESTA"
        response = self.client.post(f'/armazem/{area_id}/vender_produto', data={
            'id_produto_catalogo_venda': 'L001',
            'lote_venda': 'LT01',
            'quantidade_venda': '3',
            'destino_venda': 'Cliente Teste Venda'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Venda de 3 unidade(s) de \'Leite Teste\' (Lote: LT01) registrada com sucesso!', response.data)

        area_obj = AreaArmazem.buscar_por_id(area_id)
        produto_vendido = next(p for p in area_obj.listar_produtos() if p.lote == "LT01")
        self.assertEqual(produto_vendido.quantidade, 7)

        self.assertEqual(len(db_vendas_registradas), 1)
        venda_registrada = db_vendas_registradas[0]
        self.assertEqual(venda_registrada.id_catalogo_produto, 'L001')
        self.assertEqual(venda_registrada.quantidade_vendida, 3)
        self.assertEqual(venda_registrada.destino, 'Cliente Teste Venda')

    def test_vender_produto_quantidade_insuficiente(self):
        area_id = "TESTA"
        response = self.client.post(f'/armazem/{area_id}/vender_produto', data={
            'id_produto_catalogo_venda': 'L001',
            'lote_venda': 'LT01',
            'quantidade_venda': '15',
            'destino_venda': 'Cliente Teste Qtd Insuficiente'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Quantidade insuficiente em estoque para \'Leite Teste\' (Lote: LT01)', response.data)
        
        area_obj = AreaArmazem.buscar_por_id(area_id)
        produto = next(p for p in area_obj.listar_produtos() if p.lote == "LT01")
        self.assertEqual(produto.quantidade, 10)
        self.assertEqual(len(db_vendas_registradas), 0)

    def test_relatorios_acesso_gerente(self):
        response = self.client.get('/relatorios')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Relat\xc3\xb3rios e Monitoramento', response.data)
        self.assertIn(b'Estoque Atual Agregado', response.data)
        self.assertIn(b'Leite Teste', response.data)
    
    def test_relatorios_acesso_negado_operador(self):
        with self.client.session_transaction() as sess:
            sess['username'] = 'operador_teste'
            sess['user_funcao'] = 'operador'
        
        response = self.client.get('/relatorios', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Voc\xc3\xaa n\xc3\xa3o tem permiss\xc3\xa3o para realizar esta a\xc3\xa7\xc3\xa3o', response.data)
        self.assertNotIn(b'Estoque Atual Agregado', response.data)

    def test_api_produtos_area(self):
        response = self.client.get('/api/armazem/TESTA/produtos')
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertEqual(json_data['id_area'], 'TESTA')
        self.assertEqual(len(json_data['produtos']), 2)
        self.assertEqual(json_data['produtos'][0]['nome'], 'Leite Teste')

    def test_api_estoque_geral_gerente(self):
        response = self.client.get('/api/estoque_geral')
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertEqual(len(json_data), 2)
        self.assertEqual(json_data[0]['id_area'], 'TESTA')
        self.assertEqual(json_data[0]['produtos'][0]['id_catalogo_produto'], 'L001')

    def test_api_estoque_geral_operador_negado(self):
        with self.client.session_transaction() as sess:
            sess['username'] = 'operador_api'
            sess['user_funcao'] = 'operador'
        
        response = self.client.get('/api/estoque_geral', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Voc\xc3\xaa n\xc3\xa3o tem permiss\xc3\xa3o para realizar esta a\xc3\xa7\xc3\xa3o', response.data)

if __name__ == '__main__':
    unittest.main()