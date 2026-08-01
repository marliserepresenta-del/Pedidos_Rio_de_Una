-- Execute este arquivo uma vez no SQL Editor do Supabase.
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text not null unique,
  name text,
  active boolean not null default false,
  created_at timestamptz not null default now()
);

create table if not exists public.shipments (
  id bigint generated always as identity primary key,
  user_id uuid not null references public.profiles(id),
  user_email text not null,
  file_name text not null default '',
  sheet_url text not null default '',
  batch_name text,
  file_names text[] not null default '{}',
  item_count integer not null default 0,
  duplicate_count integer not null default 0,
  created_at timestamptz not null default now()
);

alter table public.shipments add column if not exists batch_name text;
alter table public.shipments add column if not exists file_names text[] not null default '{}';
alter table public.shipments add column if not exists duplicate_count integer not null default 0;
alter table public.shipments alter column file_name set default '';
alter table public.shipments alter column sheet_url set default '';

create table if not exists public.shipment_items (
  id_registro text primary key,
  shipment_id bigint not null references public.shipments(id) on delete cascade,
  arquivo text,
  pagina integer,
  fornecedor text,
  comprador text,
  empresa text,
  local text,
  pedido text,
  pedido_fornecedor text,
  emissao date,
  recebimento date,
  codigo_produto text,
  produto text,
  status text,
  unidade text,
  embalagem numeric,
  quantidade numeric,
  valor_item numeric,
  created_at timestamptz not null default now()
);

alter table public.profiles enable row level security;
alter table public.shipments enable row level security;
alter table public.shipment_items enable row level security;

create or replace function public.is_active_admin()
returns boolean language sql stable security definer set search_path = public
as $$ select exists(select 1 from public.profiles where id = auth.uid() and active); $$;

create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public
as $$
begin
  insert into public.profiles(id,email,name,active)
  values (
    new.id,
    lower(new.email),
    coalesce(new.raw_user_meta_data->>'name',''),
    lower(new.email) = 'ricardo.lidio@yahoo.com.br'
  ) on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created after insert on auth.users
for each row execute procedure public.handle_new_user();

insert into public.profiles(id,email,name,active)
select
  id,
  lower(email),
  coalesce(raw_user_meta_data->>'name',''),
  lower(email) = 'ricardo.lidio@yahoo.com.br'
from auth.users
on conflict (id) do nothing;

create or replace function public.set_user_active(target_id uuid, desired_active boolean)
returns void language plpgsql security definer set search_path = public
as $$
begin
  if not public.is_active_admin() then raise exception 'Acesso não autorizado'; end if;
  if target_id = auth.uid() then raise exception 'Você não pode desativar a própria conta'; end if;
  if desired_active and (select count(*) from public.profiles where active) >= 4 then
    raise exception 'O limite de quatro usuários ativos foi atingido';
  end if;
  update public.profiles set active = desired_active where id = target_id;
end;
$$;

create or replace function public.finalize_shipment(
  p_batch_name text,
  p_file_names text[],
  p_items jsonb
)
returns table(shipment_id bigint, inserted_count integer, duplicate_count integer)
language plpgsql security definer set search_path = public
as $$
declare
  v_shipment_id bigint;
  v_inserted integer := 0;
  v_total integer := coalesce(jsonb_array_length(p_items), 0);
begin
  if not public.is_active_admin() then raise exception 'Acesso não autorizado'; end if;

  insert into public.shipments(user_id,user_email,file_name,sheet_url,batch_name,file_names)
  values (auth.uid(), auth.jwt()->>'email', '', '', p_batch_name, coalesce(p_file_names,'{}'))
  returning id into v_shipment_id;

  insert into public.shipment_items(
    id_registro,shipment_id,arquivo,pagina,fornecedor,comprador,empresa,local,
    pedido,pedido_fornecedor,emissao,recebimento,codigo_produto,produto,status,
    unidade,embalagem,quantidade,valor_item
  )
  select
    x.id_registro,v_shipment_id,x.arquivo,x.pagina,x.fornecedor,x.comprador,
    x.empresa,x.local,x.pedido,x.pedido_fornecedor,x.emissao,x.recebimento,
    x.codigo_produto,x.produto,x.status,x.unidade,x.embalagem,x.quantidade,x.valor_item
  from jsonb_to_recordset(p_items) as x(
    id_registro text,arquivo text,pagina integer,fornecedor text,comprador text,
    empresa text,local text,pedido text,pedido_fornecedor text,emissao date,
    recebimento date,codigo_produto text,produto text,status text,unidade text,
    embalagem numeric,quantidade numeric,valor_item numeric
  )
  on conflict (id_registro) do nothing;

  get diagnostics v_inserted = row_count;
  update public.shipments
  set item_count = v_inserted, duplicate_count = v_total - v_inserted
  where id = v_shipment_id;

  return query select v_shipment_id, v_inserted, v_total - v_inserted;
end;
$$;

drop policy if exists profiles_select on public.profiles;
create policy profiles_select on public.profiles for select to authenticated
using (id = auth.uid() or public.is_active_admin());

drop policy if exists shipments_select on public.shipments;
create policy shipments_select on public.shipments for select to authenticated
using (public.is_active_admin());

drop policy if exists shipments_insert on public.shipments;
create policy shipments_insert on public.shipments for insert to authenticated
with check (public.is_active_admin() and user_id = auth.uid());

drop policy if exists shipment_items_select on public.shipment_items;
create policy shipment_items_select on public.shipment_items for select to authenticated
using (public.is_active_admin());

grant execute on function public.set_user_active(uuid,boolean) to authenticated;
grant execute on function public.finalize_shipment(text,text[],jsonb) to authenticated;
grant select on public.profiles to authenticated;
grant select,insert on public.shipments to authenticated;
grant select on public.shipment_items to authenticated;
