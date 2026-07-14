create table topics (
  slug     text primary key,
  name     text not null,
  color    text not null,
  layout   text not null,
  fields   jsonb not null default '[]'::jsonb,
  position integer not null
);

create table entries (
  topic_slug text    not null references topics(slug) on delete cascade,
  id         integer not null,
  date       text    not null default '',
  image      text,
  "values"   jsonb   not null default '{}'::jsonb,
  primary key (topic_slug, id)
);

create table posts (
  topic_slug text    not null,
  entry_id   integer not null,
  doc        jsonb   not null,
  primary key (topic_slug, entry_id),
  foreign key (topic_slug, entry_id) references entries(topic_slug, id) on delete cascade
);
