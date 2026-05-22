-- CoopTech Tulcán — Esquema MVP mora preventiva
-- Ejecutar en Supabase SQL Editor

create extension if not exists "uuid-ossp";

create table if not exists public.socios (
  id uuid primary key default uuid_generate_v4(),
  cedula text not null unique,
  nombre text not null,
  agencia text,
  telefono text,
  features jsonb default '{}'::jsonb,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists public.predicciones (
  id uuid primary key default uuid_generate_v4(),
  socio_id uuid references public.socios(id) on delete cascade,
  probabilidad_mora numeric(6,4) not null,
  nivel_riesgo text not null check (nivel_riesgo in ('bajo', 'medio', 'alto')),
  features jsonb default '{}'::jsonb,
  created_at timestamptz default now()
);

create index if not exists idx_predicciones_socio on public.predicciones(socio_id);
create index if not exists idx_predicciones_nivel on public.predicciones(nivel_riesgo);

create table if not exists public.alertas (
  id uuid primary key default uuid_generate_v4(),
  socio_id uuid references public.socios(id) on delete cascade,
  mensaje text not null,
  nivel text not null,
  atendida boolean default false,
  created_at timestamptz default now()
);

-- RLS: lectura pública anon para MVP demo (ajustar en producción)
alter table public.socios enable row level security;
alter table public.predicciones enable row level security;
alter table public.alertas enable row level security;

create policy "socios_read_all" on public.socios for select using (true);
create policy "predicciones_read_all" on public.predicciones for select using (true);
create policy "alertas_read_all" on public.alertas for select using (true);

create policy "socios_insert_service" on public.socios for insert with check (true);
create policy "predicciones_insert_service" on public.predicciones for insert with check (true);

-- Trigger updated_at
create or replace function public.set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists socios_updated_at on public.socios;
create trigger socios_updated_at
  before update on public.socios
  for each row execute function public.set_updated_at();
