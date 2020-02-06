import obspython as obs
import re
import threading
from queue import Queue
import socket
import xml.etree.ElementTree as ET
import time

SUCCESSFUL_LOGIN            = "<StageDisplayLoginSuccess />"
SUCCESSFUL_LOGIN_WINDOWS    = "<StageDisplayLoginSuccess>"
INVALID_PASSWORD            = "<Error>Invalid Password</Error>"
COLOR_FILTER_NAME           = "Color filter"

host            = "localhost"
port            = 50002
password        = "password"
connected       = False
autoconnect     = True
thread_running  = False #if a thread for recieving data is running
disconnect      = False #If the thread should disconnect
disconnected    = False 

displayLayouts      = ET
StageDisplayData    = ET

update_time    = 0
slideText      = ""
last_slideText = ""

source_1_name = ""
source_2_name = ""
transparency1 = 100
transparency2 = 0
transition_time = 0.5

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
q = Queue()
thread_lock = threading.Lock()

def connect_button_clicked(props, p):
    global connected
    global thread_running

    if not autoconnect and not thread_running:
        t = threading.Thread(target=connect)
        t.daemon = True
        t.start()
        q.put(0)
        thread_running = True
    elif connected:
        print("Already connected")
    elif thread_running:
       print("Autoconnect running")

def connect(): #run only in thread t
    q.get()
    global autoconnect
    global thread_running
    global disconnect
    global connected
    global password
    global s

    tries = 0

    while (autoconnect or tries < 1) and not disconnect:
        tries += 1
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((host, port))
            loginString = "<StageDisplayLogin>" + password + "</StageDisplayLogin>"
            print("Sending login") # + loginString)
            s.sendall(loginString.encode() + b'\r' + b'\n')

            data = s.recv(4096).decode("utf-8")
            print("Initial response from server: " + data.strip())
            if SUCCESSFUL_LOGIN_WINDOWS in data or SUCCESSFUL_LOGIN in data:
                print("Connected")
                with thread_lock:
                    connected = True
                while connected and not disconnect:
                    recv_and_process_data()
                s.close()
                print("Disconnected")
            elif INVALID_PASSWORD in data:
                print("Login to server failed: Invalid password - Make sure the password matches the one set in Propresenter")
            else:
                print("Login to server failed: Unknown response - Make sure you're connecting to Propresenter StageDisplay server")

        except Exception as E:
            print("Couldn't connect to server: " + str(E))
            s.close()
            time.sleep(1)
        
        with thread_lock:
            connected = False
        
    with thread_lock:
        thread_running = False

def reset_pullParser():
    global pullParser
    global first
    pullParser = None
    pullParser = ET.XMLPullParser(["start", "end"])
    first = True

def recv_and_process_data(): #run only in thread t
    global connected
    global pullParser
    global rootElement
    
    try:
        data = s.recv(4096).decode("utf-8")
    except Exception as e:
        data = ""
        if connected:
            print("Disconnected because of error while recieving data from server: " + str(e))
            with thread_lock:
                connected = False
        else:
            print("Connection was shut down")


    for line in data.splitlines(True):
        try:
            parse_and_process(line)

        except ET.ParseError as e:
            reset_pullParser()
            try:
                parse_and_process(line)
            except ET.ParseError as e2:
                print("Error parsing XML data: " + str(e2))
                reset_pullParser()

def parse_and_process(line):
    global first
    global pullParser
    global rootElement
    
    pullParser.feed(line)
    for event, element in pullParser.read_events():
        if first and event == "start":
            rootElement = element
            first = False

        if rootElement == element and event == "end":
            process_xml_data(element)
            reset_pullParser()

def process_xml_data(root):
    global slideText
    global last_slideText

    if root.tag == 'DisplayLayouts':
        with thread_lock:
            displayLayouts = root 
    elif root.tag == 'StageDisplayData':
        for slide in root.findall('**[@identifier="CurrentSlide"]'):
            if slide.text != None:
                tmp_slideText = slide.text.strip()
            else:
                tmp_slideText = ""

            if tmp_slideText != slideText:
                with thread_lock:
                    last_slideText = slideText
                    slideText = tmp_slideText
                    set_sources()

def set_sources(): #run only at loading and in thread t
    global update_time
    global slideText
    global last_slideText
    global source_1_name
    global source_2_name
    global transparency1
    global transparency2

    update_time = time.time()
    transparency2 = transparency1
    transparency1 = 0

    source1 = obs.obs_get_source_by_name(source_1_name)
    source2 = obs.obs_get_source_by_name(source_2_name)
    filter1 = obs.obs_source_get_filter_by_name(source1, COLOR_FILTER_NAME)
    filter2 = obs.obs_source_get_filter_by_name(source2, COLOR_FILTER_NAME)
    source1Settings = obs.obs_data_create()
    source2Settings = obs.obs_data_create()
    filter1Settings = obs.obs_data_create()
    filter2Settings = obs.obs_data_create()

    if source1 is not None:
        obs.obs_data_set_string(source1Settings, "text", slideText)
        if source2 is not None:
            obs.obs_data_set_string(source2Settings, "text", last_slideText)
            obs.obs_data_set_int(filter1Settings, "opacity", transparency1)
            obs.obs_data_set_int(filter2Settings, "opacity", transparency2)
        else:
            obs.obs_data_set_int(filter1Settings, "opacity", 100)
    elif source2 is not None:
        obs.obs_data_set_string(source2Settings, "text", last_slideText)
        obs.obs_data_set_int(filter1Settings, "opacity", 0)
        obs.obs_data_set_int(filter2Settings, "opacity", 100)
    
    obs.obs_source_update(source1, source1Settings)
    obs.obs_source_update(source2, source2Settings)
    obs.obs_source_update(filter1, filter1Settings)
    obs.obs_source_update(filter2, filter2Settings)
    obs.obs_data_release(source1Settings)
    obs.obs_data_release(source2Settings)
    obs.obs_data_release(filter1Settings)
    obs.obs_data_release(filter2Settings)
    obs.obs_source_release(source1)
    obs.obs_source_release(source2)
    obs.obs_source_release(filter1)
    obs.obs_source_release(filter2)
    
def transition():
    global update_time
    global source_1_name
    global source_2_name
    global transparency1
    global transparency2
    global transition_time

    with thread_lock:
        if transparency1 < 100:
            time_since_last_update = time.time() - update_time
            lerp = int(time_since_last_update * 100 / transition_time)

            transparency1 = lerp

            if transparency1 >= 100:
                transparency1 = 100
            
            transparency2 = 100 - lerp
            if transparency2 <= 0:
                transparency2 = 0

            source1 = obs.obs_get_source_by_name(source_1_name)
            source2 = obs.obs_get_source_by_name(source_2_name)
            if source1 is not None and source2 is not None:
                filter1 = obs.obs_source_get_filter_by_name(source1, COLOR_FILTER_NAME)
                filter2 = obs.obs_source_get_filter_by_name(source2, COLOR_FILTER_NAME)
                settings1 = obs.obs_data_create()
                settings2 = obs.obs_data_create()

                obs.obs_data_set_int(settings1, "opacity", transparency1)
                obs.obs_data_set_int(settings2, "opacity", transparency2)
                obs.obs_source_update(filter1, settings1)
                obs.obs_source_update(filter2, settings2)
                
                obs.obs_data_release(settings1)
                obs.obs_data_release(settings2)
                obs.obs_source_release(filter1)
                obs.obs_source_release(filter2)

            obs.obs_source_release(source1)
            obs.obs_source_release(source2)
            
# defines script description
def script_description():
   return '''Connects to Propresenter stage display server, and sets a text source as the current slides text. Make sure to set the right host IP, port and password, in order to connect to Propresenter (Propresnter does't use encryprion at all, so don't use a sensitive password here).

Choose two individual text sources to get a fading transition.

If you don't see your text sources in the lists, try to reload the script.'''

# defines user properties
def script_properties():
    #global props 
    props = obs.obs_properties_create()

    p1 = obs.obs_properties_add_list(props, "source 1", "Text Source", obs.OBS_COMBO_TYPE_LIST, obs.OBS_COMBO_FORMAT_STRING)
    p2 = obs.obs_properties_add_list(props, "source 2", "Text Source", obs.OBS_COMBO_TYPE_LIST, obs.OBS_COMBO_FORMAT_STRING)
    obs.obs_property_list_add_string(p1, "None", "")
    obs.obs_property_list_add_string(p2, "None", "")

    sources = obs.obs_enum_sources()
    if sources is not None:
        for source in sources:
            source_id = obs.obs_source_get_id(source)
            if source_id == "text_gdiplus" or source_id == "text_ft2_source":
                name = obs.obs_source_get_name(source)
                obs.obs_property_list_add_string(p1, name, name)
                obs.obs_property_list_add_string(p2, name, name)
    obs.source_list_release(sources)

    obs.obs_properties_add_float_slider(props, "transition_time", "Transition time (S)", 0.1, 5.0, 0.1)

    obs.obs_properties_add_text(props, "host", "Host ip", obs.OBS_TEXT_DEFAULT)
    obs.obs_properties_add_int(props, "port", "Port", 1, 100000, 1)
    obs.obs_properties_add_text(props, "password", "Password", obs.OBS_TEXT_PASSWORD)
    obs.obs_properties_add_button(props, "connect_button", "Connect to server", connect_button_clicked)
    obs.obs_properties_add_bool(props, "autoconnect", "Automatically try to (re)connect to server")

    return props

# called at startup
def script_load(settings):
    global autoconnect
    global thread_running
    global slideText
    global last_slideText
    global rootElement
    
    #Make the text sources show nothing at startup
    slideText       = ""
    last_slideText  = ""
    set_sources()
    reset_pullParser()
    rootElement = None

    if autoconnect:
        t = threading.Thread(target=connect)
        t.daemon = True
        t.start()
        q.put(0)
        thread_running = True

    obs.timer_add(transition, 25)
    
# called when unloaded
def script_unload():
    global connected
    global thread_running
    global disconnect

    #get the thread to end
    with thread_lock:
        disconnect = True
    
    #wait till the thread has closed
    while thread_running:
    	time.sleep(0.0001)

    obs.timer_remove(transition)

# called when user updatas settings
def script_update(settings):
    global source_1_name
    global source_2_name
    global transition_time
    global host
    global port
    global password
    global autoconnect
    global thread_running

    source_1_name = obs.obs_data_get_string(settings, "source 1")
    create_colorcorrection_filter(source_1_name, COLOR_FILTER_NAME)
    source_2_name = obs.obs_data_get_string(settings, "source 2")
    create_colorcorrection_filter(source_2_name, COLOR_FILTER_NAME)

    transition_time = obs.obs_data_get_double(settings, "transition_time")

    host = obs.obs_data_get_string(settings, "host")
    port = obs.obs_data_get_int(settings, "port")
    password = obs.obs_data_get_string(settings, "password")
    
    tmpAutoconnect = obs.obs_data_get_bool(settings, "autoconnect")
    if not autoconnect and tmpAutoconnect:
        autoconnect = tmpAutoconnect
        if not thread_running:
            t = threading.Thread(target=connect)
            t.daemon = True
            t.start()
            q.put(0)
            thread_running = True
    else:
        autoconnect = tmpAutoconnect

def script_defaults(settings):
    obs.obs_data_set_default_double(settings, "transition_time", 0.5)
    obs.obs_data_set_default_string(settings, "host", "localhost")
    obs.obs_data_set_default_int(settings, "port", 50002)
    obs.obs_data_set_default_string(settings, "password", "password")
    obs.obs_data_set_default_bool(settings, 'autoconnect', True)

def create_colorcorrection_filter(source_name, filter_name):
    source = obs.obs_get_source_by_name(source_name)
    if source is not None:
        filter_ = obs.obs_source_get_filter_by_name(source, filter_name)
        if filter_ is None:
            new_filter = obs.obs_source_create("color_filter", filter_name, None, None)
            obs.obs_source_filter_add(source, new_filter)
            obs.obs_source_release(new_filter)
        obs.obs_source_release(filter_)
    obs.obs_source_release(source)