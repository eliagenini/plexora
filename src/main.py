__author__ = 'eliagenini'

import logging
import logging.handlers
import pprint
import re
import sys
import time
import urllib.request as urllib
import validators
from command import Command
from model.Channel import Channel
from model.WebGrab import WebGrab


try:
    import config as config
except ImportError:
    print('Can\'t find any config.py!')
    sys.exit(-1)

try:
    import mapping as mapping
except ImportError:
    mapping = {}


pp = pprint.PrettyPrinter(indent=2)

# Define regex to filter single rows
m3u_regex = re.compile(config.config['regex'].get('m3u'))
name_regex = re.compile(config.config['regex'].get('name'))
group_regex = re.compile(config.config['regex'].get('group'))
logo_regex = re.compile(config.config['regex'].get('logo'))
lang_regex = re.compile(config.config['regex'].get('lang'))
country_regex = re.compile(config.config['regex'].get('country'))
id_regex = re.compile(config.config['regex'].get('id'))
number_regex = re.compile(config.config['regex'].get('number'))

# Prevent duplicate
urlCollector = []

playlist = {
    "filename": None,
    "channels": [],
    "timestamp": str(time.time())
}

webgrab = {
    "filename": None,
    "destination": None,
    "days": 0,
    "channels": []
}


def main():
    """

    :return:
    """

    start_log()

    logging.info("Job started")

    # Proxy configuration
    proxy = None
    if config.config["proxy"] is not None:
        if config.config["proxy"].get("active", False) is True:
            if config.config["proxy"].get("hostname") is not None and config.config["proxy"].get("hostname") != "":
                proxy = config.config["proxy"].get("hostname")

                if config.config["proxy"].get("port") is not None and config.config["proxy"].get("port") != "":
                    proxy = proxy + ':' + config.config["proxy"].get("port")

    for provider, data in config.config["providers"].items():

        if data.get('active', False) is True:
            logging.info("Provider  : " + provider)
            logging.info("URL       : " + data['url'])

            try:
                content = load(data['url'])
                process(content, provider, proxy)
            except Exception as e:
                logging.error(str(e))

    logging.info("Loaded " + str(len(urlCollector)) + " channels.")
    logging.info("Loaded " + str(len(webgrab)) + " epg configurations.")

    playlist["filename"] = config.config["playlist"].get("filename")
    write_playlist(playlist)

    # Webgrab configuration
    webgrab["filename"] = str(config.config["epg"].get("filename"))
    webgrab["destination"] = str(config.config["epg"].get("destination"))
    webgrab["days"] = str(config.config["epg"].get("days"))
    write_epg_configuration(webgrab)

    if config.config["epg"].get("execute") is not None and config.config["epg"].get("execute") is True:
        try:
            execute_wg(cmd=str(config.config["epg"].get("path")),
                       filename=str(webgrab["filename"]))
        except Exception as e:
            logging.error(str(e))

    logging.info("Job ended")


def load(url):
    """

    :param url:
    :return: 
    """
    
    request = urllib.Request(url)
    response = urllib.urlopen(request)
    data = response.read().decode('utf-8')

    if not 'EXTM3U' in data:
        raise Exception(url + ' is not a m3u8 file.')

    return data


def process(data, provider, proxy):
    """

    :param data:
    :param provider:
    :return:
    """

    channels = m3u_regex.findall(data)
    filters = config.config["providers"][provider].get("filters", None)

    for info, name, url in channels:
        name = str(name).strip()
        url = str(url).strip()

        logging.debug(" Work on " + name + " (" + url + ")")

        # When name is not properly set on the row, try to get it from tvg-name attribute
        if name is None or name == "":
            name = parse(name_regex, info)

        channel = Channel(
            id=clean_id(name),
            name=name,
            logo=parse(logo_regex, info),
            country=parse(country_regex, info),
            group=parse(group_regex, info),
            lang=parse(lang_regex, info),
            number=parse(number_regex, info)
        )

        if filter(filters, channel):

            # Validate URL
            # valid = validators.url(url) is True
            # logging.debug("     Validate " + str(url) + " : " + str(valid))

            # Prevent duplicate
            # valid = valid and url not in urlCollector
            valid = url not in urlCollector

            if valid:
                channel.url = translate_url(url, proxy)  # let me proxy!

                # Validate logo
                if channel.logo is not None and channel.logo != "":
                    if validators.url(channel.logo) is not True:
                        channel.logo = None

                if channel.id in mapping.channels:
                    c = mapping.channels[channel.id]

                    channel.id = c.get("id") # identifier for epg mapping
                    channel.name = c.get("name") # display name

                    if c.get("number") is not None and c.get("number") != "":
                        channel.number = c.get("number") # order by?

                    if c.get("logo") is not None and c.get("logo") != "":
                        if validators.url(c.get("logo")):
                            channel.logo = c.get("logo") # valid logo when missing

                    site = WebGrab(
                        id=c.get("id"),
                        site=c.get("site"),
                        site_id=c.get("site_id"),
                        name=c.get("name"),
                        same_as=c.get("same_as"),
                        offset=c.get("offset")
                    )

                    logging.info("      Added webgrab mapping " + str(site))

                    # Add channel to webgrab site mapping
                    webgrab["channels"].append(site)
                else:
                    channel.name = clean_name(name)

                logging.info("  Added channel " + str(channel.name))

                # Add channel to playlist and to duplicate prevent list
                playlist["channels"].append(channel)
                urlCollector.append(url)
            else :
                logging.info("      Channel " + name + " already present.")

def parse(regex, data):
    """

    :param regex:
    :param data:
    :return:
    """

    found_string = regex.search(data)
    if found_string:
        return found_string.group(1).strip()

    return None


def filter(filters, channel):
    """

    :param filters:
    :param channel:
    :return:
    """

    # When no filters are configured, just skip them
    if filters is None:
        return True

    logging.debug("     Filters: " + str(filters))

    country = filters.get("country", None)
    if country is not None:
        logging.info("Country isn't none")
        if channel.country is None or str(channel.country).lower() not in country:
            return _exclude(channel, "country")

    group = filters.get("group", None)
    if group is not None:
        logging.debug("         group " + str(channel.group).lower())
        if channel.group is None or str(channel.group).lower() not in group:
            logging.debug("         not in " + repr(group))
            return _exclude(channel, "group")

    lang = filters.get("lang", None)
    if lang is not None:
        if channel.lang is None or str(channel.lang).lower() not in lang:
            return _exclude(channel, "lang")

    number = filters.get("number", None)
    if number is not None:
        if "include" in number:
            if channel.number is not None and channel.number in \
                    [number for number in number["include"]]:
                return _include(channel, "number")
        if "exclude" in number:
            if channel.number is not None and channel.number in \
                    [number for number in number["exclude"]]:
                return _exclude(channel, "number")

    name = filters.get("name", None)
    if name is not None:
        if "include" in name:
            if channel.name is not None and not any(str(n).lower() in str(channel.name).lower() for n in name["include"]):
                return _exclude(channel, "name")

        if "exclude" in name:
            if channel.name is not None and any(str(n).lower() in str(channel.name).lower() for n in name["exclude"]):
                return _exclude(channel, "name")

        return _include(channel, "name")

    return False


def _exclude(channel, reason):
    logging.debug("      " + channel.name + " excluded cause of " + reason +
                 " (value: " + getattr(channel, reason, 'undefined') + ")")
    return False


def _include(channel, reason):
    logging.debug("      " + channel.name + " included cause of " + reason +
                 " (value: " + getattr(channel, reason, 'undefined') + ")")
    return True


def validate_url(url):
    """

    :param url:
    :return:
    """
    if validators.url(url):
        return True

    return False


def translate_url(url, proxy):
    """

    :param url:
    :param proxy:
    :return:
    """
    if proxy is None:
        return url

    dest = url

    if url.startswith('udp'):
        dest = "http://" + str(proxy) + "/udp/" + "".join(url.rsplit("udp://"))
        logging.debug("     => found multicast on " + str(url) + ". Translated to " + dest)
        return
    elif url.startswith('rtp'):
        dest = "http://" + str(proxy) + "/rtp/" + "".join(url.rsplit("rtp://"))
        logging.debug("     => found multicast on " + str(url) + ". Translated to " + dest)

    return dest


def clean_name(name):
    """

    :param name:
    :return:
    """

    bad = config.config["bad"]
    name = name.lower()
    for word in bad:
        name = name.replace(word.lower(), '')

    return name


def clean_id(name):
    """

    :param name:
    :return:
    """

    id = clean_name(name)

    return id.lstrip().rstrip().replace(' ', '-').lower()


def write_playlist(playlist):
    """

    :param playlist:
    :return:
    """

    map = {
        "id": "tvg-id",
        "name": "tvg-name",
        "logo": "tvg-logo",
        "country": "tvg-country",
        "lang": "tvg-language",
        "number": "tvg-chno"
    }

    body = "#EXTM3U\n"
    for channel in playlist['channels']:
        row = "#EXTINF:-1"

        for source, dest in map.items():
            attribute = getattr(channel, source)
            if attribute is not None and attribute != "":
                row += " " + dest + "=\"" + str(attribute).strip() + "\""

        row += ", " + str(channel.name).strip() + "\n"
        row += str(channel.url) + "\n"
        body += row

    write(playlist["filename"], body)


def write_epg_configuration(webgrab):
    """

    :param webgrab:
    :return:
    """

    logging.debug(webgrab["destination"])

    body = "<?xml version=\"1.0\"?>\n"
    body += "<settings>\n"
    body += "\t<filename>" + webgrab["destination"] + "</filename>\n"
    body += "\t<mode></mode>\n"
    body += "\t<postprocess grab=\"y\" run=\"n\">mdb</postprocess>\n"
    body += "\t<user-agent>Mozilla/5.0 (Windows NT 6.1; WOW64; rv:29.0) Gecko/20100101 Firefox/29.0</user-agent>\n"
    body += "\t<logging>on</logging>\n"
    body += "\t<retry time-out=\"5\">2</retry>\n"
    body += "\t<timespan>" + webgrab["days"] + "</timespan>\n"
    body += "\t<update>l</update>\n"

    for channel in webgrab['channels']:
        if channel.same_as is not None:
            body += "\t<channel update=\"i\" same_as=\"" + str(channel.same_as) + "\" offset=\"" + str(channel.offset) \
                    + "\" xmltv_id=\"" + str(channel.id) + "\">" + str(channel.name) + "</channel>\n"
        else:
            body += "\t<channel update=\"i\" site=\"" + str(channel.site) + "\" site_id=\"" + str(channel.site_id) \
                    + "\" xmltv_id=\"" + str(channel.id) + "\">" + str(channel.name) + "</channel>\n"

    body += "</settings>"

    write(webgrab["filename"], body)


def write(filename, data):
    """

    :param filename:
    :param data:
    :return:
    """

    logging.debug("Trying to write " + filename)
    logging.debug("     " + data)

    try:
        with open(filename, 'w') as fd:
            fd.write(data)
    except Exception as e:
        logging.error("Can't write " + filename + " (" + str(e) + ")")
        sys.exit(-1)


def execute_wg(cmd, filename):
    """

    :param filename:
    :return:
    """

    logging.info("Executing Webgrab++")
    logging.debug("     " + cmd + " " + filename)
    cmd = Command(cmd + " " + filename)
    ret = cmd.run(timeout=3)

    logging.debug("     " + str(ret))


def start_log():
    """
    start logging
    """

    conf = config.config["log"]

    logging.basicConfig(
        filename=conf.get("filename", "plexora.log"),
        level=int(conf.get("level",10)),
        format='%(asctime)s - %(name)s: %(levelname)s: %(message)s'
    )

    hand = logging.handlers.RotatingFileHandler(conf.get("filename", "plexora.log"),
                                                maxBytes=conf.get('maxBytes', 100*1024),
                                                backupCount=conf.get('backupCount', 5))

    logger = logging.getLogger('root')
    logger.addHandler(hand)

    return


if __name__ == "__main__":
    main()