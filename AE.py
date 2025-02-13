#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from settings import range_seperator
import requests
import re
from bs4 import BeautifulSoup

  ############################################           
 # Functions for getting record information #
############################################

def get_holdings(base_url, mms_id, api_key):
    """
    Get the holdings id(s) for the bib record via the Alma API.
    """
    holdings_list = []
    query = 'bibs/{}/holdings?apikey={}'
    r = requests.get(''.join([base_url, query.format(mms_id, api_key)]))
    soup = BeautifulSoup(r.text, 'xml')
    holdings = soup.find_all('holding_id')
    for id in holdings:
        holdings_list.append(id.text)

    return holdings_list


def get_item_info(base_url, mms_id, holdings_id, api_key):
    """
    Get the enumeration, chronology, and item id for each item for each holdings
    record.
    """
    limit = 100
    offset = 0
    query = 'bibs/{}/holdings/{}/items?limit={}&offset={}&apikey={}'
    item_ids = []
    descriptions = []
    item_info = []

    r = requests.get(''.join([base_url, query.format(mms_id, holdings_id, limit, offset, api_key)]))
    soup = BeautifulSoup(r.text, 'xml')

    current_response = soup.find_all('item_data')
    items = current_response

    # Iterate through the entire list of items
    while True:
        if len(current_response) == limit:
            offset += limit
            r = requests.get(''.join([base_url, query.format(mms_id, holdings_id, limit, offset, api_key)]))
            soup = BeautifulSoup(r.text, 'xml')
            current_response = soup.find_all('item_data')
            items += current_response
        else:
            break

    for item in items:
        item_ids.append(item.find('pid').text)
        descriptions.append(item.find('description').text)

    # Call get_info_from_description() function to parse the description
    # and return a dictionary with
    for d in descriptions:
        inf = get_info_from_description(d)
        item_info.append(inf)
        #DCP add cross check file
        with open('crosscheck.txt','a', encoding='utf-8') as fh2:
            fh2.write('{}\n'.format(mms_id))
            fh2.write('{}\n'.format(holdings_id))
            fh2.write('{}\n'.format(d))
            fh2.write('{}\n'.format('='*20))
            fh2.write('{}\n\n\n\n'.format(inf))

    # Add the item ID to each item
    for i in range(len(item_ids)):
        item_info[i]['id'] = item_ids[i]

    return item_info


def get_info_from_description(item):
    """
    This is where most of the magic happens. If something goes wrong,
    it probably went wrong here.

    This function parses item descriptions and is called by get_item_info().
    For those descriptions it can parse, it returns a dictionary with each field
    converted to a format compatible with Alma's enumeration and chronology fields.
    """
    splitter_p = re.compile(r'( |\.|,)')
    item_info = {}
    info = splitter_p.split(item)

    # This dictonary of patterns is used convert month and season words to numerals.
    # It's also used to identify descriptions with words that are not
    # month or season indicators.
    date_patterns = {
                     re.compile(r'(Jan\.?|January)', re.IGNORECASE):     '01',
                     re.compile(r'(Feb\.?|February)', re.IGNORECASE):    '02',
                     re.compile(r'(Mar\.?|March)', re.IGNORECASE):       '03',
                     re.compile(r'(Apr\.?|April)', re.IGNORECASE):       '04',
                     re.compile(r'May', re.IGNORECASE):                  '05',
                     re.compile(r'(Jun\.?|June)', re.IGNORECASE):        '06',
                     re.compile(r'(Jul\.?|July)', re.IGNORECASE):        '07',
                     re.compile(r'(Aug\.?|August)', re.IGNORECASE):      '08',
                     re.compile(r'(Sep\.?|Sept\.?|September)', re.IGNORECASE):   '09',
                     re.compile(r'(Oct\.?|October)', re.IGNORECASE):     '10',
                     re.compile(r'(Nov\.?|November)', re.IGNORECASE):    '11',
                     re.compile(r'(Dec\.?|December)', re.IGNORECASE):    '12',
                     re.compile(r'(Spr\.?|Spring)', re.IGNORECASE):      '21',
                     re.compile(r'(Sum\.?|Summer)', re.IGNORECASE):      '22',
                     re.compile(r'(Fal\.?|Fall|Autumn|Aut\.?)', re.IGNORECASE): '23',
                     re.compile(r'(Win\.?|Winter)', re.IGNORECASE):      '24',
                     }

    # This pattern is used to see if a field in info has numerals
    has_digitsp = re.compile(r'.*\d+')

    # This pattern is used to remove periods, parentheses, and commas that can
    # mess things up if they're left in.
    bad_charsp = re.compile(r'[\.\(\),\\:]')

    # This pattern matches hyphens and slashes and is used to recognize and edit
    # date and issue ranges like 1995-1999, 12/13, or 5&6.
    rp = re.compile(r'[-/&]')

    # This pattern matches a field that is a single hyphen, slash, or ampersand.
    r_exp = re.compile(r'^[-/&]$')

    # This pattern is used to catch strings like 2011-Win or 2011/Win.
    year_mop = re.compile(r'((\d+)(-|/|&)([a-zA-Z]+)|([a-zA-Z]+)(-|/|&)(\d+))')

    # This pattern is used to distinguish between years and volume/issue numbers,
    # but it may trip over long continuously numbered issues. The pattern also
    # assumes it won't be handling records from before the 19th century.
    is_yearp = re.compile(r'(18|19|20)\d\d')

    # Used to filter out Alma-generated descriptions. Since they already
    # have enumeration/chronology and have a funky format, we can ignore
    # them for now.
    alma_generatedp = re.compile(r'(.*:)?.*\(.*:.*\)')

    # Mark  descriptions generated by Alma's item prediction functionality
    # as errors.
    if alma_generatedp.match(item):
        item_info = handle_record_error(item, item_info)

    # This is used to collect all fields that appear to be words, but not
    # month or season words.
    to_remove = []
    bad_ends_begins = ('-', '%', '/')

    #DCP
    #detect 3 part pattern pt. 2 v. 1 no. 40-45
    part_vol_nop = re.compile(r'pt\.?\s?\d+\s?\[?v\.\s?\d+\]?\s?no\.?\s?(\d+-?\d+,?\s?)+')
    if part_vol_nop.match(item):
        print('match found')
        print(item)

    # Check each field in info
    for i in info:
        # Scrub '.(),:' from text for better matching
        info[info.index(i)] = bad_charsp.sub('', i)
        i = bad_charsp.sub('', i)
        # Remove leading hyphen
        if i.startswith(bad_ends_begins):
            info[info.index(i)] = i[1:]
            i = i[1:]
        # Remove trailing hypen
        if i.endswith(bad_ends_begins):
            info[info.index(i)] = i[:-1]
            i = i[:-1]
        if i == ' ':
            to_remove.append(i)
    # Remove fields from info that we don't want.
    for i in to_remove:
        info.remove(i)
    # Sometimes, we might encounter a description like 'v 46 July 2005-June 2006',
    # where there is no space surrounding the hyphen (or slash), which produces
    # a field that looks like this '2005-June', which will not process correctly.
    # To deal with this we split the field to look like ('2005', '-', 'June'),
    # drop the original field, and put the three new fields in its place.
    for i in info:
        if year_mop.match(i):
            index = info.index(i)
            head = info[0:index]
            tail = info[(index + 1):]
            body = [x for x in year_mop.match(i).groups()[1:] if x is not None]
            info = head + body + tail

    # Set the defaults for all the fields, so that in case there's nothing
    # to put in them, our CSV columns don't get messed up.
    item_info['enumeration_a'] = ''
    item_info['enumeration_b'] = ''
    item_info['chronology_i'] = ''
    item_info['chronology_j'] = ''
    item_info['chronology_k'] = ''
    item_info['pages'] = ''

    mo_season = []
    years = []
    pages = []
    delete_me = []
    has_chron_k = False
    last_index = len(info) - 1

    # Go through each item in the list
    for i in info:
        # If it's a hyphen, ampersand, or slash, add it to the deletion list.
        if r_exp.match(i):
            delete_me.append(i)

        # If it's not a numeric value, check to see if it's a pagination marker,
        # otherwise, add it to the month/season list. In either case, mark it
        # for deletion.
        elif not has_digitsp.match(i):
            if has_pagination(i):
                pp = snarf_numerals(info[info.index(i) + 1])
                info[info.index(i) + 1] = pp
                pages.append(pp)
                delete_me.append(i)
                delete_me.append(pp)
            else:
                for key in date_patterns:
                    if key.match(i):
                        mo_season.append(i)
                        # Check the item after this one.
                        if last_index > info.index(i):
                            look_ahead = info[info.index(i) + 1]

                            # If it looks like a numeric value and not like a year. Mark it
                            # as a chronology_k (day) value.
                            if has_digitsp.match(look_ahead) and not is_yearp.match(look_ahead):
                                has_chron_k = True
                        break

                delete_me.append(i)

        # If it is a numeric value, sanitize it by running it through
        # snarf_numerals()
        else:
            info[info.index(i)] = snarf_numerals(i)
            i = snarf_numerals(i)

            # If it looks like a year, add it to the years list and the deletion
            # list.
            if is_yearp.match(i) and i not in pages:
                years.append(i)
                delete_me.append(i)

            # Only month values should have leading zeros if anything left in this list
            # has a leading zero, it's probably something like an abbreviated year that
            # has been misidentified as not a year (ie 07 for 2007). Treat it as an
            # error.
            if has_leading_zero(i):
                item_info = handle_record_error(item, item_info)

    # Delete all the values that we've already identified.
    for i in delete_me:
        info.remove(i)

    # Remove duplicates from our year and mo_season lists as duplicates usually
    # show up in circumstances like Win 2015-Win 2016 or June 2015 & July 2015
    # where they are redundant.
    years = remove_duplicates(years)
    mo_season = remove_duplicates(mo_season)

    # Split years values like 1920/2001 and 1950/55. This is important for
    # values like 1950/55 because they will be corrected to 1950/1955.
    years = [i for l in years for i in rp.split(l)]

    if len(years) == 1:
        item_info['chronology_i'] = years[0]
    elif len(years) > 1:
        for i in years[1:]:
            # If we have something like ['1976', '77'], convert it to
            # ['1976', '1977']
            if len(i) == 2:
                years[years.index(i)] = years[years.index(i) - 1][:2] + i

        item_info['chronology_i'] = range_seperator.join(years)

    if len(mo_season) == 1:
        item_info['chronology_j'] = mo_season[0]
    elif len(mo_season) > 1:
        item_info['chronology_j'] = range_seperator.join(mo_season)

    if len(pages) == 1:
        item_info['pages'] = pages[0]
    elif len(pages) > 1:
        item_info['pages'] = range_seperator.join(pages)

    i_len = len(info)

    if i_len > 0:
        item_info['enumeration_a'] = info[0]

        if i_len > 1:
            if has_chron_k and i_len == 2:
                item_info['chronology_k'] = info[1]
            else:
                item_info['enumeration_b'] = info[1]

            if i_len >= 3:
                days_of_month = range(1,32)
                for i in info[2:]:
                    try:
                        if '/' not in i:
                            if int(i) not in days_of_month:
                                item_info = handle_record_error(item, item_info)
                        else:
                            days = i.split('/')
                            for x in days:
                                if int(x) not in days_of_month:
                                    item_info = handle_record_error(item, item_info)
                                    break
                    except ValueError:
                        item_info = handle_record_error(item, item_info)

                if i_len == 3:
                    item_info['chronology_k'] = info[2]

                if i_len > 3:
                    item_info['chronology_k'] = range_seperator.join(info[2:])


    # Make sure we convert the description field's representation of months,
    # Jan, Win, etc. to the appropriate digital representation: 01, 24, etc.
    # Splitting accounts for things formatted like Jan-Feb and Jan/Feb which
    # will be converted to 01/02.
    if item_info['chronology_j'] != '':
        delete_list = []
        mo_split = rp.split(item_info['chronology_j'])
        for i in range(len(mo_split)):
            for key in date_patterns:
                if key.match(mo_split[i]):
                    mo_split[i] = date_patterns[key]
                    break
            if not has_digitsp.match(mo_split[i]):
                delete_list.append(mo_split[i])

        for i in delete_list:
            mo_split.remove(i)

        # Recombine multiple dates
        mo_len = len(mo_split)
        if mo_len > 1:
            item_info['chronology_j'] = range_seperator.join(mo_split)
        # Otherwise, just set chronology_j to the one date
        elif mo_len == 1:
            item_info['chronology_j'] = mo_split[0]

    return item_info

def has_leading_zero(_input):
    return _input[0] == '0'


def has_pagination(_input):
    pagination_p = re.compile(r'^pp', re.IGNORECASE)
    return pagination_p.match(_input)


def handle_record_error(item, item_info):
    print('{} appears to be irregular. Please correct by hand.'.format(item))
    item_info['error'] = item
    return item_info


def snarf_numerals(string):
    """
    This function is called by get_info_from_description(). It takes a string
    of arbitrary characters and returns only those characters that are numerals
    or the range_seperator. All other characters are discarded. Input like 'v.40-41' 
    would be returned as '40/41' if the range_seperator is set to '/'.
    """
    # This pattern matches hyphens and slashes and is used to recognize and edit
    # date and issue ranges like 1995-1999 or 12/13.
    rp = re.compile(r'[-/&]')

    numerals = rp.sub(range_seperator, ''.join([x
                                                for x
                                                in string
                                                if x.isdigit() or rp.match(x) != None]))

    return numerals

def remove_duplicates(l):
    check_list = []
    out_list = [x for x in l if not (x in check_list or check_list.append(x))]

    return out_list


def write_header_to_csv(output_file, item_info, delimeter=','):
    """
    Write out the field headers: id, enumeration_a, etc, to the output file.
    """
    with open(output_file, 'a', encoding='utf-8') as fh:
        try:
            fh.write('{}\n'.format(delimeter.join(item_info[0].keys())))
        except IndexError:
            pass


def output_to_csv(output_file, error_file, item_info, delimeter=','):
    """
    Write each item's info as a row in our output file. Write records with
    errors to our error file.
    """
    item_errors = []
    # Write out the data we were able to extract
    with open(output_file, 'a', encoding='utf-8') as fh:
        for item in item_info:
            # Collect the descriptions we couldn't handle for writing to a 
            # seperate file.
            if 'error' in item:
                item_errors.append(item)
            else:
                fh.write('{}\n'.format(delimeter.join(item.values())))

    # Write out the item id and description for those descriptions that we couldn't handle
    with open(error_file, 'a', encoding='utf-8') as fh:
        for item in item_errors:
            fh.write('Description parsing failure. {}.\n'.format(delimeter.join(item.values())))


def fetch(mms_id, output_file, error_file, api_key, base_url):
    # Get holdings id(s)
    holdings = get_holdings(base_url, mms_id, api_key)

    # Make sure the output file is empty.
    with open(output_file, 'w', encoding='utf-8') as fh:
        fh.truncate()

    # For each holdings ID, write the ID to the output file, get the information
    # for all of the holdings' items, write the field headers to the output file,
    # then write the item information to the output file and write errors to the 
    # error file.
    for h in holdings:
        with open(output_file, 'a', encoding='utf-8') as fh:
            fh.write('{}\n'.format(h))


        item_info = get_item_info(base_url, mms_id, h, api_key)
        write_header_to_csv(output_file, item_info)
        output_to_csv(output_file, error_file, item_info)



  ##################################           
 # Functions for updating records #
##################################

def get_info_from_csv(input_file):
    holdings_p = re.compile(r'^\d{8,19}$')
    header_p = re.compile(r'^[a-z_,]+$')
    # If support for additional range separators is added the
    # new separator character(s) will need to be added to items_p.
    items_p = re.compile(r'^[0-9,/-]+$')
    item_info = {}
    with open(input_file, 'r', encoding='utf-8') as fh:
        lines = fh.readlines()

    """
    The loop below creates a data structure that looks like this:
        {holdings_id_number:
            [ {id: number,
               enumeration_a: number,
               enumeration_b: number,
               chronology_i: number,
               ...
              },
              {id: number,
              ...
              }
            ],
         another_holdings_id_number:
             [ ... ],
        ...
        }
    Usually, this will create a dictionary with one holdings id
    and a list of item dictionaries, but some bibliographic records
    may have more than one holdings.
    """
    for line in lines:
        line = line.strip()
        if holdings_p.match(line):
            holdings_id = line
            item_info[holdings_id] = []
        elif header_p.match(line):
            keys = line.split(',')
        elif items_p.match(line):
            info = line.split(',')
            item_info[holdings_id].append(dict(zip(keys, info)))

    return item_info


def get_item_xml(base_url, mms_id, holdings_id, item_id, api_key):
    query = 'bibs/{}/holdings/{}/items/{}?apikey={}'
    r = requests.get(''.join([base_url, query.format(mms_id, holdings_id, item_id, api_key)]))
    item_xml = r.text

    return item_xml


def update_item_xml(item_xml, item_info, error_file):
    soup = BeautifulSoup(item_xml, 'xml')
    for i in item_info:
        if soup.find(i):
            soup.find(i).string = item_info[i]
        else:
            # We don't need to update the item's ID, but we do want to update
            # all the other fields.
            if i != 'id':
                new_tag = soup.new_tag(i)
                new_tag.string = item_info[i]
                try:
                    soup.find('item_data').find('description').insert_before(new_tag)
                except:
                    with open(error_file, 'a', encoding='utf-8') as fh:
                        fh.write('XML update failure. The XML file for {} did not update properly. Unsuccessful tag: {}. XML at time of failure: {}\n'.format(item_info, str(new_tag), str(soup)))

    new_xml = str(soup)

    return new_xml


def update_item(base_url, mms_id, holdings_id, item_id, api_key, item_xml, error_file):
    headers = {'content-type':'application/xml'}
    query = 'bibs/{}/holdings/{}/items/{}?apikey={}'

    url = ''.join([base_url, query.format(mms_id, holdings_id, item_id, api_key)])
    r = requests.put(url, headers=headers, data=item_xml.encode('utf-8'))
    if r.status_code != 200:
        with open(error_file, 'a', encoding='utf-8') as fh:
            fh.write('XML upload failure. HTTP status: {} -- {}\n'.format(r.status_code, r.text))


def update(mms_id, input_file, error_file, api_key, base_url):
    items_to_update = get_info_from_csv(input_file)

    for holdings in items_to_update:
        for item in items_to_update[holdings]:
            xml = get_item_xml(base_url, mms_id, holdings, item['id'], api_key)
            updated_xml = update_item_xml(xml, item, error_file)
            update_item(base_url, mms_id, holdings, item['id'], api_key, updated_xml, error_file)
