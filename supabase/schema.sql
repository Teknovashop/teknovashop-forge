create extension if not exists pgcrypto;

create table if not exists public.models (
  id uuid primary key default gen_random_uuid(),
  slug text unique not null,
  name text not null,
  category text not null,
  base_price_cents int not null default 490,
  commercial_multiplier real not null default 2.0,
  params jsonb not null,
  created_at timestamptz default now()
);

create table if not exists public.device_presets (
  id uuid primary key default gen_random_uuid(),
  model_id uuid references public.models(id) on delete cascade,
  brand text,
  device text,
  slug text unique not null,
  params jsonb not null,
  created_at timestamptz default now()
);

create table if not exists public.orders (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id),
  model_id uuid references public.models(id),
  preset_id uuid references public.device_presets(id),
  license text not null check (license in ('personal','commercial')),
  amount_cents int not null,
  currency text not null default 'EUR',
  stripe_payment_intent text,
  status text not null default 'created',
  created_at timestamptz default now()
);

create table if not exists public.stl_jobs (
  id uuid primary key default gen_random_uuid(),
  order_id uuid references public.orders(id) on delete cascade,
  model_slug text not null,
  params jsonb not null,
  stl_path text,
  preview_path text,
  status text not null default 'queued',
  error text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

alter table public.models enable row level security;
alter table public.device_presets enable row level security;
alter table public.orders enable row level security;
alter table public.stl_jobs enable row level security;

drop policy if exists read_models on public.models;
drop policy if exists read_presets on public.device_presets;
drop policy if exists user_read_orders on public.orders;
drop policy if exists user_read_jobs on public.stl_jobs;

create policy read_models on public.models for select using (true);
create policy read_presets on public.device_presets for select using (true);
create policy user_read_orders on public.orders for select using (auth.uid() = user_id);
create policy user_read_jobs on public.stl_jobs for select using (
  exists(select 1 from public.orders o where o.id = order_id and o.user_id = auth.uid())
);

insert into public.models (slug, name, category, base_price_cents, params) values
('vesa-adapter', 'Adaptador VESA universal', 'vesa', 590,
 '{ "params": [
   {"key":"width","label":"Ancho base (mm)","min":80,"max":300,"step":1,"default":180},
   {"key":"height","label":"Alto base (mm)","min":80,"max":300,"step":1,"default":180},
   {"key":"thickness","label":"Espesor (mm)","min":2,"max":12,"step":0.5,"default":6},
   {"key":"pattern","label":"Patrón VESA","options":["75x75","100x100","200x200"],"default":"100x100"}
 ]}')
on conflict (slug) do nothing;

insert into public.models (slug, name, category, base_price_cents, params) values
('router-mount', 'Soporte pared para router', 'mount', 490,
 '{ "params": [
   {"key":"width","label":"Ancho router (mm)","min":60,"max":300,"step":1,"default":120},
   {"key":"depth","label":"Fondo router (mm)","min":20,"max":200,"step":1,"default":60},
   {"key":"lip","label":"Borde de retención (mm)","min":2,"max":20,"step":1,"default":6}
 ]}')
on conflict (slug) do nothing;

insert into public.models (slug, name, category, base_price_cents, params) values
('cable-tray', 'Organizador de cables (bandeja)', 'cable', 390,
 '{ "params": [
   {"key":"length","label":"Longitud (mm)","min":80,"max":800,"step":5,"default":300},
   {"key":"width","label":"Ancho (mm)","min":20,"max":200,"step":2,"default":60},
   {"key":"height","label":"Altura (mm)","min":10,"max":120,"step":1,"default":40}
 ]}')
on conflict (slug) do nothing;
