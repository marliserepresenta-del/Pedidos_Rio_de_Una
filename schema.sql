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
  file_name text not null,
  sheet_url text not null,
  item_count integer not null default 0,
  created_at timestamptz not null default now()
);

alter table public.profiles enable row level security;
alter table public.shipments enable row level security;

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

drop policy if exists profiles_select on public.profiles;
create policy profiles_select on public.profiles for select to authenticated
using (id = auth.uid() or public.is_active_admin());

drop policy if exists shipments_select on public.shipments;
create policy shipments_select on public.shipments for select to authenticated
using (public.is_active_admin());

drop policy if exists shipments_insert on public.shipments;
create policy shipments_insert on public.shipments for insert to authenticated
with check (public.is_active_admin() and user_id = auth.uid());

grant execute on function public.set_user_active(uuid,boolean) to authenticated;
grant select on public.profiles to authenticated;
grant select,insert on public.shipments to authenticated;
