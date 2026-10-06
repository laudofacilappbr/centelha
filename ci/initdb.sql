-- Banco separado para o ciclo de migração: os testes criam tabelas com create_all no
-- centelha_test, e upgrade/check/downgrade precisam de um banco vazio.
CREATE DATABASE centelha_mig;
