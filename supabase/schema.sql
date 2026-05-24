create table user_inventory (
  user_id uuid primary key references auth.users(id) on delete cascade,
  my_camera_ids jsonb not null default '[]',
  my_battery_ids jsonb not null default '[]',
  updated_at timestamptz not null default now()
);

alter table user_inventory enable row level security;

create policy "Users can read own inventory"
on user_inventory
for select
using (auth.uid() = user_id);

create policy "Users can insert own inventory"
on user_inventory
for insert
with check (auth.uid() = user_id);

create policy "Users can update own inventory"
on user_inventory
for update
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

create policy "Users can delete own inventory"
on user_inventory
for delete
using (auth.uid() = user_id);
