# laticinios_armazem/tests/test_models.py

import unittest
from datetime import datetime, timedelta
# Certifique-se de que o diretório pai (laticinios_armazem) está no PYTHONPATH
# Isso pode ser feito adicionando o caminho ou rodando os testes da raiz do projeto com `python -m unittest discover`
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import ProdutoLacteo, AreaArmazem, Venda, Usuario, db_areas_armazem, db_vendas_registradas, get_area_por_id, registrar_venda_no_db, popular_dados_iniciais, get_produto_catalogo_por_id

class TestProdutoLacteo(unittest.TestCase):
    def test_criar_produto(self):
        data_validade = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        produto = ProdutoLacteo("LEITE001", "Leite Integral", 10, data_validade, "LOTE01")
        self.assertEqual(produto.nome, "Leite Integral")
        self.assertEqual(produto.quantidade, 10)
        self.assertEqual(produto.lote, "LOTE01")
        self.assertEqual(produto.data_validade, datetime.strptime(data_validade, '%Y-%m-%d').date())

    def test_data_validade_invalida(self):
        with self.assertRaises(ValueError):
            ProdutoLacteo("LEITE001", "Leite Integral", 10, "30/12/2025", "LOTE01")

class TestAreaArmazem(unittest.TestCase):
    def setUp(self):
        # Limpa e recria a área para cada teste para evitar interferência
        db_areas_armazem["TESTE99"] = {"nome": "Área de Teste", "produtos": []}
        self.area = get_area_por_id("TESTE99")
        self.produto1 = ProdutoLacteo("QUE003", "Queijo Teste", 20, "2025-12-31", "LTESTE01")
        self.produto2 = ProdutoLacteo("IOG002", "Iogurte Teste", 15, "2025-11-30", "LTESTE02")

    def tearDown(self):
        # Remove a área de teste após os testes
        if "TESTE99" in db_areas_armazem:
            del db_areas_armazem["TESTE99"]

    def test_adicionar_produto_novo(self):
        self.area.adicionar_produto(self.produto1)
        produtos_na_area = self.area.listar_produtos()
        self.assertEqual(len(produtos_na_area), 1)
        self.assertEqual(produtos_na_area[0].nome, "Queijo Teste")
        self.assertEqual(produtos_na_area[0].quantidade, 20)

    def test_adicionar_produto_existente_mesmo_lote(self):
        self.area.adicionar_produto(self.produto1) # Adiciona 20 unidades
        produto_mesmo_lote = ProdutoLacteo("QUE003", "Queijo Teste", 5, "2025-12-31", "LTESTE01")
        self.area.adicionar_produto(produto_mesmo_lote) # Adiciona mais 5
        
        produtos_na_area = self.area.listar_produtos()
        self.assertEqual(len(produtos_na_area), 1) # Deve continuar sendo 1 produto (mesmo lote)
        self.assertEqual(produtos_na_area[0].quantidade, 25) # Quantidade somada

    def test_adicionar_produto_existente_lote_diferente(self):
        self.area.adicionar_produto(self.produto1) # LTESTE01
        produto_lote_diferente = ProdutoLacteo("QUE003", "Queijo Teste", 10, "2025-12-31", "LTESTE03")
        self.area.adicionar_produto(produto_lote_diferente) # LTESTE03

        produtos_na_area = self.area.listar_produtos()
        self.assertEqual(len(produtos_na_area), 2) # Dois produtos distintos devido ao lote


    def test_remover_produto_sucesso(self):
        self.area.adicionar_produto(self.produto1) # 20 unidades
        removido = self.area.remover_produto("QUE003", "LTESTE01", 5)
        self.assertTrue(removido)
        self.assertEqual(self.area.listar_produtos()[0].quantidade, 15)

    def test_remover_produto_totalmente(self):
        self.area.adicionar_produto(self.produto1) # 20 unidades
        removido = self.area.remover_produto("QUE003", "LTESTE01", 20)
        self.assertTrue(removido)
        self.assertEqual(len(self.area.listar_produtos()), 0) # Produto deve ser removido da lista

    def test_remover_produto_quantidade_insuficiente(self):
        self.area.adicionar_produto(self.produto1) # 20 unidades
        removido = self.area.remover_produto("QUE003", "LTESTE01", 25)
        self.assertFalse(removido)
        self.assertEqual(self.area.listar_produtos()[0].quantidade, 20) # Quantidade não deve mudar

    def test_remover_produto_nao_existente(self):
        removido = self.area.remover_produto("XYZ789", "LOTEXYZ", 5)
        self.assertFalse(removido)

class TestVenda(unittest.TestCase):
    def test_criar_venda(self):
        venda = Venda("LEITE001", "Leite Integral", "LOTEABC", 5, "Cliente X", "A1")
        self.assertEqual(venda.quantidade_vendida, 5)
        self.assertEqual(venda.destino, "Cliente X")
        self.assertIsNotNone(venda.data_hora)

    def test_registrar_venda_no_db(self):
        db_vendas_registradas.clear() # Limpa para o teste
        venda = Venda("IOG002", "Iogurte", "LOTE123", 10, "Supermercado Y", "B2")
        registrar_venda_no_db(venda)
        self.assertEqual(len(db_vendas_registradas), 1)
        self.assertEqual(db_vendas_registradas[0].nome_produto, "Iogurte")

class TestUsuario(unittest.TestCase):
    def test_verificar_senha_correta(self):
        usuario = Usuario.verificar_senha("operador1", "senha123")
        self.assertIsNotNone(usuario)
        self.assertEqual(usuario.username, "operador1")
        self.assertEqual(usuario.funcao, "operador")

    def test_verificar_senha_incorreta(self):
        usuario = Usuario.verificar_senha("operador1", "senhaerrada")
        self.assertIsNone(usuario)

    def test_permissao_gerente(self):
        gerente = Usuario.verificar_senha("gerente1", "senhaforte")
        self.assertTrue(gerente.tem_permissao("qualquer_coisa"))

    def test_permissao_operador(self):
        operador = Usuario.verificar_senha("operador1", "senha123")
        self.assertTrue(operador.tem_permissao("registrar_venda"))
        self.assertFalse(operador.tem_permissao("ver_relatorios_completos")) # Exemplo de permissão restrita

class TestFuncoesAuxiliares(unittest.TestCase):
    def setUp(self):
        # Garante que os dados de teste não interfiram com os dados populados
        self._original_db_areas = db_areas_armazem.copy()
        self._original_db_produtos_catalogo = db_produtos_catalogo[:]
        
        # Limpa e recria áreas para testes específicos, se necessário
        db_areas_armazem.clear()
        db_areas_armazem["TSTA"] = {"nome": "Área Teste A", "produtos": []}
        db_areas_armazem["TSTB"] = {"nome": "Área Teste B", "produtos": []}

        db_produtos_catalogo.clear()
        db_produtos_catalogo.append({"id": "PRODTST", "nome": "Produto de Teste"})

    def tearDown(self):
        # Restaura os dados originais
        db_areas_armazem.clear()
        db_areas_armazem.update(self._original_db_areas)
        
        db_produtos_catalogo.clear()
        db_produtos_catalogo.extend(self._original_db_produtos_catalogo)
        # db_areas_armazem = self._original_db_areas # Não funciona como esperado para dicionários globais
        # db_produtos_catalogo = self._original_db_produtos_catalogo


    def test_get_area_por_id(self):
        area = get_area_por_id("TSTA")
        self.assertIsNotNone(area)
        self.assertEqual(area.nome, "Área Teste A")
        area_inexistente = get_area_por_id("NAOEXISTE")
        self.assertIsNone(area_inexistente)

    def test_get_produto_catalogo_por_id(self):
        produto_cat = get_produto_catalogo_por_id("PRODTST")
        self.assertIsNotNone(produto_cat)
        self.assertEqual(produto_cat["nome"], "Produto de Teste")
        produto_cat_inexistente = get_produto_catalogo_por_id("NAOEXISTE")
        self.assertIsNone(produto_cat_inexistente)


if __name__ == '__main__':
    # Chama a popular_dados_iniciais antes de rodar os testes para garantir que A1, B2, C3 existam
    # para testes que possam depender deles implicitamente, embora os testes atuais tentem ser isolados.
    # No entanto, é melhor que cada classe de teste configure seu próprio ambiente no setUp.
    # popular_dados_iniciais() # Removido daqui, pois setUp deve cuidar do estado.
    unittest.main()