import zipfile
import codecs
import json
import os
import shutil
from globalization.provider import GeoNamesProvider

from pmetro.file_utils import get_file_ext
from pmetro.serialization import write_as_json_file
from settings import INDEX_LANGUAGE_SET


class MapIndexEntity(object):
    def __init__(self, uid, geoname_id, file, size, timestamp, transports, latitude, longitude):
        self.uid = uid
        self.geoname_id = geoname_id
        self.file = file
        self.size = size
        self.timestamp = timestamp
        self.transports = transports
        self.latitude = latitude
        self.longitude = longitude


def publish_maps(maps_path, publishing_path):
    __publish_maps(maps_path, publishing_path)
    __rebuild_index(publishing_path)


def __publish_maps(maps_path, publishing_path):
    for file_name in [f for f in os.listdir(maps_path) if get_file_ext(os.path.join(maps_path, f)) == 'zip']:
        source_file = os.path.join(maps_path, file_name)
        destination_file = os.path.join(publishing_path, file_name)

        if os.path.isfile(destination_file) and os.path.getsize(source_file) == os.path.getsize(
                destination_file) and os.path.getmtime(source_file) == os.path.getmtime(destination_file):
            continue

        if os.path.isfile(destination_file):
            os.remove(destination_file)
        shutil.copy2(source_file, publishing_path)


def __rebuild_index(publishing_path):
    maps_index = sorted(__create_index(publishing_path), key=lambda k: k.uid)
    write_as_json_file(maps_index, os.path.join(publishing_path, 'index.json'))

    localizations = __create_locales((map.geoname_id for map in maps_index))

    for locale in localizations['locales']:
        write_as_json_file(localizations['locales'][locale],
                           os.path.join(publishing_path, 'locale.{0}.json'.format(locale)))

    write_as_json_file(localizations['locales'][localizations['default_locale']],
                       os.path.join(publishing_path, 'locale.default.json'))


def __create_locales(geoname_ids):
    geonames_provider = GeoNamesProvider()

    cities = geonames_provider.get_cities_info(geoname_ids)

    all_ids = set([c.geoname_id for c in cities] + [c.country_geoname_id for c in cities])

    locales = dict()
    for language_code in INDEX_LANGUAGE_SET:
        names = geonames_provider.get_names_for_language(all_ids, language_code)
        locale = dict()
        for city_info in cities:
            city_name = names.get(city_info.geoname_id, city_info.name)
            country_name = names.get(city_info.country_geoname_id, city_info.country)

            locale[city_info.geoname_id] = (city_name, country_name)
        locales[language_code] = locale

    return dict(locales=locales, default_locale='en')


def __create_index(maps_path):
    for map_file in [f for f in os.listdir(maps_path) if get_file_ext(os.path.join(maps_path, f)) == 'zip']:
        full_map_file_path = os.path.join(maps_path, map_file)
        meta = __get_map_metadata(full_map_file_path)
        yield MapIndexEntity(
            meta['map_id'],
            meta['geoname_id'],
            map_file,
            os.path.getsize(full_map_file_path),
            meta['timestamp'],
            sorted([transport['type'] for transport in meta['transports']]),
            meta['latitude'],
            meta['longitude']
        )


def __get_map_metadata(map_path):
    with zipfile.ZipFile(map_path, 'r') as zip_file:
        index_json = codecs.decode(zip_file.read('index.json'), 'utf-8)')
        return json.loads(index_json)


