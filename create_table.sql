-- Run this in your Supabase SQL Editor to create the deals table
create table deals (
  id bigint primary key,
  title text,
  value numeric,
  currency text,
  status text,
  stage_id bigint,
  pipeline_id bigint,
  owner_name text,
  add_time timestamp with time zone,
  won_time timestamp with time zone,
  close_time timestamp with time zone,
  activities_count int,
  notes_count int,
  email_messages_count int,
  org_name text,
  person_name text
);

-- Optional: Create an index on common filter columns for speed
create index idx_deals_status on deals(status);
create index idx_deals_pipeline on deals(pipeline_id);
create index idx_deals_owner on deals(owner_name);
