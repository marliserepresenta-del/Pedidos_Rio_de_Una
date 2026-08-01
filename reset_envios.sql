-- LIMPEZA SOLICITADA: apaga somente envios e produtos, preservando os usuários.
-- Execute uma única vez no SQL Editor do Supabase.
begin;

alter table public.shipment_items
  add column if not exists valor_unitario numeric;

truncate table public.shipment_items, public.shipments restart identity cascade;

commit;

select
  (select count(*) from public.shipments) as envios,
  (select count(*) from public.shipment_items) as produtos;
