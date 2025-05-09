# laticinios_armazem/test_models.py

import unittest
from datetime import datetime, date
from models import (
    Usuario, ProdutoLacteo, AreaArmazem, Venda,
    db_usuarios, db_areas_armazem, db_vendas_registradas, db_produtos_catalogo,
    get_produto_catalogo_por_id
)

class TestModels(unittest.TestCase):
    def setUp(self):
        # Limpar bancos de dados globais antes de cada teste
        db_usuarios.clear()
        db_areas_armazem.clear()
        db_vendas_registradas.clear()
        db_produtos_catalogo.clear()

        # Configurar dados de teste
        db_usuarios.update({
            'test_user': {'senha': 'test123', 'funcao': 'operador', 'nome': 'Teste Operador'}
        })
        db_produtos_catalogo.update({
            'TEST001': {'nome': 'Leite Teste 1L'}
        })
        db_areas_armazem.update({
            'TEST1': {
                'nome': 'Área Teste',
                'tipo_armazenamento': 'refrigerado',
                'produtos': []
            }
        })

    def tearDown(self):
        # Limpar bancos de dados após cada teste
        db_usuarios.clear()
        db_areas_armazem.clear()
        db_vendas_registradas.clear()
        db_produtos_catalogo.clear()

    def test_usuario_verificar_senha(self):
        usuario = Usuario.verificar_senha('test_user', 'test123')
        self.assertIsNotNone(usuario)
        self.assertEqual(usuario.username, 'test_user')
        self.assertEqual(usuario.funcao, 'operador')
        self.assertEqual(usuario.nome, 'Teste Operador')
        usuario = Usuario.verificar_senha('test_user', 'wrong')
        self.assertIsNone(usuario)
        usuario = Usuario.verificar_senha('non_existent', 'test123')
        self.assertIsNone(usuario)

    def test_usuario_tem_permissao(self):
        usuario = Usuario('test_user', 'operador', 'Teste Operador')
        self.assertTrue(usuario.tem_permissao('visualizar_armazem'))
        self.assertFalse(usuario.tem_permissao('gerente'))

    def test_produto_lacteo(self):
        produto = ProdutoLacteo(
            id_catalogo_produto='TEST001',
            nome='Leite Teste 1L',
            quantidade=100,
            data_validade_str='2025-06-01',
            lote='LOTE001'
        )
        self.assertEqual(produto.id_catalogo_produto, 'TEST001')
        self.assertEqual(produto.nome, 'Leite Teste 1L')
        self.assertEqual(produto.quantidade, 100)
        self.assertEqual(produto.data_validade, date(2025, 6, 1))
        self.assertEqual(produto.lote, 'LOTE001')
        produto_dict = produto.to_dict()
        self.assertEqual(produto_dict['data_validade'], '2025-06-01')

    def test_area_armazem_adicionar_produto(self):
        area = AreaArmazem('TEST1', 'Área Teste', 'refrigerado')
        produto = ProdutoLacteo('TEST001', 'Leite Teste 1L', 100, '2025-06-01', 'LOTE001')
        area.adicionar_produto(produto)
        produtos = area.listar_produtos()
        self.assertEqual(len(produtos), 1)
        self.assertEqual(produtos[0].quantidade, 100)
        self.assertEqual(produtos[0].data_validade, date(2025, 6, 1))
        produto2 = ProdutoLacteo('TEST001', 'Leite Teste 1L', 50, '2025-06-01', 'LOTE001')
        area.adicionar_produto(produto2)
        produtos = area.listar_produtos()
        self.assertEqual(len(produtos), 1)
        self.assertEqual(produtos[0].quantidade, 150)
        produto3 = ProdutoLacteo('TEST001', 'Leite Teste 1L', 30, '2025-06-01', 'LOTE002')
        area.adicionar_produto(produto3)
        produtos = area.listar_produtos()
        self.assertEqual(len(produtos), 2)

    def test_area_armazem_remover_produto(self):
        area = AreaArmazem('TEST1', 'Área Teste', 'refrigerado')
        produto = ProdutoLacteo('TEST001', 'Leite Teste 1L', 100, '2025-06-01', 'LOTE001')
        area.adicionar_produto(produto)
        sucesso = area.remover_produto('TEST001', 'LOTE001', 40)
        self.assertTrue(sucesso)
        produtos = area.listar_produtos()
        self.assertEqual(produtos[0].quantidade, 60)
        sucesso = area.remover_produto('TEST001', 'LOTE001', 60)
        self.assertTrue(sucesso)
        self.assertEqual(len(area.listar_produtos()), 0)
        sucesso = area.remover_produto('TEST001', 'LOTE001', 10)
        self.assertFalse(sucesso)

    def test_venda_registrar(self):
        venda = Venda(
            id_catalogo_produto='TEST001',
            nome='Leite Teste 1L',
            lote='LOTE001',
            data_validade_produto='2025-06-01',
            quantidade_vendida=50,
            destino='Cliente Teste',
            area_origem_id='TEST1',
            usuario_responsavel='test_user'
        )
        Venda.registrar(venda)
        self.assertEqual(len(db_vendas_registradas), 1)
        venda_registrada = db_vendas_registradas[0]
        self.assertEqual(venda_registrada.nome, 'Leite Teste 1L')
        self.assertEqual(venda_registrada.quantidade_vendida, 50)

    def test_get_produto_catalogo_por_id(self):
        produto = get_produto_catalogo_por_id('TEST001')
        self.assertEqual(produto['nome'], 'Leite Teste 1L')
        produto = get_produto_catalogo_por_id('INVALID')
        self.assertIsNone(produto)

    def test_db_produtos_catalogo_is_dict(self):
        # Verificar que db_produtos_catalogo permanece um dicionário
        self.assertIsInstance(db_produtos_catalogo, dict)
        db_produtos_catalogo['TEST002'] = {'nome': 'Queijo Teste 500g'}
        self.assertIsInstance(db_produtos_catalogo, dict)
        self.assertIn('TEST002', db_produtos_catalogo)

if __name__ == '__main__':
    unittest.main()