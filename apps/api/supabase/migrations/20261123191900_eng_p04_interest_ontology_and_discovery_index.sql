-- ENG-P04 forward migration: normalized interest ontology and opt-in discovery index.
-- Interest preferences remain owner-readable. The discovery index contains only
-- interests whose owner explicitly opted into interest matching and public discovery.

create table if not exists public.interest_catalog (
  interest_key text primary key check (interest_key ~ '^[a-z0-9][a-z0-9._-]{0,79}$'),
  label text not null check (char_length(label) between 1 and 80),
  label_key text not null check (char_length(label_key) between 1 and 100),
  category text not null check (char_length(category) between 1 and 60),
  aliases text[] not null default '{}',
  active boolean not null default true,
  sort_order integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

insert into public.interest_catalog(interest_key,label,label_key,category,aliases,active,sort_order)
values
  ('health','Kesehatan','auth.interest.health','wellbeing',array['Kesehatan'],true,10),
  ('technology','IT & Teknologi','auth.interest.tech','technology',array['IT & Teknologi','Teknologi'],true,20),
  ('spatial_3d','3D Spatial','auth.interest.spatial','spatial',array['3D Spatial','3D'],true,30),
  ('content_creator','Kreator Konten','auth.interest.creator','creator',array['Kreator Konten','Konten Kreator'],true,40),
  ('business_finance','Bisnis & Finansial','auth.interest.businessFinance','business',array['Bisnis & Finansial','Bisnis dan Finansial'],true,50),
  ('design_ui_ux','Desain & UI/UX','auth.interest.designUi','design',array['Desain & UI/UX','Desain'],true,60),
  ('education_research','Edukasi & Riset','auth.interest.education','education',array['Edukasi & Riset','Edukasi'],true,70),
  ('gaming_metaverse','Gaming & Metaverse','auth.interest.metaverse','gaming',array['Gaming & Metaverse','Gaming'],true,80)
on conflict (interest_key) do update set
  label=excluded.label,label_key=excluded.label_key,category=excluded.category,
  aliases=excluded.aliases,active=excluded.active,sort_order=excluded.sort_order,updated_at=now();

alter table public.interest_catalog enable row level security;
drop policy if exists interest_catalog_read_active on public.interest_catalog;
create policy interest_catalog_read_active on public.interest_catalog
for select to anon,authenticated using (active=true);
revoke all privileges on public.interest_catalog from anon,authenticated;
grant select on public.interest_catalog to anon,authenticated;
grant select,insert,update,delete on public.interest_catalog to service_role;

-- Ontology sensitivity is explicit: observed behavior must never infer a
-- sensitive interest. User-selected/explicit-feedback preferences remain
-- under direct user control.
alter table public.interest_catalog
  add column if not exists sensitivity text not null default 'standard'
  check (sensitivity in ('standard','sensitive'));
update public.interest_catalog set sensitivity='sensitive',updated_at=now()
 where interest_key='health' and sensitivity<>'sensitive';

create table if not exists public.interest_taxonomy_edges (
  source_interest_key text not null references public.interest_catalog(interest_key) on delete cascade,
  target_interest_key text not null references public.interest_catalog(interest_key) on delete cascade,
  relation_type text not null check (relation_type in ('parent_of','related_to')),
  weight numeric(4,3) not null default 1 check (weight between 0 and 1),
  active boolean not null default true,
  created_at timestamptz not null default now(),
  primary key(source_interest_key,target_interest_key,relation_type),
  check(source_interest_key<>target_interest_key)
);
alter table public.interest_taxonomy_edges enable row level security;
drop policy if exists interest_taxonomy_edges_read_active on public.interest_taxonomy_edges;
create policy interest_taxonomy_edges_read_active on public.interest_taxonomy_edges
for select to anon,authenticated using(active=true);
revoke all privileges on public.interest_taxonomy_edges from public,anon,authenticated;
grant select on public.interest_taxonomy_edges to anon,authenticated;
grant select,insert,update,delete on public.interest_taxonomy_edges to service_role;
insert into public.interest_taxonomy_edges(source_interest_key,target_interest_key,relation_type,weight)
values
  ('technology','spatial_3d','parent_of',1),
  ('technology','gaming_metaverse','parent_of',1),
  ('content_creator','design_ui_ux','related_to',0.8),
  ('business_finance','technology','related_to',0.6),
  ('education_research','technology','related_to',0.6),
  ('gaming_metaverse','spatial_3d','related_to',0.8)
on conflict (source_interest_key,target_interest_key,relation_type) do update
set weight=excluded.weight,active=true;

alter table public.user_settings alter column privacy_settings
  set default '{"discoverable_by_username":true,"allow_interest_matching":false}'::jsonb;
update public.user_settings
   set privacy_settings=jsonb_set(coalesce(privacy_settings,'{}'::jsonb),'{allow_interest_matching}','false'::jsonb,true)
 where not (coalesce(privacy_settings,'{}'::jsonb) ? 'allow_interest_matching');

create table if not exists private.user_interest_discovery_index (
  user_id uuid not null references auth.users(id) on delete cascade,
  interest_key text not null references public.interest_catalog(interest_key) on delete cascade,
  indexed_at timestamptz not null default now(),
  primary key(user_id,interest_key)
);
create index if not exists user_interest_discovery_index_interest_idx
  on private.user_interest_discovery_index(interest_key,user_id);
revoke all privileges on private.user_interest_discovery_index from public,anon,authenticated;
grant select,insert,update,delete on private.user_interest_discovery_index to service_role;

create or replace function private.refresh_user_interest_discovery_index(p_user_id uuid)
returns void
language plpgsql
security definer
set search_path = ''
as $refresh_interest_index$
begin
  delete from private.user_interest_discovery_index where user_id=p_user_id;
  if exists (
    select 1 from public.user_settings s
     where s.user_id=p_user_id
       and coalesce(s.privacy_settings,'{}'::jsonb) @> '{"discoverable_by_username":true,"allow_interest_matching":true}'::jsonb
       and exists (
         select 1 from public.profiles p
          where p.id=p_user_id and p.visibility='public' and p.account_status='active'
       )
  ) then
    insert into private.user_interest_discovery_index(user_id,interest_key)
    select ui.user_id,ui.interest_key
      from public.user_interests ui
      join public.interest_catalog c on c.interest_key=ui.interest_key and c.active=true
     where ui.user_id=p_user_id and ui.preference='interested'
    on conflict (user_id,interest_key) do update set indexed_at=now();
  end if;
end;
$refresh_interest_index$;

create or replace function private.refresh_interest_index_from_user_interests()
returns trigger
language plpgsql
security definer
set search_path = ''
as $refresh_interest_trigger$
begin
  if tg_op='DELETE' then
    perform private.refresh_user_interest_discovery_index(old.user_id);
    return old;
  end if;
  perform private.refresh_user_interest_discovery_index(new.user_id);
  if tg_op='UPDATE' and old.user_id is distinct from new.user_id then
    perform private.refresh_user_interest_discovery_index(old.user_id);
  end if;
  return new;
end;
$refresh_interest_trigger$;

create or replace function private.refresh_interest_index_from_user_settings()
returns trigger
language plpgsql
security definer
set search_path = ''
as $refresh_settings_trigger$
begin
  perform private.refresh_user_interest_discovery_index(new.user_id);
  return new;
end;
$refresh_settings_trigger$;

drop trigger if exists user_interests_refresh_discovery_index on public.user_interests;
create trigger user_interests_refresh_discovery_index
after insert or update or delete on public.user_interests
for each row execute function private.refresh_interest_index_from_user_interests();

drop trigger if exists user_settings_refresh_discovery_index on public.user_settings;
create trigger user_settings_refresh_discovery_index
after insert or update of privacy_settings on public.user_settings
for each row execute function private.refresh_interest_index_from_user_settings();

create or replace function public.set_my_interest_preference_for_actor(
  p_actor_user_id uuid,
  p_interest_key text,
  p_preference text
)
returns table(interest_key text,preference text,created_at timestamptz,updated_at timestamptz)
language plpgsql
security definer
set search_path = ''
as $set_interest$
declare
  v_interest_key text;
begin
  if coalesce(auth.role(),'') <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_actor_user_id is null or not exists(select 1 from auth.users u where u.id=p_actor_user_id) then
    raise exception 'interest_actor_not_found' using errcode='P0002';
  end if;
  if p_preference is null or p_preference not in ('interested','not_interested') then
    raise exception 'interest_preference_invalid' using errcode='22023';
  end if;
  select c.interest_key into v_interest_key
    from public.interest_catalog c
   where c.active=true
     and (lower(c.interest_key)=lower(p_interest_key)
       or exists(select 1 from unnest(c.aliases) a where lower(a)=lower(p_interest_key)))
   order by case when lower(c.interest_key)=lower(p_interest_key) then 0 else 1 end
   limit 1;
  if v_interest_key is null then
    -- Preserve preference updates for a user's pre-catalog legacy keys, but do
    -- not permit creating new arbitrary keys outside the canonical ontology.
    if exists(select 1 from public.user_interests ui where ui.user_id=p_actor_user_id and ui.interest_key=p_interest_key) then
      v_interest_key := p_interest_key;
    else
      raise exception 'interest_key_not_in_catalog' using errcode='22023';
    end if;
  end if;
  return query
  insert into public.user_interests as ui(user_id,interest_key,preference)
  values(p_actor_user_id,v_interest_key,p_preference)
  on conflict on constraint user_interests_pkey do update
    set preference=excluded.preference,updated_at=now()
  returning ui.interest_key,ui.preference,ui.created_at,ui.updated_at;
end;
$set_interest$;

create or replace function public.delete_my_interest_for_actor(
  p_actor_user_id uuid,
  p_interest_key text
)
returns table(interest_key text)
language plpgsql
security definer
set search_path = ''
as $delete_interest$
declare
  v_interest_key text;
begin
  if coalesce(auth.role(),'') <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_actor_user_id is null or not exists(select 1 from auth.users u where u.id=p_actor_user_id) then
    raise exception 'interest_actor_not_found' using errcode='P0002';
  end if;
  select c.interest_key into v_interest_key
    from public.interest_catalog c
   where c.active=true
     and (lower(c.interest_key)=lower(p_interest_key)
       or exists(select 1 from unnest(c.aliases) a where lower(a)=lower(p_interest_key)))
   order by case when lower(c.interest_key)=lower(p_interest_key) then 0 else 1 end
   limit 1;
  if v_interest_key is null then
    -- Existing custom/legacy keys remain removable after the catalog cutover.
    if exists(select 1 from public.user_interests ui where ui.user_id=p_actor_user_id and ui.interest_key=p_interest_key) then
      v_interest_key := p_interest_key;
    else
      raise exception 'interest_key_not_found' using errcode='P0002';
    end if;
  end if;
  return query delete from public.user_interests ui
   where ui.user_id=p_actor_user_id and ui.interest_key=v_interest_key
   returning ui.interest_key;
end;
$delete_interest$;

create or replace function public.find_interest_discovery_candidates(
  p_interest_keys text[],
  p_limit integer default 500
)
returns table(user_id uuid,interest_key text)
language plpgsql
security definer
set search_path = ''
as $find_interest_candidates$
begin
  if coalesce(auth.role(),'') <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if p_interest_keys is null or cardinality(p_interest_keys)=0
     or p_limit is null or p_limit not between 1 and 5000 then
    raise exception 'interest_discovery_query_invalid' using errcode='22023';
  end if;
  return query
  select i.user_id,i.interest_key
    from private.user_interest_discovery_index i
    join public.interest_catalog c on c.interest_key=i.interest_key and c.active=true
   where i.interest_key=any(p_interest_keys)
   order by i.interest_key,i.user_id
   limit p_limit;
end;
$find_interest_candidates$;

revoke all on function private.refresh_user_interest_discovery_index(uuid) from public,anon,authenticated;
revoke all on function private.refresh_interest_index_from_user_interests() from public,anon,authenticated;
revoke all on function private.refresh_interest_index_from_user_settings() from public,anon,authenticated;
revoke all on function public.set_my_interest_preference_for_actor(uuid,text,text) from public,anon,authenticated;
revoke all on function public.delete_my_interest_for_actor(uuid,text) from public,anon,authenticated;
revoke all on function public.find_interest_discovery_candidates(text[],integer) from public,anon,authenticated;
grant execute on function public.set_my_interest_preference_for_actor(uuid,text,text) to service_role;
grant execute on function public.delete_my_interest_for_actor(uuid,text) to service_role;
grant execute on function public.find_interest_discovery_candidates(text[],integer) to service_role;

revoke insert,update,delete on public.user_interests from anon,authenticated;
grant select on public.user_interests to authenticated;
grant select,insert,update,delete on public.user_interests to service_role;


