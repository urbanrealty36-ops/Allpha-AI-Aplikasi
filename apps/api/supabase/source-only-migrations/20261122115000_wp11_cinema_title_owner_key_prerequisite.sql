-- SOURCE ONLY — WP-11 prerequisite for the composite title/owner foreign key.
-- The Cinema generation link migration references cinema_titles(id, owner_id).
-- The production table currently has a primary key on id only, so PostgreSQL
-- cannot create that composite FK until this matching unique index exists.
-- This additive index preserves the existing primary key and row semantics.
begin;

do $$
begin
  if to_regclass('public.cinema_titles') is null
     or not exists (
       select 1 from information_schema.columns
       where table_schema='public' and table_name='cinema_titles'
         and column_name='id' and data_type='uuid'
     )
     or not exists (
       select 1 from information_schema.columns
       where table_schema='public' and table_name='cinema_titles'
         and column_name='owner_id' and data_type='uuid'
     ) then
    raise exception 'WP11_CINEMA_TITLE_OWNER_KEY_COLUMNS_MISSING';
  end if;
end $$;

create unique index if not exists cinema_titles_id_owner_id_uidx
  on public.cinema_titles(id, owner_id);

do $$
begin
  if not exists (
    select 1 from pg_index i
    join pg_class t on t.oid=i.indrelid
    join pg_class x on x.oid=i.indexrelid
    where t.oid='public.cinema_titles'::regclass
      and x.relname='cinema_titles_id_owner_id_uidx'
      and i.indisunique and i.indisvalid
  ) then
    raise exception 'WP11_CINEMA_TITLE_OWNER_KEY_INDEX_NOT_READY';
  end if;
end $$;

commit;
