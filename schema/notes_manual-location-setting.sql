select
    (select description from dev.locations l where l.location_id = f.location_id) as loc,
    (select node_label from dev.nodes n where n.node_id = f.node_id) as label,
    class,
    --serial_number,
    array_agg(DISTINCT serial_number) as sn,
    count(file_id), min(time) as time_start, max(time) as time_end
from dev.files_audio f
group by location_id, node_id, class --, serial_number
order by time_start

---- DONE ----

update dev.files_audio
set location_id = (select location_id from dev.locations where location ~= point(47.534230119, 7.614490083))
where node_id = (select node_id from dev.nodes where node_label = '2061-6644')
  and serial_number = '24A04F085FDF276E';

update dev.files_audio
set class = 'Chiroptera' -- these are bat recordings, at unknown location
where node_id = (select node_id from dev.nodes where node_label = '9589-1225')
  and serial_number = '24E144085F2569BF';

update dev.files_audio
set location_id = (select location_id from dev.locations where location ~= point(47.535135, 7.614674))
where node_id = (select node_id from dev.nodes where node_label = '1874-8542')
  and serial_number = '247475055F2569A5';

update dev.files_audio
set location_id = (select location_id from dev.locations where location ~= point(47.536054, 7.614804))
where node_id = (select node_id from dev.nodes where node_label = '4672-2602')
  -- 2 different devices were used at this location, with the same node_label
  and (serial_number = '24A04F085FDF2787' or serial_number = '24F319055FDF28DD');

update dev.files_audio
set location_id = (select location_id from dev.locations where location ~= point(47.534649, 7.613092))
where node_id = (select node_id from dev.nodes where node_label = '3704-8490')
  and serial_number = '24A04F085FDF273B';

update dev.files_audio
set location_id = (select location_id from dev.locations where location ~= point(47.538413, 7.615415))
where node_id = (select node_id from dev.nodes where node_label = '4258-6870')
  and serial_number = '24A04F085FDF2FF5';

update dev.files_audio
set location_id = (select location_id from dev.locations where location ~= point(47.537386128, 7.615148802))
where node_id = (select node_id from dev.nodes where node_label = '2614-9017')
  -- 2 different devices were used at this location, with the same node_label
  and (serial_number = '247AA5015FDF27AC' or serial_number = '24F319055FDF2902');

update dev.files_audio
set location_id = (select location_id from dev.locations where location ~= point(47.537170071, 7.614982059))
where node_id = (select node_id from dev.nodes where node_label = '8125-0324')
  -- class was set manually before, used to distinguish same node_id and serial_number
  -- the Orthoptera (grasshoppers) were recorded at unknown location (Weide),
  -- and a second sd-card (6431-2987 renamed to 3164-8729) was used to record
  -- some bats as well between this set and the orthoptera, at unknown location (Gundeli)
  and serial_number = '24A04F085FDF2793' and class = 'Chiroptera';

update dev.files_audio
set location_id = (select location_id from dev.locations where location ~= point(47.535255865, 7.614006247))
where node_id = (select node_id from dev.nodes where node_label = '0863-3235')
  -- same as above (24A04F085FDF2793 / 8125-0324 / Chiroptera)
  and serial_number = '24F319055FDF2902' and class = 'Chiroptera';

update dev.files_audio
set location_id = (select location_id from dev.locations where location ~= point(47.54329652492795, 7.596164727046104))
where node_id = (select node_id from dev.nodes where node_label = '6431-2987')
  and serial_number = '24E144036037E72E';

update dev.files_audio
set location_id = (select location_id from dev.locations where location ~= point(47.5612038295474, 7.591551112713341))
where node_id = (select node_id from dev.nodes where node_label = '6444-8804')
  and serial_number = '248D9B026037BAA6';

update dev.files_audio
set location_id = (select location_id from dev.locations where location ~= point(47.563053,7.595287))
where node_id = (select node_id from dev.nodes where node_label = '9589-1225')
  and serial_number = '24E144085F2569BF';

update dev.files_audio
set location_id = (select location_id from dev.locations where location ~= point(47.54329652492795,7.596164727046104))
where node_id = (select node_id from dev.nodes where node_label = '3164-8729')
  and serial_number in ('24A04F085FDF2787', '24A04F085FDF2793');

update dev.files_audio
    set location_id = 46 where node_id = (select node_id from dev.nodes where node_label = '3994-7806')
    and serial_number = '24F319055FDF2748' and class = 'Orthoptera';
update dev.files_audio
    set location_id = 47 where node_id = (select node_id from dev.nodes where node_label = '0863-3255')
    and serial_number = '24F319055FDF2902' and class = 'Orthoptera';
update dev.files_audio
    set location_id = 48 where node_id = (select node_id from dev.nodes where node_label = '8125-0324')
    and serial_number = '24A04F085FDF2793' and class = 'Orthoptera';
update dev.files_audio
    set location_id = 45 where node_id = (select node_id from dev.nodes where node_label = '8477-2673')
    and serial_number = '24A04F085FDF2787' and class = 'Orthoptera';

---- OTHER ----

-- finding deployments
-- file has location, time and node
-- node may have been deployed to multiple locations
-- timeranges are known from this sheet:
-- https://docs.google.com/spreadsheets/d/1H2KUk-7AxRO8rgsI3cCtQ9gxSG7RggAHPazr1KrZhzk/edit#gid=105081797

select count(file_id), min(time) as time_start, max(time) as time_end
from dev.files_audio f where serial_number = '24E144085F2569BF'
group by node_id
