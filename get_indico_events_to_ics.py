# MIT License

# Copyright (c) 2022 University of Bonn

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

#!/usr/bin/env python3

import requests
import json
import os
from datetime import datetime
import pytz
from icalendar import Calendar, Event
from pathlib import Path
import yaml

try:
    from urllib.parse import urlencode
except ImportError:
    from urllib import urlencode

def build_indico_request(path, params, only_public=False):
    items = list(params.items()) if hasattr(params, 'items') else list(params)
    if only_public:
        items.append(('onlypublic', 'yes'))
    if not items:
        return path
    return '%s?%s' % (path, urlencode(items))

def exec_get_request(indico_instance, request_path, api_token=None):
    req_headers = {'Accept': 'application/json', 'Content-Type': 'application/json', 'Authorization': f'Bearer {api_token}'}
    req = requests.get(indico_instance + request_path, headers=req_headers)
    return req

def exec_post_request(indico_instance, request_path, data, api_token=None):
    req_headers = {'Accept': 'application/json', 'Content-Type': 'application/json', 'Authorization': f'Bearer {api_token}'}
    req = requests.post(indico_instance + request_path, headers=req_headers, data=data)
    return req

def get_jresp(req): #Return req converted to json
    try:
      jresp = req.json() #We could also do json.loads(req.content) I am not sure what is more portable
    except:
      print("Error parsing JSON response!")
      os.exit(1)
    return jresp

def get_room_ids(indico_instance, api_token=None): #Get dict of all rooms in indico instance with ids as keys and names as values
    PATH = '/rooms/api/rooms'
    PARAMS = {}
    request_path = build_indico_request(PATH, PARAMS)
    req = exec_get_request(indico_instance, request_path, api_token=API_TOKEN)
    jresp = get_jresp(req)
    room_ids = {room_data['id']:room_data['full_name'] for room_data in jresp}
    return room_ids

def get_bookings(indico_instance, room_id, start_date, end_date, api_token=None):
    data = json.dumps({'room_ids': [room_id]})
    PATH = '/rooms/api/calendar'
    PARAMS = {
        'start_date': start_date,
        'end_date': end_date
    }
    request_path = build_indico_request(PATH, PARAMS)
    req = exec_post_request(indico_instance, request_path, data, api_token=api_token)
    jresp = get_jresp(req)
    return list(jresp[0]['bookings'].values())

def get_date_time_obj(bookings_date_time_str):
    bookings_date_time_str_no_T = bookings_date_time_str.replace("T", " ") #The indico dates have an ugly T in the middle that I don't know how to process
    date_time_obj = datetime.strptime(bookings_date_time_str_no_T, '%Y-%m-%d %H:%M:%S')
    date_time_obj = pytz.utc.localize(date_time_obj) #Make object aware of timezone which we need for icalendar
    return date_time_obj

def get_event(booking):
    event = Event()
    event.add('dtstart', get_date_time_obj(booking['start_dt']))
    event.add('dtend', get_date_time_obj(booking['end_dt']))
    event.add('summary', booking['reservation']['booking_reason'])
    event['organizer'] = booking['reservation']['booked_for_name']
    return event

def get_calendar(bookings):
    calendar = Calendar()
    for booking in bookings:
        list_of_events = range(len(booking)) #expect more than 1 event per room and day
        for index in list_of_events:
            event = get_event(booking[index])
            calendar.add_component(event)
    return calendar

def save_calendar_to_file(calendar, room_id):
    directory = Path.cwd() / 'icalendars'
    f = open(os.path.join(directory, '{}.ics'.format(room_id)), 'wb')
    f.write(calendar.to_ical())
    f.close()

if __name__ == '__main__':
    with open("config.yaml", "r") as stream:
        try:
            config = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(exc)
    INDICO_INSTANCE = config['indico_instance']
    API_TOKEN = config['api_token']
    start_date = config['start_date']
    end_date = config['end_date']
    room_ids = get_room_ids(INDICO_INSTANCE, api_token=API_TOKEN)
    directory = Path.cwd() / 'icalendars'
    directory.mkdir(parents=True, exist_ok=True)
    with open(os.path.join(directory, 'room_id_mappings.txt'), 'w') as f:
        for (room_id,room_name) in sorted(room_ids.items()):
            bookings = get_bookings(INDICO_INSTANCE, room_id, start_date, end_date, api_token=API_TOKEN)
            calendar = get_calendar(bookings)
            save_calendar_to_file(calendar, room_id)
            f.write('{}: {}\n'.format(room_id, room_name))
