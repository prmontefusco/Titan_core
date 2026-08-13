from apps.validacao.fumaca import ROTEIROS, _como_texto, _rodar


def test_como_texto_trata_none_str_e_bytes() -> None:
    assert _como_texto(None) == ""
    assert _como_texto("ja e texto") == "ja e texto"
    assert _como_texto("café".encode()) == "café"


def test_rodar_processo_bem_sucedido_captura_saida_e_codigo() -> None:
    # `python -m this` e parte da biblioteca padrao: sempre disponivel, sem
    # rede, sem banco, e sempre imprime o Zen of Python e sai com codigo 0.
    resultado = _rodar("zen de teste", ["this"])

    assert resultado.codigo == 0
    assert resultado.motivo is None
    # A cauda guarda só as últimas `_LINHAS_DE_CAUDA` linhas — o título do Zen
    # não sobrevive ao corte, mas sua última linha sim.
    assert "Namespaces are one honking great idea" in resultado.cauda
    assert resultado.duracao_segundos >= 0


def test_rodar_processo_com_falha_captura_codigo_nao_zero() -> None:
    resultado = _rodar("modulo inexistente", ["apps.validacao._modulo_inexistente_para_teste"])

    assert resultado.codigo != 0
    assert resultado.motivo is None
    assert resultado.cauda != ""


def test_roteiros_nao_tem_rotulo_ou_modulo_duplicado() -> None:
    rotulos = [rotulo for rotulo, _ in ROTEIROS]
    modulos = [tuple(modulo_args) for _, modulo_args in ROTEIROS]

    assert len(rotulos) == len(set(rotulos))
    assert len(modulos) == len(set(modulos))
