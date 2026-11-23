begin;

-- Forward repair: align the first ENG-P13 bridge migration with the existing
-- cinema_api.py contract. Keep the original identifiers and constraints intact.
alter table public.cinema_generation_job_links
  add column if not exists owner_id uuid references auth.users(id) on delete restrict,
  add column if not exists title_id uuid references public.cinema_titles(id) on delete cascade,
  add column if not exists requester_user_id uuid references auth.users(id) on delete restrict,
  add column if not exists target_section text,
  add column if not exists expected_title_version integer,
  add column if not exists idempotency_key text,
  add column if not exists applied_at timestamptz,
  add column if not exists applied_version integer;

-- Preserve existing rows if any; derive legacy request identity from its
-- recorded owner/job rather than dropping or replacing records.
update public.cinema_generation_job_links l
set owner_id = coalesce(l.owner_id, l.owner_user_id),
    title_id = coalesce(l.title_id, l.cinema_title_id),
    requester_user_id = coalesce(l.requester_user_id, l.owner_user_id),
    target_section = coalesce(l.target_section, 'screenplay_draft'),
    expected_title_version = coalesce(l.expected_title_version, t.version, 1),
    idempotency_key = coalesce(l.idempotency_key, 'legacy:' || l.generation_job_id::text)
from public.cinema_titles t
where t.id = l.cinema_title_id;

update public.cinema_generation_job_links l
set owner_id = coalesce(l.owner_id, l.owner_user_id),
    title_id = coalesce(l.title_id, l.cinema_title_id),
    requester_user_id = coalesce(l.requester_user_id, l.owner_user_id),
    target_section = coalesce(l.target_section, 'screenplay_draft'),
    expected_title_version = coalesce(l.expected_title_version, 1),
    idempotency_key = coalesce(l.idempotency_key, 'legacy:' || l.generation_job_id::text)
where l.owner_id is null or l.title_id is null or l.requester_user_id is null
   or l.target_section is null or l.expected_title_version is null
   or l.idempotency_key is null;

alter table public.cinema_generation_job_links
  alter column owner_id set not null,
  alter column title_id set not null,
  alter column requester_user_id set not null,
  alter column target_section set not null,
  alter column expected_title_version set not null,
  alter column idempotency_key set not null;

alter table public.cinema_generation_job_links
  add constraint cinema_generation_job_links_target_section_check
    check (target_section in ('screenplay_draft')),
  add constraint cinema_generation_job_links_expected_version_check
    check (expected_title_version >= 1),
  add constraint cinema_generation_job_links_idempotency_key_check
    check (char_length(idempotency_key) between 8 and 160);

create unique index if not exists cinema_generation_job_links_requester_idempotency_uidx
  on public.cinema_generation_job_links(requester_user_id, idempotency_key);

create index if not exists cinema_generation_job_links_title_contract_idx
  on public.cinema_generation_job_links(owner_id, title_id, created_at desc);

commit;