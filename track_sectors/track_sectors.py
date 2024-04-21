import configparser
import functools
import json
import math
import os
import platform
import shutil
import sys
import time
import threading
import struct
from third_party.playsound import playsound
from collections import OrderedDict
from datetime import datetime
import ac
import acsys

# ctypes library is different for 32 and 64 bits respectively
if platform.architecture()[0] == "64bit":
    dllfolder = "stdlib64"
else:
    dllfolder = "stdlib"
cwd = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(cwd, dllfolder))
os.environ['PATH'] = os.environ['PATH'] + ";."

from third_party.sim_info_ts2 import info


class Config:
    """App configuration. Load config upon initialization."""

    def __init__(self, local_folder):
        """Initialize config parser and load config"""

        # Load config
        self.update_cfg = False

        # Set up config paths
        self.cfg_file_path = local_folder + "config/config.ini"
        self.defaults_file_path = local_folder + "config/config_defaults.ini"

        # Load config file parser
        self.cfg_parser = configparser.ConfigParser()
        self.cfg_parser.read(self.cfg_file_path)

        # Load config defaults file parser
        self.defaults_parser = configparser.ConfigParser(inline_comment_prefixes=";")
        self.defaults_parser.read(self.defaults_file_path)

        # Loop over sections in defaults. If any are missing in cfg, add them.
        for section in self.defaults_parser.sections():
            if not self.cfg_parser.has_section(section):
                self.cfg_parser.add_section(section)

        # Loading values
        self.main_window_scale = float(self.cfg_parser["MAIN_APP"]["main_window_scale"])
        self.main_window_opacity = float(self.cfg_parser["MAIN_APP"]["opacity_level"])
        self.theoretical_best = int(self.cfg_parser["MAIN_APP"]["theoretical_best"])

        self.settings_window_scale = float(self.cfg_parser["SETTINGS_APP"]["settings_window_scale"])
        self.ui_layout = int(self.cfg_parser["MAIN_APP"]["ui_layout"])
        self.new_best_sfx = int(self.cfg_parser["SETTINGS_APP"]["new_best_sfx"])
        self.settings_window_opacity = int(self.cfg_parser["SETTINGS_APP"]["opacity_level"])
        self.max_sector_number = int(self.cfg_parser["SETTINGS_APP"]["max_sector_number"])
        self.next_page_delay = int(self.cfg_parser["SETTINGS_APP"]["next_page_delay"])

    def save(self):
        """Save config file"""
        if self.update_cfg:
            with open(self.cfg_file_path, 'w') as cfg_file:
                self.cfg_parser.write(cfg_file)


class DataDictionary:

    def __init__(self, track_name, track_layout, car_name):
        self.track_name = track_name
        self.car_name = car_name
        self.track_layout = track_layout
        self.data_location = "apps/python/track_sectors/data/"
        self.backup_location = self.data_location + "backups/"
        self.curr_date_time = str(datetime.now().strftime("%d_%m_%Y_%H_%M_%S"))
        self.sector_count = None
        self.dictionary = None
        self.update_flag = False

        self.structure_update_flag = None
        self.time_update_flag = None
        self.track_valid_flag = None
        self.reset_times_flag_config = None

        self.imported_checkpoints = []

        self.load()

    def creation_date(self, path_to_file):
        """
        Try to get the date that a file was created, falling back to when it was
        last modified if that isn't possible.
        """
        if platform.system() == 'Windows':
            return os.path.getctime(self.backup_location + path_to_file)
        else:
            stat = os.stat(self.backup_location + path_to_file)
            try:
                return stat.st_birthtime
            except AttributeError:
                # We're probably on Linux. No easy way to get creation dates here,
                # so we'll settle for when its content was last modified.
                return stat.st_mtime

    def create_backup(self):
        """Stores 10 backups of the config files and periodically deletes the oldest
        file if there are more than 10 backups"""

        shutil.copy(self.data_location + "data.json", self.backup_location + "data_" + self.curr_date_time + ".json")
        backup_files = os.listdir(self.backup_location)
        backup_files = sorted(backup_files, key=self.creation_date)

        if len(backup_files) > 10:
            os.remove(self.backup_location + backup_files[0])

    def load(self):
        """Loads into memory the data, makes a backup of the data and updates the last time the dictionary
        was opened."""

        if os.path.exists(self.data_location + "data.json"):
            self.create_backup()
            self.dictionary = json.load(open(self.data_location + "data.json", 'r'), object_pairs_hook=OrderedDict)
            self.dictionary['date_time'] = self.curr_date_time

        else:
            # special case block if for some reason somebody deletes the data file
            # example wanting to get rid of all their configurations
            self.dictionary = OrderedDict()
            self.dictionary['date_time'] = self.curr_date_time

            # makes a new file to avoid errors
            with open(self.data_location + "data.json", 'w') as x:
                pass

    def display(self):
        return json.dumps(self.dictionary, indent=4)

    def save(self):
        with open(self.data_location + "data.json", "w") as outfile:
            json.dump(self.dictionary, outfile, indent=4)

    def update(self, *args):
        if self.structure_update_flag:
            if self.track_name not in self.dictionary:
                self.dictionary[self.track_name] = OrderedDict()
            try:
                if self.track_layout != "":
                    if self.track_layout in self.dictionary[self.track_name]:
                        del self.dictionary[self.track_name][self.track_layout]
                else:
                    del self.dictionary[self.track_name]
            except KeyError:
                pass

            if self.track_valid_flag:
                # track config changed and is valid, so we add an entry for the track
                if self.track_layout == "":
                    self.dictionary[self.track_name] = OrderedDict({'sector_checkpoints': OrderedDict()})
                    self.dictionary[self.track_name]['sector_count'] = self.sector_count
                else:
                    self.dictionary[self.track_name][self.track_layout] = OrderedDict(
                        {'sector_checkpoints': OrderedDict()})
                    self.dictionary[self.track_name][self.track_layout]['sector_count'] = self.sector_count

                # add track entry in config
                if self.track_layout == "":
                    for i in range(0, self.sector_count):
                        self.dictionary[self.track_name]["sector_checkpoints"][
                            "sector_" + str(i + 1)] = self.imported_checkpoints[i]
                else:
                    for i in range(0, self.sector_count):
                        self.dictionary[self.track_name][self.track_layout]["sector_checkpoints"][
                            "sector_" + str(i + 1)] = self.imported_checkpoints[i]

                # add car entry in config only if at least 1 sector has been cleared
                if self.time_update_flag:
                    if self.track_layout == "":
                        self.dictionary[self.track_name][self.car_name] = OrderedDict()
                        for i in range(0, self.sector_count):
                            self.dictionary[self.track_name][self.car_name][
                                "sector_" + str(i + 1)] = get_time("best", i, True)
                    else:
                        self.dictionary[self.track_name][self.track_layout][self.car_name] = OrderedDict()
                        for i in range(0, self.sector_count):
                            self.dictionary[self.track_name][self.track_layout][self.car_name][
                                "sector_" + str(i + 1)] = get_time("best", i, True)
            else:
                # track config changed, but is not valid, so there is nothing to add
                pass

            # deletes leftover track name key in case there are no more stored
            # configs for any layouts of said track
            try:
                if not self.dictionary[self.track_name]:
                    del self.dictionary[self.track_name]
            except:
                pass

        elif self.time_update_flag:
            # track configuration didn't change, therefore change only the car time's
            if self.track_layout == "":
                if self.car_name not in self.dictionary[self.track_name]:
                    self.dictionary[self.track_name][self.car_name] = OrderedDict()

                for i in range(0, self.sector_count):
                    self.dictionary[self.track_name][self.car_name][
                        "sector_" + str(i + 1)] = get_time("best", i, True)
            else:
                if self.car_name not in self.dictionary[self.track_name][self.track_layout]:
                    self.dictionary[self.track_name][self.track_layout][self.car_name] = OrderedDict()

                for i in range(0, self.sector_count):
                    self.dictionary[self.track_name][self.track_layout][self.car_name][
                        "sector_" + str(i + 1)] = get_time("best", i, True)
        elif self.reset_times_flag_config:

            if self.track_layout == "":
                del self.dictionary[self.track_name][self.car_name]
            else:
                del self.dictionary[self.track_name][self.track_layout][self.car_name]


version = 1.42
app_name = "Track Sectors"
local_folder = "apps/python/track_sectors/"
csp_necessarry_ver = 2744
csp_necessarry_ver_string = "2.2"


car_id = 0
track_name = ac.getTrackName(car_id)
track_layout = ac.getTrackConfiguration(car_id)
car_name = ac.getCarName(car_id)

cfg = Config(local_folder)
stored_data = DataDictionary(track_name, track_layout, car_name)

sectors_changed = False
refresh_rate_opacity = 0
sector_count = 2
track_in_config_flag = False
track_layout_in_config_flag = False
car_in_config_flag = False
structure_update_flag = False
reset_times_flag = False
reset_times_flag_config = False
start_timing_flag = False
current_lap = None
old_lap = 0
new_lap_flag = False
initialization_run = False
correct_conditions = False
position_list = []
is_game_loaded = None
session_type = -2
started_in_pits = None
aux_lap_time = 0
old_session_time = 0
ui_layout_change = False
wait_for_loading = False
went_into_replay = False
old_force_feedback = 0
current_force_feedback = 0
session_type_change = False

# check if map has AI lines
track_folder = "content/tracks/" + track_name + "/"
has_ai_line = True
if not os.path.isfile(track_folder + '/ai/fast_lane.ai') and not os.path.isfile(
        track_folder + track_layout + '/ai/fast_lane.ai'):
    has_ai_line = False

if has_ai_line:
    # there exists a configuration
    if track_name in stored_data.dictionary:

        # there exists a configuration for a specific layout
        if track_layout in stored_data.dictionary[track_name]:
            track_in_config_flag = True
            sector_count = stored_data.dictionary[track_name][track_layout]['sector_count']
            track_layout_in_config_flag = True

            # there are registered times of the current car
            if car_name in stored_data.dictionary[track_name][track_layout]:
                car_in_config_flag = True

        # there might be a configuration for track, without layout
        elif "sector_checkpoints" in stored_data.dictionary[track_name]:
            track_in_config_flag = True
            sector_count = stored_data.dictionary[track_name]['sector_count']

            # there are registered times of the current car
            if car_name in stored_data.dictionary[track_name]:
                car_in_config_flag = True


def check_backwards_driving(curr_progress):
    """Checks if the player is driving backwards.
    returns True if driving backwards or stationary,
    returns False if driving forward"""

    global position_list, new_lap_flag

    if new_lap_flag:
        new_lap_flag = False
        position_list.clear()
        position_list.append(0)

    # curr_progress - position_list[0]) <= position_list[0] * 0.30 - clamps down the maximum possible difference

    # curr_progress <= 0.05 and abs(curr_progress - position_list[0]) <= position_list[0] * 0.80 - at very low
    # progression values , a difference of only 30% is too small,it can be overcomed with a fast enough car so that
    # the game engine gives data just at the right time when the newest curr_progress received is more than 130% of
    # the already stored progress, so we increase the clamping to 300%
    if len(position_list) != 0:
        if (curr_progress <= 0.05) or position_list[0] == 0 \
                or abs(curr_progress - position_list[0]) <= position_list[0] * 0.30:
            if curr_progress > position_list[0]:
                # ac.log("# normal forward driving")
                position_list.clear()
                position_list.append(curr_progress)
                return False
            elif curr_progress == position_list[0]:
                # moving backwards, late coord update from the engine
                # or car is stationary
                # ac.log("moving backwards, late coord update from the engine, or car is stationary")
                return True
            elif curr_progress < position_list[0]:
                # classic going backwards
                # ac.log("classic going backwards")
                return True
        else:
            # the difference between positions is too high
            # think of the scenario when crossing the finish
            # line backwards
            # ac.log("big difference")
            return True
    else:
         # block for adding first value to list
        # used when first run or when jumping to pits
        position_list.append(curr_progress)
        return False

def time_to_str(x):
    """Converts time (float) to a string"""

    # minutes
    try:
        if x >= 60:
            y = str(int(x / 60)) + ':'
        else:
            y = '0:'

        # seconds
        if x % 60 >= 10:
            y = y + str(int(x % 60)) + ':'
        else:
            y = y + '0' + str(int(x % 60)) + ':'

        # milliseconds
        x = int(round(x % 1, 3) * 1000)

        if x >= 100:
            y = y + str(x)
        elif 10 <= x < 100:
            y = y + '0' + str(x)
        else:
            y = y + '00' + str(x)

        return y
    except TypeError:
        return "--:--:---"

def str_to_time(string_time, extra_flag=False):
    """Converts a string to time (float)"""
    try:
        b = string_time.split(':')
        y = round(float(float(int(b[0]) * 60) + int(b[1]) + float('0.{}'.format(b[2]))), 3)
        return y
    except ValueError:
        if not extra_flag:
            return string_time
        elif extra_flag:
            return ""

def get_time(time_type, index, extra_flag=False):
    global sector_buttons

    if time_type == "last":
        aux = sector_buttons.last_sectors[index]
    elif time_type == "best":
        aux = sector_buttons.best_sectors[index]
    elif time_type == "delta":
        aux = sector_buttons.delta_sectors[index]

    return str_to_time(ac.getText(aux), extra_flag)

def set_time(time_type, index, time_value):
    global sector_buttons
    if time_type == "last":
        ac.setText(sector_buttons.last_sectors[index], time_to_str(time_value))
    elif time_type == "best":
        ac.setText(sector_buttons.best_sectors[index], time_to_str(time_value))
    elif time_type == "delta":
        if time_value == "worse":
            ac.setText(sector_buttons.delta_sectors[index],
                       "+" + time_to_str(get_time("last", index) - get_time("best", index)))
            ac.setFontColor(sector_buttons.delta_sectors[index], 1, 0, 0, 1)
        if time_value == "better":
            ac.setText(sector_buttons.delta_sectors[index],
                       "-" + time_to_str(get_time("best", index) - get_time("last", index)))
            ac.setFontColor(sector_buttons.delta_sectors[index], 0, 1, 0, 1)

def get_collective_time(*args, length):
    """Gets the total time of the first n "last" type sectors."""

    collective_time = 0
    for i in range(0, length):
        if sector_buttons.sector_cleared[i]:
            collective_time += get_time("last", i)

    return collective_time

def get_theoretical_time(*args):
    """Gets the theoretical best time, calculated from summing
    up all the "best" type sector times."""

    theoretical_time = 0
    for i in range(0, main_app.sector_count):
        theoretical_time += get_time("best", i)

    return theoretical_time

def set_up_times(current_progress, lap_time):
    auto_next_page_thread = threading.Thread(target=auto_next_page)
    new_best_thread = threading.Thread(target=new_best_sfx)
    for i in range(0, len(sector_buttons.sector_checkpoints)):
        # checks if the car has reached the checkpoint of
        # a particular sector on this lap
        condition_1 = current_progress >= sector_buttons.sector_checkpoints[i] and not sector_buttons.sector_cleared[i]
        condition_2 = abs(current_progress - sector_buttons.sector_checkpoints[i]) <= 0.1   # clamping the possible difference
        condition_3 = sector_buttons.sector_checkpoints[i] != 2

        if (condition_1 and condition_2 and condition_3) or condition_1:
            set_time("last", i, lap_time - get_collective_time(length=i))
            sector_buttons.sector_cleared[i] = True
            ac.setFontColor(sector_buttons.last_sectors[i], 1, 1, 1, 1)

            # colors orange the current sector that the player is on
            if i == len(sector_buttons.sector_checkpoints) - 1:
                ac.setFontColor(sector_buttons.last_sectors[0], 1, 0.6, 0, 1)
            else:
                ac.setFontColor(sector_buttons.last_sectors[i + 1], 1, 0.6, 0, 1)

            if get_time("best", i) == "--:--:---":
                set_time("best", i, get_time("last", i))
            else:
                if get_time("best", i) > get_time("last", i):
                    set_time("delta", i, "better")
                    set_time("best", i, get_time("last", i))

                    # updates best theoretical time when a sector has a new best
                    if i == len(sector_buttons.sector_checkpoints):
                        ac.setText(main_app.theoretical_best, time_to_str(get_theoretical_time()))
                    if cfg.new_best_sfx:
                        new_best_thread.start()

                elif get_time("best", i) <= get_time("last", i):
                    set_time("delta", i, "worse")

            if (i + 1) % 5 == 0 or i == len(sector_buttons.sector_checkpoints) - 1:
                auto_next_page_thread.start()
            break

    # Set up total and theoretical times
    all_clear = True
    for i in range(0, len(sector_buttons.sector_checkpoints)):
        if not sector_buttons.sector_cleared[i]:
            all_clear = False

    if all_clear:
        ac.setText(main_app.total_time, time_to_str(get_collective_time(length=len(sector_buttons.sector_checkpoints))))
        ac.setText(main_app.theoretical_best, time_to_str(get_theoretical_time()))

def configure_ui(item, xPos, yPos, xSize=0, ySize=0, fontSize=15, window="main"):
    """Set up values for attributes of ui elements."""

    if window == "main":
        ac.setPosition(item, xPos * cfg.main_window_scale, yPos * cfg.main_window_scale)
        if xSize != 0 and ySize != 0:
            ac.setSize(item, xSize * cfg.main_window_scale, ySize * cfg.main_window_scale)
        ac.setFontSize(item, fontSize * cfg.main_window_scale)

    elif window == "settings":
        ac.setPosition(item, xPos * cfg.settings_window_scale, yPos * cfg.settings_window_scale)
        if xSize != 0 and ySize != 0:
            ac.setSize(item, xSize * cfg.settings_window_scale, ySize * cfg.settings_window_scale)
        ac.setFontSize(item, fontSize * cfg.settings_window_scale)

def get_current_spline_pos(car_id=0):
    """Gets the current spline position of the player in a more useful format.\n
    Possible return values range from [0,1], sensitivity: 9 decimals"""

    return round(ac.getCarState(car_id, acsys.CS.NormalizedSplinePosition), 9)

def is_car_in_pit_area(*args):
    return ac.isCarInPit(car_id) or ac.isCarInPitlane(car_id)

def new_best_sfx():
    playsound(local_folder + "new_best.wav")

def auto_next_page(reset=False):
    """Handles the automatic switching to the next/first page
    when all the sectors on the current page have been cleared"""

    global main_app
    if not reset:
        time.sleep(cfg.next_page_delay)

        if main_app.current_page == int(math.ceil((main_app.sector_count / 5))):
            main_app.current_page = 1
        else:
            main_app.current_page += 1

        # settings the value like this will also trigger
        # the function that manages the page change
    else:
        time.sleep(cfg.next_page_delay)
        main_app.current_page = 1
    ac.setValue(main_app.page_spinner, main_app.current_page)

def warning_flash(ui_element, error_label, reason, window_name="settings"):
    global settings_app
    """Flashes the given ui element with red and white, signaling
    to the user that the button can not be used in that scenario.
    Example: Trying to reset the times outside pits will flash said button using
    this function."""

    if reason == "Pits":
        configure_ui(error_label, 230, 30, 110, 20, 20, window=window_name)
        ac.setText(error_label, "You can't use this button outside the pits!")
    elif reason == "Replay":
        ac.setText(error_label, "The app isn't made to run in replay mode. Thus will work only when not in replay.")
        configure_ui(settings_app.info_label, 50, 30, 110, 20, 20, window=window_name)
    elif reason == "NotConfigured":
        ac.setText(error_label, "Can't reset the times because the sectors for this track are not configured.")
        configure_ui(error_label, 120, 30, 110, 20, 20, window=window_name)

    ac.setVisible(error_label, 1)
    for i in range(0, 3):
        ac.setFontColor(ui_element, 1, 0, 0, 1)
        time.sleep(0.4)
        ac.setFontColor(ui_element, 1, 1, 1, 1)
        time.sleep(0.4)
    ac.setVisible(error_label, 0)

def has_timing_started():
    global started_in_pits, start_timing_flag, current_progress, current_lap, lap_time, old_lap_time, aux_lap_time
    global is_game_loaded, old_session_time, new_lap_flag, old_lap, main_app, sector_buttons, position_list
    global wait_for_loading, current_session_time, current_force_feedback, old_force_feedback, session_type_change

    if not wait_for_loading:
        current_session_time = info.graphics.sessionTimeLeft
    session_type = info.graphics.session

    # Session Reset, the -1 part is because in hotlap session type, in replay the sess time is -1
    if old_session_time // 100 < current_session_time // 100 and info.graphics.sessionTimeLeft != -1:
        if  (old_session_time // 100 > info.graphics.sessionTimeLeft // 100 and abs(old_session_time - info.graphics.sessionTimeLeft) >= 1000 and round(old_force_feedback,5) != round(current_force_feedback,5) and old_force_feedback!= 0 and ac.isAcLive()) or info.graphics.sessionTimeLeft>=old_session_time * 0.01:
            ac.log("Track Sectors - Debug - Session restart/Went to pits")
            is_game_loaded = None
            started_in_pits = None
            start_timing_flag = False
            current_session_time = info.graphics.sessionTimeLeft
            old_session_time = current_session_time
            current_lap = ac.getCarState(0, acsys.CS.LapCount)
            old_lap = current_lap
            sector_buttons.reset_sector_cleared()
            new_lap_flag = True
            main_app.current_page = 1
            auto_next_page_thread = threading.Thread(target=auto_next_page,args=[True])
            auto_next_page_thread.start()
            wait_for_loading = False
            return False

        # the second part of the conditions is for a particular case in practice hotlap where the player goes to pits
        # before crossing the starting line
        elif (round(old_force_feedback,5) != round(current_force_feedback,5) and old_force_feedback!= 0 and ac.isAcLive()) or (ac.isAcLive() and is_car_in_pit_area()):
            wait_for_loading = False
        else:
            wait_for_loading = True
            return False
    else:
        # checks if car was loaded into the memory by assuring that the car position on the 3d space
        # is not (0,0,0) (default position for objects that are still loading)
        car_coordonates = [round(elem, 3) for elem in list(info.graphics.carCoordinates)]
        if is_game_loaded is None and not all(elem == 0 for elem in car_coordonates):
            is_game_loaded = True
            old_session_time = info.graphics.sessionTimeLeft

        if is_game_loaded:
            old_session_time = current_session_time

            if started_in_pits is None:
                started_in_pits = is_car_in_pit_area()
                aux_lap_time = lap_time

            if not start_timing_flag:
                # Practice or Qualifying
                if session_type == 0 or session_type == 1:
                    # Start in pits starting line or hotlap
                    start_timing_flag =  not is_car_in_pit_area() and current_progress <= sector_buttons.sector_checkpoints[0]
                    if start_timing_flag:
                        old_lap = ac.getCarState(0, acsys.CS.LapCount)


                # Race
                elif session_type == 2:
                    start_timing_flag = not is_car_in_pit_area() and lap_time > 0 and current_progress <= sector_buttons.sector_checkpoints[0]
                    if start_timing_flag:
                        old_lap = ac.getCarState(0, acsys.CS.LapCount)

                # Hotlap
                elif session_type == 3:
                    if current_lap == 0 and aux_lap_time >= lap_time and current_progress <= sector_buttons.sector_checkpoints[0]:
                        start_timing_flag = True
                        aux_lap_time = lap_time
                    else:
                        # if player teleports to pits before crossing start line
                        if not started_in_pits and is_car_in_pit_area():
                            started_in_pits = True
                        elif started_in_pits and not is_car_in_pit_area():
                            start_timing_flag = True
                    if start_timing_flag:
                        auto_next_page_thread = threading.Thread(target=auto_next_page, args=[True])
                        auto_next_page_thread.start()
                        old_lap = ac.getCarState(0, acsys.CS.LapCount)

                # not supported session type
                else:
                    start_timing_flag = False
                    hide_show_non_replay_ui(0)
                    ac.setText(main_app.info_label, "Session Type not supported. Supported: Practice, Qualifying, Race and Hotlap")
                    ac.setText(settings_app.info_label, "Session Type not supported. Supported: Practice, Qualifying, Race and Hotlap")
                    configure_ui(main_app.info_label, 100, 30, 110, 20, 20, window="main")
                    configure_ui(settings_app.info_label, 50, 30, 110, 20, 20, window="settings")
                    ac.setVisible(main_app.info_label, 1)
                    ac.setVisible(settings_app.info_label, 1)
                    ac.log("Track Sectors - Debug - Session Type not supported")
                    session_type_change = True

            # Went to pits
            elif is_car_in_pit_area():
                ac.log("Track Sectors - Debug - Went to pits")
                start_timing_flag = False
                sector_buttons.reset_sector_cleared()
                current_lap = ac.getCarState(0, acsys.CS.LapCount)
                old_lap = current_lap
                new_lap_flag = True
                main_app.current_page = 1
                auto_next_page_thread = threading.Thread(target=auto_next_page, args=[True])
                auto_next_page_thread.start()
                return False
            return start_timing_flag
        return False

def hide_show_non_replay_ui(visibility):
    global settings_app, main_app, sector_buttons

    ac.setVisible(settings_app.sector_count_spinner, visibility)
    ac.setVisible(settings_app.sector_count_spinner_label, visibility)

    ac.setVisible(settings_app.reset_checkpoints_btn, visibility)
    ac.setVisible(settings_app.reset_checkpoints_label, visibility)

    ac.setVisible(settings_app.last_sector_as_finish, visibility)
    ac.setVisible(settings_app.last_sector_as_finish_label, visibility)

    ac.setVisible(settings_app.page_spinner, visibility)
    ac.setVisible(settings_app.page_spinner_label, visibility)

    ac.setVisible(settings_app.opacity_spinner, visibility)
    ac.setVisible(settings_app.opacity_spinner_label, visibility)

    ac.setVisible(settings_app.size_spinner, visibility)
    ac.setVisible(settings_app.size_spinner_label, visibility)

    ac.setVisible(settings_app.next_page_delay, visibility)
    ac.setVisible(settings_app.next_page_delay_label, visibility)

    ac.setVisible(settings_app.new_best_checkbox, visibility)
    ac.setVisible(settings_app.new_best_checkbox_label, visibility)

    ac.setVisible(settings_app.start_info, visibility)


    for i in sector_buttons.sector_buttons:
        ac.setVisible(i, visibility)

    if cfg.ui_layout == 1:
        ac.setVisible(main_app.reset_time_btn, visibility)

        ac.setVisible(main_app.ui_layout_btn, visibility)
        ac.setVisible(main_app.ui_layout_btn_label, visibility)

        ac.setVisible(main_app.total_and_theoretical_checkbox, visibility)
        ac.setVisible(main_app.total_and_theoretical_checkbox_label, visibility)

        ac.setVisible(main_app.size_spinner, visibility)
        ac.setVisible(main_app.size_spinner_label, visibility)

        ac.setVisible(main_app.opacity_spinner, visibility)
        ac.setVisible(main_app.opacity_spinner_label, visibility)

        ac.setVisible(main_app.page_spinner, visibility)
        ac.setVisible(main_app.page_spinner_label, visibility)

        ac.setVisible(settings_app.info_label, not visibility)
        ac.setVisible(main_app.info_label, not visibility)
    elif cfg.ui_layout == 2:
        ac.setVisible(main_app.ui_layout_btn, visibility)


        ac.setVisible(settings_app.info_label, not visibility)
        ac.setVisible(main_app.info_label, not visibility)

class SectorButtons:

    def __init__(self):
        self.sector_count = sector_count - 1
        self.sector_buttons = []
        self.sector_checkpoints = []
        self.sector_btn_actions = []
        self.sector_cleared = []
        self.sector_counter_labels = []
        self.last_sectors = []
        self.best_sectors = []
        self.delta_sectors = []
        self.sectors_are_configured = False

    def set_label_invisible(self):
        """Sets all 'last', 'best', 'delta', 'sector_count_labels'
        type labels invisible."""

        # try block is to catch an out of index error
        # when first entering the function that creates
        # the labels
        try:
            for i in range(0, self.sector_count + 1):
                ac.setVisible(self.sector_counter_labels[i], 0)
                ac.setVisible(self.last_sectors[i], 0)
                ac.setVisible(self.best_sectors[i], 0)
                ac.setVisible(self.delta_sectors[i], 0)
        except:
            pass

    def are_all_sectors_cleared(self):
        """Checks if all sectors have been already cleared on this current lap
        \n returns True if all sectors have been cleared
        \n returns False if there is at least one sector that has not been cleared"""

        for i in range(0, len(self.sector_buttons)):
            if not self.sector_cleared[i]:
                return False
        return True

    def set_invisible(self):
        """Sets invisible the sector buttons that appear in the settings app"""

        # try block is to catch an out of index error
        # when first entering the function that creates
        # the buttons
        try:
            for i in range(0, self.sector_count + 1):
                ac.setVisible(self.sector_buttons[i], 0)
        except:
            pass

    def reset_sector_cleared(self, *args):
        """Resets the cleared flag from all the sectors, allowing for them to be
        cleared again on a new lap."""

        self.sector_cleared.clear()
        self.sector_cleared = [False] * (self.sector_count + 1)

    def reset_checkpoints(self, *args):
        #self.sector_checkpoints.clear()
        self.sector_checkpoints = [-1] * (self.sector_count + 1)
        for i in self.sector_buttons:
            ac.setFontColor(i, 1, 1, 1, 1)

    def reset_times(self, *args):
        """Clears from memory the times of all 'last', 'best', 'delta' type sectors."""

        self.last_sectors.clear()
        self.best_sectors.clear()
        self.delta_sectors.clear()

    def check_time_update(self, *args):
        for i in range(0, len(self.best_sectors)):
            aux_string = ac.getText(self.best_sectors[i])
            if aux_string != "--:--:---":
                return True
        return False

    def clear_labels(self):
        self.sector_counter_labels.clear()
        self.last_sectors.clear()
        self.best_sectors.clear()
        self.delta_sectors.clear()

    def clear(self):
        self.sector_buttons.clear()
        self.reset_checkpoints()
        self.sector_btn_actions.clear()
        self.reset_sector_cleared()

    def append(self, x, index ):
        self.sector_buttons.append(x)
        self.sector_cleared[index] = False

    def is_configured(self, shutdown = False):
        """Checks if all sectors have been configured\n
        - returns 1 on success
        - 0 otherwise"""

        if not shutdown:
            for i in range(0, self.sector_count + 1):
                if self.sector_checkpoints[i] == -1:
                    ac.setText(settings_app.start_info, "You must configure all the sectors to start the timing.")
                    ac.setFontColor(settings_app.start_info, 1, 0, 0, 1)
                    return False
                # some sector is not configured

            # finished configuring the sectors but not went to pits first time
            if not self.sectors_are_configured and not is_car_in_pit_area():
                ac.setText(settings_app.start_info, "You must go to pits to start the timing")
                ac.setFontColor(settings_app.start_info, 0, 1, 0, 1)
                return False

            # finished configuring and went to the pits for the first time
            elif not self.sectors_are_configured and is_car_in_pit_area():
                self.sectors_are_configured = True
                ac.setText(settings_app.start_info, "You can go on the track to start the timing.")
                ac.setFontColor(settings_app.start_info, 0, 1, 0, 1)
                return True

            # finished configuring and is outside the pits // normally running
            elif self.sectors_are_configured and not is_car_in_pit_area():
                ac.setText(settings_app.start_info, "You can go on the track to start the timing.")
                ac.setFontColor(settings_app.start_info, 0, 1, 0, 1)
                return True
            elif self.sectors_are_configured and is_car_in_pit_area():
                ac.setText(settings_app.start_info, "You can go on the track to start the timing.")
                ac.setFontColor(settings_app.start_info, 0, 1, 0, 1)
                return True
        else:
            for i in range(0, self.sector_count + 1):
                if self.sector_checkpoints[i] == -1:
                    return False
            return True

    def button_trigger(self, *args, button_id=0):
        global settings_app

        """Handles the effects of pressing a sector button"""

        # operating rules for setting up buttons:
        #   - check that car is not in pit area
        #   - check if the current button has not already been triggered
        #   - check that the previous button has been triggered
        #   - the current sector must be placed further than the previous one

        def wrong_press_func(reason):
            global settings_app


            if reason == "Pits":
                configure_ui(settings_app.info_label, 230, 30, 110, 20, 20, window="settings")
                ac.setText(settings_app.info_label, "You can't use this button inside the pits!")
            elif reason == "AlreadyTriggered":
                configure_ui(settings_app.info_label, 180, 30, 110, 20, 20, window="settings")
                ac.setText(settings_app.info_label, "This sector's checkpoint has already been configured.")
            elif reason == "NotContinous":
                configure_ui(settings_app.info_label, 170, 30, 110, 20, 20, window="settings")
                ac.setText(settings_app.info_label, "The previous sector's checkpoint has not yet been configured.")
            elif reason == "SameLocation":
                configure_ui(settings_app.info_label, 180, 30, 110, 20, 20, window="settings")
                ac.setText(settings_app.info_label, "You must place the current sector further than the previous one.")
            elif reason =="Replay":
                ac.setText(settings_app.info_label, "The app isn't made to run in replay mode. Thus will work only when not in replay.")
                configure_ui(settings_app.info_label, 50, 30, 110, 20, 20, window="settings")


            # Flashing the button color to alert that something is not right
            ac.setVisible(settings_app.info_label, 1)
            for i in range(0, 3):
                ac.setFontColor(self.sector_buttons[button_id], 1, 0, 0, 1)
                time.sleep(0.4)
                ac.setFontColor(self.sector_buttons[button_id], 1, 1, 1, 1)
                time.sleep(0.4)
            ac.setVisible(settings_app.info_label, 0)

            if self.sector_checkpoints[button_id] != -1:
                ac.setFontColor(self.sector_buttons[button_id], 0, 1, 0, 1)
            else:
                ac.setFontColor(self.sector_buttons[button_id], 1, 1, 1, 1)


        if not is_car_in_pit_area() and ac.isAcLive() and info.graphics.status != 1:
            if button_id != 0:
                # set up button checkpoints besides the first one
                if self.sector_checkpoints[button_id] == -1 and self.sector_checkpoints[button_id - 1] != -1:
                    if get_current_spline_pos() > self.sector_checkpoints[button_id - 1]:
                        ac.setFontColor(self.sector_buttons[button_id], 0, 1, 0, 1)
                        self.sector_checkpoints[button_id] = get_current_spline_pos()
                    else:
                        wrong_press = threading.Thread(target=wrong_press_func, args=["SameLocation"])
                        wrong_press.start()
                elif self.sector_checkpoints[button_id - 1] == -1:
                    wrong_press = threading.Thread(target=wrong_press_func, args=["NotContinous"])
                    wrong_press.start()
                elif self.sector_checkpoints[button_id] != -1:
                    wrong_press = threading.Thread(target=wrong_press_func, args=["AlreadyTriggered"])
                    wrong_press.start()

            # set up first button checkpoint
            elif self.sector_checkpoints[button_id] == -1:
                ac.setFontColor(self.sector_buttons[button_id], 0, 1, 0, 1)
                self.sector_checkpoints[button_id] = get_current_spline_pos()
            else:
                wrong_press = threading.Thread(target=wrong_press_func, args=["AlreadyTriggered"])
                wrong_press.start()
        elif info.graphics.status == 1:
            wrong_press = threading.Thread(target=wrong_press_func, args=["Replay"])
            wrong_press.start()
        else:
            wrong_press = threading.Thread(target=wrong_press_func, args=["Pits"])
            wrong_press.start()

class MainApp:

    def __init__(self):
        self.window = ac.newApp(app_name)

    def initialization(self):
        """The point in having a different initialization method besides __init__
        is that the app needs to be loaded into memory before the whole game loads up
        but some functions from the game's python library will output a wrong/invalid
        value if they are accessed before the game fully loads up.

        Example: if you want to get the 3d vector position of the car right after
        the app is loaded into the memory you will always get (0,0,0).
        The workaround is to load in memory the app using __init__
        ,as how it is supposed to be, but then wait until the game is fully loaded
        and then start properly, using this method.
        """

        global sector_count
        self.sector_count = sector_count
        self.current_page = 1
        self.theoretical_best_flag = cfg.theoretical_best

        if has_ai_line and ac.isAcLive() and ac.ext_patchVersionCode() >= csp_necessarry_ver:
            self.build_ui()
            self.create_timing_labels()
            self.size_ui()
            self.page_spinner_changed()
        else:
            self.build_error_ui()

    def build_error_ui(self, *args):
        """In case that one the below conditions is not met, this method will
        display an appropriate message accordingly to the missing condition.\n\n
        - track has AI line\n
        - game is live\n
        - custom shaders patch at least version 1.78\n
        """

        # disables the window border
        ac.drawBorder(self.window, 0)

        # move the assetto corsa icon out of sight
        ac.setIconPosition(self.window, 20000, 20000)
        ac.setSize(self.window, 1000 * cfg.main_window_scale, 300 * cfg.main_window_scale)

        if ac.ext_patchVersionCode() < csp_necessarry_ver:
            self.error_label1 = ac.addLabel(self.window, "This app is not supposed to work without")
            self.error_label2 = ac.addLabel(self.window,
                                            "custom shaders patch. Please download/upgrade to at least")
            self.error_label3 = ac.addLabel(self.window,
                                            "version " + str(csp_necessarry_ver_string) + "for the app to work.")
            self.error_label4 = ac.addLabel(self.window, "")
        elif not has_ai_line:
            self.error_label1 = ac.addLabel(self.window,
                                            "This track has no AI Line, It is most likely that this map is either a freerooam type")
            self.error_label2 = ac.addLabel(self.window,
                                            "map or is a mod map that hasn't had an AI Line implemented yet. If you want")
            self.error_label3 = ac.addLabel(self.window,
                                            "the app to work on this particular map you will need to implement an AI Line")
            self.error_label4 = ac.addLabel(self.window,
                                            "an AI Line, search 'racedepartment ai line helper' to learn how to do it.")
        elif not ac.isAcLive():
            self.error_label1 = ac.addLabel(self.window, "This app is not supposed to work in a replay.")
            self.error_label2 = ac.addLabel(self.window,
                                            "It's intended use is for live gameplay only, this is due to the fact")
            self.error_label3 = ac.addLabel(self.window,
                                            "that the player can randomly 'jump' around the track, therefore")
            self.error_label4 = ac.addLabel(self.window, "the app cant keep track of the progress done by the player.")

        ac.setFontColor(self.error_label1, 1, 0, 0, 1)
        ac.setFontColor(self.error_label2, 1, 0, 0, 1)
        ac.setFontColor(self.error_label3, 1, 0, 0, 1)
        ac.setFontColor(self.error_label4, 1, 0, 0, 1)

        configure_ui(self.error_label1, 40, 60, 100, 30, 25, window="main")
        configure_ui(self.error_label2, 40, 110, 100, 30, 25, window="main")
        configure_ui(self.error_label3, 40, 160, 100, 30, 25, window="main")
        configure_ui(self.error_label4, 40, 210, 100, 30, 25, window="main")

    def size_spinner_changed(self, *args):
        """Handles the change of size for the app window dimensions.
        Updates the config file with the new settings and rebuilds the
        ui with new sizes."""

        value = ac.getValue(self.size_spinner) / 10
        cfg.main_window_scale = value

        # option values must be strings
        cfg.cfg_parser.set('MAIN_APP', 'main_window_scale', str(value))
        cfg.update_cfg = True

        self.size_ui()
        self.page_spinner_changed()

    def page_spinner_changed(self, *args):
        """Handles the change in page number in the settings app by redrawing the UI elements
        that are affected by the page change, specifically, the sector buttons."""
        global sector_buttons

        self.current_page = int(ac.getValue(self.page_spinner))

        sector_buttons.set_label_invisible()

        # try block to easily catch cases where there isn't a full page of labels
        try:
            for i in range((self.current_page - 1) * 5, self.current_page * 5):
                ac.setFontColor(sector_buttons.last_sectors[i], 1, 1, 1, 1)
                if cfg.ui_layout == 1:
                    ac.setVisible(sector_buttons.sector_counter_labels[i], 1)
                    ac.setVisible(sector_buttons.last_sectors[i], 1)
                    ac.setVisible(sector_buttons.best_sectors[i], 1)
                    ac.setVisible(sector_buttons.delta_sectors[i], 1)
                else:
                    ac.setVisible(sector_buttons.last_sectors[i], 1)
                    ac.setVisible(sector_buttons.delta_sectors[i], 1)
        except:
            pass

        found_index = False
        for index, x in enumerate(sector_buttons.sector_cleared):
            if not x:
                found_index = True
                ac.setFontColor(sector_buttons.last_sectors[index], 1, 0.6, 0, 1)
                break
        if not found_index:
            ac.setFontColor(sector_buttons.last_sectors[0], 1, 0.6, 0, 1)

    def opacity_spinner_changed(self, *args):
        """Handles the change in opacity when selecting a new value from the
        opacity spinner element."""

        value = ac.getValue(self.opacity_spinner)
        cfg.main_window_opacity = int(value)

        cfg.cfg_parser.set('MAIN_APP', 'main_window_opacity', str(int(value)))
        cfg.update_cfg = True

    def reset_times(self, *args):
        global reset_times_flag, reset_times_flag_config

        if is_car_in_pit_area() and ac.isAcLive() and sector_buttons.is_configured():
            reset_times_flag = True
            reset_times_flag_config = True
            ac.setText(self.theoretical_best, "--:--:---")
            ac.setText(self.total_time, "--:--:---")
        elif not sector_buttons.is_configured():
            wrong_press = threading.Thread(target=warning_flash,
                                           args=[self.reset_time_btn, self.info_label, "NotConfigured", "main"])
            wrong_press.start()
        else:
            wrong_press = threading.Thread(target=warning_flash,
                                           args=[self.reset_time_btn, self.info_label, "Pits", "main"])
            wrong_press.start()

    def create_timing_labels(self, *args):
        """Creates and configures the labels that show the times on the main app:
         last/best/delta types and renders them accordingly to the current ui layout."""

        global sector_buttons

        sector_buttons.set_label_invisible()
        sector_buttons.clear_labels()

        if cfg.ui_layout == 1:
            x_offset = 80
        else:
            x_offset = -20

        car_times = 0
        for i in range(1, self.sector_count + 1):
            aux_sector = ac.addLabel(self.window, "Sector " + str(i))
            aux_last = ac.addLabel(self.window, "--:--:---")
            aux_delta = ac.addLabel(self.window, "--:--:---")

            # decides how to make the "best sector" label based on if there is data for the care stored in the json file
            if track_in_config_flag:
                if track_layout_in_config_flag:
                        if car_in_config_flag and stored_data.dictionary[track_name][track_layout][car_name]['sector_' + str(i)] != "":
                            aux_time = stored_data.dictionary[track_name][track_layout][car_name]['sector_' + str(i)]
                            aux_best = ac.addLabel(self.window, time_to_str(aux_time))
                            car_times += 1
                        else:
                            aux_best = ac.addLabel(self.window, "--:--:---")
                else:
                    if car_in_config_flag and stored_data.dictionary[track_name][track_layout][car_name]['sector_' + str(i)] != "":
                        aux_time = stored_data.dictionary[track_name][car_name]['sector_' + str(i)]
                        aux_best = ac.addLabel(self.window, time_to_str(aux_time))
                        car_times += 1
                    else:
                        aux_best = ac.addLabel(self.window, "--:--:---")
            else:
                aux_best = ac.addLabel(self.window, "--:--:---")


            if cfg.ui_layout == 1:
                configure_ui(aux_sector, x_offset, 60, 100, 25, window="main")
                configure_ui(aux_last, x_offset, 120, 100, 25, window="main")
                configure_ui(aux_best, x_offset, 180, 100, 25, window="main")
                configure_ui(aux_delta, x_offset, 240, 100, 25, window="main")

                x_offset += 100
                if i % 5 == 0:
                    x_offset = 80
            elif cfg.ui_layout == 2:
                configure_ui(aux_last, x_offset, 20, 100, 35, window="main")
                configure_ui(aux_delta, x_offset, 50, 100, 35, window="main")

                x_offset += 85
                if i % 5 == 0:
                    x_offset = -20

            ac.setFontAlignment(aux_sector, "right")
            ac.setFontAlignment(aux_last, "right")
            ac.setFontAlignment(aux_best, "right")
            ac.setFontAlignment(aux_delta, "right")

            if i == 1:
                ac.setFontColor(aux_last, 1, 0.6, 0, 1)


            sector_buttons.sector_counter_labels.append(aux_sector)
            sector_buttons.last_sectors.append(aux_last)
            sector_buttons.best_sectors.append(aux_best)
            sector_buttons.delta_sectors.append(aux_delta)

        if car_times == self.sector_count:
            ac.setText(self.theoretical_best, time_to_str(get_theoretical_time()))
        sector_buttons.set_label_invisible()



        ac.setValue(self.page_spinner, 1)
        ac.setRange(self.page_spinner, 1, int(math.ceil((self.sector_count / 5))))
        self.page_spinner_changed()

    def theoretical_best_changed(self, *args):
        """Handles the change in values of the checkbox that switches
        the theoretical best and total times on/off."""
        value = args[1]
        self.theoretical_best_flag = value
        cfg.cfg_parser.set('MAIN_APP', 'theoretical_best', str(value))
        cfg.update_cfg = True

        self.size_ui()
        self.page_spinner_changed()

    def exit_btn_func(self, *args):
        ac.setVisible(self.window, False)

    def ui_layout_btn_changed(self, *args):
        global ui_layout_change
        """Handles the change of value in the UI Layout spinner."""


        if cfg.ui_layout == 1:
            cfg.ui_layout = 2
        else:
            cfg.ui_layout = 1
        cfg.cfg_parser.set('MAIN_APP', 'ui_layout', str(int(cfg.ui_layout)))

        cfg.update_cfg = True

        ui_layout_change = True

    def build_ui(self):
        """Doing first time configuration for UI elements of the window."""

        # disables the window border
        ac.drawBorder(self.window, 0)

        # move the assetto corsa icon out of sight
        ac.setIconPosition(self.window, 20000, 20000)

        self.info_label = ac.addLabel(self.window, "")
        ac.setVisible(self.info_label, 0)

        # building the size spinner
        self.size_spinner = ac.addSpinner(self.window, "")
        ac.setValue(self.size_spinner, cfg.main_window_scale * 10)
        ac.setStep(self.size_spinner, 1)
        ac.setRange(self.size_spinner, 8, 40)
        self.size_spinnerFunc = functools.partial(self.size_spinner_changed)
        ac.addOnValueChangeListener(self.size_spinner, self.size_spinnerFunc)
        self.size_spinner_label = ac.addLabel(self.window, "Window Size")

        # building the page spinner
        self.page_spinner = ac.addSpinner(self.window, "")
        ac.setValue(self.page_spinner, 1)
        ac.setStep(self.page_spinner, 1)
        ac.setRange(self.page_spinner, 1, 1)
        self.page_spinnerFunc = functools.partial(self.page_spinner_changed)
        ac.addOnValueChangeListener(self.page_spinner, self.page_spinnerFunc)
        self.page_spinner_label = ac.addLabel(self.window, "Page")

        # building the opacity spinner
        self.opacity_spinner = ac.addSpinner(self.window, "")
        ac.setValue(self.opacity_spinner, cfg.main_window_opacity)
        ac.setStep(self.opacity_spinner, 1)
        ac.setRange(self.opacity_spinner, 0, 100)
        self.opacity_spinnerFunc = functools.partial(self.opacity_spinner_changed)
        ac.addOnValueChangeListener(self.opacity_spinner, self.opacity_spinnerFunc)
        self.opacity_spinner_label = ac.addLabel(self.window, "Opacity Level")

        # building the reset times button
        self.reset_time_btn = ac.addButton(self.window, "Reset Times")
        self.reset_time_btnFunc = functools.partial(self.reset_times)
        ac.addOnClickedListener(self.reset_time_btn, self.reset_time_btnFunc)

        # building the left side labels
        self.sector_label = ac.addLabel(self.window, "Sector")
        self.last_label = ac.addLabel(self.window, "Last")
        self.best_label = ac.addLabel(self.window, "Best")
        self.delta_label = ac.addLabel(self.window, "Delta")

        self.total_and_theoretical_checkbox = ac.addCheckBox(self.window, "")
        self.total_and_theoretical_checkboxFunc = functools.partial(self.theoretical_best_changed)
        ac.addOnCheckBoxChanged(self.total_and_theoretical_checkbox, self.total_and_theoretical_checkboxFunc)
        self.total_and_theoretical_checkbox_label = ac.addLabel(self.window, "Theoretical Best")

        # theoretical bests
        ac.setValue(self.total_and_theoretical_checkbox, cfg.theoretical_best)
        self.total_time_label = ac.addLabel(self.window, "Total Time:")
        self.theoretical_best_label = ac.addLabel(self.window, "Theoretical Best:")
        self.total_time = ac.addLabel(self.window, "--:--:---")
        self.theoretical_best = ac.addLabel(self.window, "--:--:---")

        # exit button
        self.exit_btn = ac.addButton(self.window, "x")
        self.exit_btn_part_func = functools.partial(self.exit_btn_func)
        ac.addOnClickedListener(self.exit_btn, self.exit_btn_part_func)
        ac.setBackgroundColor(self.exit_btn, 1, 0, 0)

        ac.setFontColor(self.total_time, 1, 0.5, 0.9, 1)
        ac.setFontColor(self.theoretical_best, 1, 0.5, 0.9, 1)

        # building the ui layout spinner
        self.ui_layout_btn = ac.addButton(self.window, "Layout")
        self.ui_layout_btnFunc = functools.partial(self.ui_layout_btn_changed)
        ac.addOnClickedListener(self.ui_layout_btn, self.ui_layout_btnFunc)
        self.ui_layout_btn_label = ac.addLabel(self.window, "Change UI")

    def size_ui(self):
        """Method to be called whenever the window size changes, to resize the UI elements
         accordingly or for initialization for the first time to position correctly the
         elements when the program is starting."""

        if cfg.ui_layout == 1:
            # shows the title and resizes the window background
            ac.setSize(self.window, 900 * cfg.main_window_scale, 300 * cfg.main_window_scale)
            ac.setTitle(self.window, app_name)

            configure_ui(self.exit_btn, 2, 2, 25, 25, 15, window="main")

        elif cfg.ui_layout == 2:
            # Hides title and resizes the window background
            ac.setSize(self.window, 455 * cfg.main_window_scale, 90 * cfg.main_window_scale)
            ac.setTitle(self.window, "")
            configure_ui(self.exit_btn, 2, 2, 18, 18, 11, window="main")

        configure_ui(self.info_label, 230, 30, 110, 17, 20, window="main")
        ac.setFontColor(self.info_label, 1,0,0,1)
        configure_ui(self.size_spinner, 730, 160, 150, 20, window="main")
        configure_ui(self.size_spinner_label, 770, 140, 150, 20, 13, window="main")
        configure_ui(self.page_spinner, 730, 260, 150, 20, window="main")
        configure_ui(self.page_spinner_label, 792, 240, 150, 20, 13, window="main")
        configure_ui(self.opacity_spinner, 730, 210, 150, 20, window="main")
        configure_ui(self.opacity_spinner_label, 765, 190, 150, 20, 13, window="main")
        configure_ui(self.reset_time_btn, 100, 15, 150, 20, window="main")
        configure_ui(self.total_and_theoretical_checkbox, 730, 110, 150, 20, window="main")
        configure_ui(self.total_and_theoretical_checkbox_label, 760, 110, 150, 20, 15, window="main")

        # left side labels
        configure_ui(self.sector_label, 30, 60, 10, 20, window="main")
        configure_ui(self.last_label, 30, 120, 10, 20, window="main")
        configure_ui(self.best_label, 30, 180, 10, 20, window="main")
        configure_ui(self.delta_label, 30, 240, 10, 20, window="main")

        # hiding / showing static ui elements depending on the ui layout
        if cfg.ui_layout == 1:
            ac.setVisible(self.total_and_theoretical_checkbox, 1)
            ac.setVisible(self.reset_time_btn, 1)
            ac.setVisible(self.size_spinner, 1)
            ac.setVisible(self.size_spinner_label, 1)
            ac.setVisible(self.opacity_spinner, 1)
            ac.setVisible(self.opacity_spinner_label, 1)
            ac.setVisible(self.page_spinner, 1)
            ac.setVisible(self.page_spinner_label, 1)
            ac.setVisible(self.sector_label, 1)
            ac.setVisible(self.last_label, 1)
            ac.setVisible(self.best_label, 1)
            ac.setVisible(self.delta_label, 1)
            ac.setVisible(self.total_time_label, 1)
            ac.setVisible(self.total_time, 1)
            ac.setVisible(self.theoretical_best, 1)
            ac.setVisible(self.theoretical_best_label, 1)
            ac.setVisible(self.total_and_theoretical_checkbox_label, 1)
            x_offset = 80

            configure_ui(self.total_time_label, 600, 60, 10, 20, window="main")
            configure_ui(self.theoretical_best_label, 600, 180, 10, 20, window="main")

            configure_ui(self.total_time, 600, 120, 10, 20, window="main")
            configure_ui(self.theoretical_best, 600, 240, 10, 20, window="main")

            configure_ui(self.ui_layout_btn, 780, 70, 50, 25, window="main")
            configure_ui(self.ui_layout_btn_label, 775, 50, 150, 20, 13, window="main")
            ac.setVisible(self.ui_layout_btn_label, 1)
            if self.theoretical_best_flag:
                ac.setVisible(self.total_time_label, 1)
                ac.setVisible(self.total_time, 1)
                ac.setVisible(self.theoretical_best, 1)
                ac.setVisible(self.theoretical_best_label, 1)

                configure_ui(self.total_time_label, 600, 60, 10, 20, window="main")
                configure_ui(self.total_time, 620, 120, 10, 20, window="main")
                configure_ui(self.theoretical_best_label, 600, 180, 10, 20, window="main")
                configure_ui(self.theoretical_best, 620, 240, 10, 20, window="main")
            else:
                ac.setVisible(self.total_time_label, 0)
                ac.setVisible(self.total_time, 0)
                ac.setVisible(self.theoretical_best, 0)
                ac.setVisible(self.theoretical_best_label, 0)

        else:  # cfg.ui_layout == 2:
            ac.setVisible(self.total_and_theoretical_checkbox, 0)
            ac.setVisible(self.reset_time_btn, 0)
            ac.setVisible(self.size_spinner, 0)
            ac.setVisible(self.opacity_spinner, 0)
            ac.setVisible(self.page_spinner, 0)
            ac.setVisible(self.sector_label, 0)
            ac.setVisible(self.last_label, 0)
            ac.setVisible(self.best_label, 0)
            ac.setVisible(self.delta_label, 0)
            ac.setVisible(self.page_spinner_label, 0)
            ac.setVisible(self.opacity_spinner_label, 0)
            ac.setVisible(self.size_spinner_label, 0)
            ac.setVisible(self.total_and_theoretical_checkbox_label, 0)
            ac.setVisible(self.ui_layout_btn_label, 0)

            if self.theoretical_best_flag:
                ac.setVisible(self.total_time_label, 0)
                ac.setVisible(self.total_time, 1)
                ac.setVisible(self.theoretical_best, 1)
                ac.setVisible(self.theoretical_best_label, 0)
                configure_ui(self.total_time, 455, 20, 10, 20, window="main")
                configure_ui(self.theoretical_best, 455, 50, 10, 20, window="main")
                ac.setSize(self.window, 530 * cfg.main_window_scale, 90 * cfg.main_window_scale)
                configure_ui(self.ui_layout_btn, 490, 75, 40, 15, 12, window="main")

            else:
                ac.setVisible(self.total_time_label, 0)
                ac.setVisible(self.total_time, 0)
                ac.setVisible(self.theoretical_best, 0)
                ac.setVisible(self.theoretical_best_label, 0)
                ac.setSize(self.window, 455 * cfg.main_window_scale, 90 * cfg.main_window_scale)
                configure_ui(self.ui_layout_btn, 415, 75, 40, 15, 12, window="main")
            x_offset = -20

        for i in range(1, self.sector_count + 1):
            if cfg.ui_layout == 1:
                ac.setVisible(sector_buttons.sector_counter_labels[i - 1], 1)
                configure_ui(sector_buttons.sector_counter_labels[i - 1], x_offset, 60, 100, 25, window="main")
                configure_ui(sector_buttons.last_sectors[i - 1], x_offset, 120, 100, 25, window="main")
                configure_ui(sector_buttons.best_sectors[i - 1], x_offset, 180, 100, 25, window="main")
                configure_ui(sector_buttons.delta_sectors[i - 1], x_offset, 240, 100, 25, window="main")
                ac.setVisible(sector_buttons.best_sectors[i - 1], 1)
                x_offset += 100
                if i % 5 == 0:
                    x_offset = 80
            elif cfg.ui_layout == 2:
                configure_ui(sector_buttons.last_sectors[i - 1], x_offset, 20, 100, 35, window="main")
                configure_ui(sector_buttons.delta_sectors[i - 1], x_offset, 50, 100, 35, window="main")
                ac.setVisible(sector_buttons.sector_counter_labels[i - 1], 0)
                ac.setVisible(sector_buttons.best_sectors[i - 1], 0)
                x_offset += 85
                if i % 5 == 0:
                    x_offset = -20

class SettingsApp:

    def __init__(self):
        self.window = ac.newApp(app_name + " Settings")

    def initialization(self):
        """The point in having a different initialization method besides __init__
        is that the app needs to be loaded into memory before the whole game loads up
        but some functions from the game's python library will output a wrong/invalid
        value if they are accessed before the game fully loads up.

        Example: if you want to get the 3d vector position of the car right after
        the app is loaded into the memory you will always get (0,0,0).
        The workaround is to load in memory the app using __init__
        ,as how it is supposed to be, but then wait until the game is fully loaded
        and then start properly, using this method.
        """

        global sector_count, correct_conditions
        self.sector_count = sector_count
        self.current_page = 1

        if has_ai_line and ac.isAcLive() and ac.ext_patchVersionCode() >= csp_necessarry_ver:
            correct_conditions = True
            self.build_ui()
            self.create_sector_checkpoint_btns()
            self.size_ui()
        else:
            self.build_error_ui()

    def build_error_ui(self, *args):
        """In case that one the below conditions is not met, this method will
        display an appropriate message accordingly to the missing condition.\n\n
        - track has AI line\n
        - game is live\n
        - custom shaders patch at least version 1.78\n
        """

        # disables the window border
        ac.drawBorder(self.window, 0)

        # move the assetto corsa icon out of sight
        ac.setIconPosition(self.window, 20000, 20000)
        ac.setSize(self.window, 1000 * cfg.settings_window_scale, 300 * cfg.settings_window_scale)

        if ac.ext_patchVersionCode() < csp_necessarry_ver:
            self.error_label1 = ac.addLabel(self.window, "This app is not supposed to work without")
            self.error_label2 = ac.addLabel(self.window,
                                            "custom shaders patch. Please download/upgrade to at least")
            self.error_label3 = ac.addLabel(self.window,
                                            "version " + str(csp_necessarry_ver_string) + "for the app to work.")
            self.error_label4 = ac.addLabel(self.window, "")
        elif not has_ai_line:
            self.error_label1 = ac.addLabel(self.window,
                                            "This track has no AI Line, It is most likely that this map is either a freerooam type")
            self.error_label2 = ac.addLabel(self.window,
                                            "map or is a mod map that hasn't had an AI Line implemented yet. If you want")
            self.error_label3 = ac.addLabel(self.window,
                                            "the app to work on this particular map you will need to implement an AI Line")
            self.error_label4 = ac.addLabel(self.window,
                                            "an AI Line, search 'racedepartment ai line helper' to learn how to do it.")
        elif not ac.isAcLive():
            self.error_label1 = ac.addLabel(self.window, "This app is not supposed to work in a replay.")
            self.error_label2 = ac.addLabel(self.window,
                                            "It's intended use is for live gameplay only, this is due to the fact")
            self.error_label3 = ac.addLabel(self.window,
                                            "that the player can randomly 'jump' around the track, therefore")
            self.error_label4 = ac.addLabel(self.window, "the app cant keep track of the progress done by the player.")

        ac.setFontColor(self.error_label1, 1, 0, 0, 1)
        ac.setFontColor(self.error_label2, 1, 0, 0, 1)
        ac.setFontColor(self.error_label3, 1, 0, 0, 1)
        ac.setFontColor(self.error_label4, 1, 0, 0, 1)

        configure_ui(self.error_label1, 40, 60, 100, 30, 25, window="settings")
        configure_ui(self.error_label2, 40, 110, 100, 30, 25, window="settings")
        configure_ui(self.error_label3, 40, 160, 100, 30, 25, window="settings")
        configure_ui(self.error_label4, 40, 210, 100, 30, 25, window="settings")

    def size_spinner_changed(self, *args):
        """Handles the change of size for the app window dimensions.
        Updates the config file with the new settings and rebuilds the
        ui with new sizes."""

        value = ac.getValue(self.size_spinner) / 10
        cfg.settings_window_scale = value

        # option values must be strings
        cfg.cfg_parser.set('SETTINGS_APP', 'settings_window_scale', str(value))
        cfg.update_cfg = True

        self.size_ui()

    def page_spinner_changed(self, *args):
        """Handles the change in page number in the settings app by redrawing the UI elements
        that are affected by the page change, specifically, the sector buttons."""

        self.current_page = int(ac.getValue(self.page_spinner))
        sector_buttons.set_invisible()

        # try block to easily catch cases where there isn't a full page of buttons
        try:
            for i in range((self.current_page - 1) * 10, self.current_page * 10):
                ac.setVisible(sector_buttons.sector_buttons[i], 1)
        except:
            pass

    def sector_count_spinner_changed(self, *args):
        """Updates the sector value when the sector count spinner gets changed
        and sets the sector_changed flag to True resulting in the sector buttons
        being redrawn."""

        global sectors_changed, track_in_config_flag, track_layout_in_config_flag, car_in_config_flag

        if is_car_in_pit_area() and ac.isAcLive():
            self.sector_count = int(ac.getValue(self.sector_count_spinner))
            ac.setText(main_app.theoretical_best, "--:--:---")
            ac.setText(main_app.total_time, "--:--:---")
            ac.setFontColor(self.last_sector_as_finish, 1, 1, 1, 1)
            sectors_changed = True

        else: # youre not in pits
            ac.setValue(self.sector_count_spinner, self.sector_count)
            wrong_press = threading.Thread(target=warning_flash, args=[self.sector_count_spinner_label, self.info_label, "Pits", "settings"])
            wrong_press.start()

    def create_sector_checkpoint_btns(self, *args):
        global sector_buttons, main_app, structure_update_flag


        sector_buttons.set_invisible()
        sector_buttons.sector_count = self.sector_count - 1
        sector_buttons.clear()

        x_offset = 30
        y_mult = 1
        for i in range(1, self.sector_count + 1):
            aux_button = ac.addButton(self.window, "Sector " + str(i))
            configure_ui(aux_button, x_offset, 90 * y_mult, 100, 25, window="settings")
            x_offset += 120

            if i % 5 == 0:
                y_mult += 1
                x_offset = 30
            if i % 10 == 0:
                y_mult = 1

            act = functools.partial(sector_buttons.button_trigger, button_id=i - 1)
            act.__name__ = 'self.button_trigger'
            ac.addOnClickedListener(aux_button, act)

            sector_buttons.sector_btn_actions.append(act)
            sector_buttons.append(aux_button, i - 1)
            if track_in_config_flag:
                if track_layout_in_config_flag:
                    sector_buttons.sector_checkpoints[i - 1] = \
                        stored_data.dictionary[track_name][track_layout]['sector_checkpoints']['sector_' + str(i)]
                    if i == self.sector_count and stored_data.dictionary[track_name][track_layout]['sector_checkpoints']['sector_' + str(i)] == 2:
                        ac.setFontColor(self.last_sector_as_finish, 1, 0, 0, 1)

                else:
                    sector_buttons.sector_checkpoints[i - 1] = stored_data.dictionary[track_name]['sector_checkpoints'][
                        'sector_' + str(i)]
                    if i == self.sector_count and stored_data.dictionary[track_name][track_layout]['sector_checkpoints']['sector_' + str(i)] == 2:
                        ac.setFontColor(self.last_sector_as_finish, 1, 0, 0, 1)

                sector_buttons.sectors_are_configured = True
                ac.setFontColor(sector_buttons.sector_buttons[i - 1], 0, 1, 0, 1)
            else:
                structure_update_flag = True

        # if the last sector is configured as finish line, color the button green
        if sector_buttons.sector_checkpoints[len(sector_buttons.sector_checkpoints) - 1] == 2:
            ac.setFontColor(self.last_sector_as_finish, 0, 1, 0, 1)


        sector_buttons.set_invisible()

        # adjusts the page boundaries and puts you on page 1
        ac.setValue(self.page_spinner, 1)
        ac.setRange(self.page_spinner, 1, int((self.sector_count - 1) / 10) + 1)
        self.page_spinner_changed()

    def opacity_spinner_changed(self, *args):
        """Handles the change in opacity when selecting a new value from the
        opacity spinner element."""

        value = ac.getValue(self.opacity_spinner)
        cfg.settings_window_opacity = int(value)

        cfg.cfg_parser.set('SETTINGS_APP', 'settings_window_opacity', str(int(value)))
        cfg.update_cfg = True

    def new_best_checkbox_changed(self, *args):
        """Handles the change in values of the new best sfx checkbox."""

        # gets the value from checkbox
        value = args[1]
        cfg.new_best_sfx = value
        cfg.cfg_parser.set('SETTINGS_APP', 'new_best_sfx', str(int(value)))

        cfg.update_cfg = True

    def next_page_delay_changed(self, *args):
        """Handles the change in values of the next page delay spinner."""

        value = int(ac.getValue(self.next_page_delay))
        cfg.ui_layout = value
        cfg.cfg_parser.set('SETTINGS_APP', 'next_page_delay', str(int(value)))

        cfg.update_cfg = True

    def reset_checkpoints(self, *args):
        """Resets the checkpoints for all buttons and deletes all times."""

        global sector_buttons, main_app
        global sectors_changed

        if is_car_in_pit_area() and ac.isAcLive():
            sector_buttons.reset_checkpoints()
            sector_buttons.reset_sector_cleared()
            ac.setFontColor(self.last_sector_as_finish, 1, 1, 1, 1)
            sector_buttons.sectors_are_configured = False
            sectors_changed = True
        else: # not in pits
            wrong_press = threading.Thread(target=warning_flash, args=[self.reset_checkpoints_btn, self.info_label, "Pits", "settings"])
            wrong_press.start()

    def last_sector_as_finish_setter(self, *args):

        def warning_flash_local(ui_element, reason):
            if reason == "NotContinous":
                configure_ui(settings_app.info_label, 170, 30, 110, 20, 20, window="settings")
                ac.setText(settings_app.info_label, "The previous sector's checkpoint has not yet been configured.")
            if reason == "AlreadyTriggered":
                configure_ui(settings_app.info_label, 230, 30, 110, 20, 20, window="settings")
                ac.setText(settings_app.info_label, "The last sector is already configured!")


            ac.setVisible(settings_app.info_label, 1)
            for i in range(0, 3):
                ac.setFontColor(ui_element, 1, 0, 0, 1)
                time.sleep(0.4)
                ac.setFontColor(ui_element, 1, 1, 1, 1)
                time.sleep(0.4)
            ac.setVisible(settings_app.info_label, 0)
            if sector_buttons.sector_checkpoints[button_id] == -1:
                ac.setFontColor(self.last_sector_as_finish, 1, 1, 1, 1)
            elif sector_buttons.sector_checkpoints[button_id] == 2:
                ac.setFontColor(self.last_sector_as_finish, 0, 1, 0, 1)

        button_id = self.sector_count - 1
        if ac.isAcLive():
            if sector_buttons.sector_checkpoints[button_id] == -1 and sector_buttons.sector_checkpoints[button_id - 1] != -1:
                ac.setFontColor(sector_buttons.sector_buttons[button_id], 0, 1, 0, 1)
                sector_buttons.sector_checkpoints[button_id] = 2
                ac.setFontColor(self.last_sector_as_finish, 0, 1, 0, 1)
            elif sector_buttons.sector_checkpoints[button_id - 1] == -1:
                wrong_press = threading.Thread(target=warning_flash_local,
                                               args=[self.last_sector_as_finish, "NotContinous"])
                wrong_press.start()
            elif sector_buttons.sector_checkpoints[button_id] != -1:
                wrong_press = threading.Thread(target=warning_flash_local,
                                               args=[self.last_sector_as_finish, "AlreadyTriggered"])
                wrong_press.start()

    def exit_btn_func(self, *args):
        ac.setVisible(self.window, False)

    def build_ui(self):
        """Doing first time configuration for UI elements of the window."""

        # disables the window border
        ac.drawBorder(self.window, 0)

        # move the assetto corsa icon out of sight
        ac.setIconPosition(self.window, 20000, 20000)

        # building the warning info label
        self.info_label = ac.addLabel(self.window, "You can't use this button outside the pits.")
        ac.setFontColor(self.info_label, 1, 0, 0, 1)
        ac.setVisible(self.info_label, 0)
        ac.setFontAlignment(self.info_label, "left")

        # building the start info label
        self.start_info = ac.addLabel(self.window, "You must configure all the sectors to start the timing.")
        ac.setFontColor(self.start_info, 1, 0, 0, 1)
        ac.setFontAlignment(self.start_info, "left")

        # building the size spinner
        self.size_spinner = ac.addSpinner(self.window, "")
        ac.setValue(self.size_spinner, cfg.settings_window_scale * 10)
        ac.setStep(self.size_spinner, 1)
        ac.setRange(self.size_spinner, 8, 40)
        self.size_spinnerFunc = functools.partial(self.size_spinner_changed)
        ac.addOnValueChangeListener(self.size_spinner, self.size_spinnerFunc)
        self.size_spinner_label = ac.addLabel(self.window, "Window Size")

        # building the page spinner
        self.page_spinner = ac.addSpinner(self.window, "")
        ac.setValue(self.page_spinner, 1)
        ac.setStep(self.page_spinner, 1)
        ac.setRange(self.page_spinner, 1, 1)
        self.page_spinnerFunc = functools.partial(self.page_spinner_changed)
        ac.addOnValueChangeListener(self.page_spinner, self.page_spinnerFunc)
        self.page_spinner_label = ac.addLabel(self.window, "Page")

        # building the opacity spinner
        self.opacity_spinner = ac.addSpinner(self.window, "")
        ac.setValue(self.opacity_spinner, cfg.settings_window_opacity)
        ac.setStep(self.opacity_spinner, 1)
        ac.setRange(self.opacity_spinner, 0, 100)
        self.opacity_spinnerFunc = functools.partial(self.opacity_spinner_changed)
        ac.addOnValueChangeListener(self.opacity_spinner, self.opacity_spinnerFunc)
        self.opacity_spinner_label = ac.addLabel(self.window, "Opacity Level")

        # building the sector count spinner
        self.sector_count_spinner = ac.addSpinner(self.window, "")
        ac.setValue(self.sector_count_spinner, self.sector_count)
        ac.setStep(self.sector_count_spinner, 1)
        ac.setRange(self.sector_count_spinner, 2, cfg.max_sector_number)
        self.sector_count_spinnerFunc = functools.partial(self.sector_count_spinner_changed)
        ac.addOnValueChangeListener(self.sector_count_spinner, self.sector_count_spinnerFunc)
        self.sector_count_spinner_label = ac.addLabel(self.window, "Sector Count")

        # building the next page delay spinner
        self.next_page_delay = ac.addSpinner(self.window, "")
        ac.setValue(self.next_page_delay, cfg.next_page_delay)
        ac.setStep(self.next_page_delay, 1)
        ac.setRange(self.next_page_delay, 1, 15)
        self.next_page_delayFunc = functools.partial(self.next_page_delay_changed)
        ac.addOnValueChangeListener(self.next_page_delay, self.next_page_delayFunc)
        self.next_page_delay_label = ac.addLabel(self.window, "Next Page Delay (s)")

        # building the button that resets the checkpoints
        self.reset_checkpoints_btn = ac.addButton(self.window, "Reset")
        self.reset_checkpoints_btnFunc = functools.partial(self.reset_checkpoints)
        ac.addOnClickedListener(self.reset_checkpoints_btn, self.reset_checkpoints_btnFunc)
        self.reset_checkpoints_label = ac.addLabel(self.window, "Sector Checkpoints")

        # building the new best sfx checkbox
        self.new_best_checkbox = ac.addCheckBox(self.window, "")
        ac.setValue(self.new_best_checkbox, cfg.new_best_sfx)
        self.new_best_checkboxFunc = functools.partial(self.new_best_checkbox_changed)
        ac.addOnCheckBoxChanged(self.new_best_checkbox, self.new_best_checkboxFunc)
        self.new_best_checkbox_label = ac.addLabel(self.window, "New best sfx")

        # building the button that sets the last sector at the finish line
        self.last_sector_as_finish = ac.addButton(self.window, "Set")
        self.last_sector_as_finishFunc = functools.partial(self.last_sector_as_finish_setter)
        ac.addOnClickedListener(self.last_sector_as_finish, self.last_sector_as_finishFunc)
        self.last_sector_as_finish_label = ac.addLabel(self.window, "Finish Line as Last Sector")

        # building the exit button
        self.exit_btn = ac.addButton(self.window, "x")
        self.exit_btn_part_func = functools.partial(self.exit_btn_func)
        ac.addOnClickedListener(self.exit_btn, self.exit_btn_part_func)
        ac.setBackgroundColor(self.exit_btn, 1, 0, 0)

    def size_ui(self):
        """Method to be called whenever the window size changes, to resize the UI elements
         accordingly or for initialization for the first time to position correctly the
         elements when the program is starting."""

        ac.setSize(self.window, 800 * cfg.settings_window_scale, 300 * cfg.settings_window_scale)

        configure_ui(self.size_spinner, 620, 160, 150, 20, window="settings")
        configure_ui(self.size_spinner_label, 660, 140, 150, 20, 13, window="settings")
        configure_ui(self.page_spinner, 620, 260, 150, 20, window="settings")
        configure_ui(self.page_spinner_label, 682, 240, 150, 20, 13, window="settings")
        configure_ui(self.sector_count_spinner, 30, 250, 150, 20, window="settings")
        configure_ui(self.sector_count_spinner_label, 70, 230, 150, 20, 13, window="settings")
        configure_ui(self.reset_checkpoints_btn, 250, 250, 110, 23, window="settings")
        configure_ui(self.reset_checkpoints_label, 250, 230, 110, 20, 13, window="settings")
        configure_ui(self.new_best_checkbox, 620, 60, 50, 20, window="settings")
        configure_ui(self.new_best_checkbox_label, 655, 60, 50, 20, 15, window="settings")
        configure_ui(self.opacity_spinner, 620, 210, 150, 20, window="settings")
        configure_ui(self.opacity_spinner_label, 655, 190, 150, 20, 13, window="settings")
        configure_ui(self.next_page_delay, 620, 110, 150, 20, window="settings")
        configure_ui(self.next_page_delay_label, 640, 90, 150, 20, 13, window="settings")
        configure_ui(self.last_sector_as_finish, 420, 250, 140, 23, window="settings")
        configure_ui(self.last_sector_as_finish_label, 420, 230, 110, 20, 13, window="settings")
        configure_ui(self.exit_btn, 2, 2, 25, 25, 15, window="settings")
        configure_ui(self.info_label, 230, 30, 110, 17, 20, window="settings")
        configure_ui(self.start_info, 140, 50, 110, 17, 20, window="settings")

        # adjusts sizes for sector buttons
        x_offset = 30
        y_mult = 1
        for i in range(1, self.sector_count + 1):
            configure_ui(sector_buttons.sector_buttons[i - 1], x_offset, 90 * y_mult, 100, 25, window="settings")
            x_offset += 120

            if i % 5 == 0:
                y_mult += 1
                x_offset = 30
            if i % 10 == 0:
                y_mult = 1

def acMain(ac_version):
    global main_app, settings_app

    main_app = MainApp()
    settings_app = SettingsApp()
    return app_name + " " + str(version)

def acUpdate(deltaT):
    global settings_app, main_app, sector_buttons, cfg, refresh_rate_opacity, current_lap
    global reset_times_flag, old_lap, current_lap, position_list, initialization_run, current_progress
    global track_in_config_flag, track_layout_in_config_flag, car_in_config_flag, correct_conditions, session_type
    global new_lap_flag, lap_time, is_game_loaded, ui_layout_change, old_force_feedback, current_force_feedback
    global current_progress, current_lap, sectors_changed, structure_update_flag, went_into_replay, session_type_change


    if not initialization_run and ac.isConnected(car_id):
        initialization_run = True
        sector_buttons = SectorButtons()
        main_app.initialization()
        settings_app.initialization()


    if initialization_run and correct_conditions:
        current_progress = get_current_spline_pos()
        lap_time = ac.getCarState(0, acsys.CS.LapTime) / 1000
        current_lap = ac.getCarState(0, acsys.CS.LapCount)


        if sectors_changed:
            structure_update_flag = True
            track_in_config_flag = False
            track_layout_in_config_flag = False
            car_in_config_flag = False
            settings_app.create_sector_checkpoint_btns()
            main_app.sector_count = sector_buttons.sector_count + 1
            main_app.create_timing_labels()
            ac.setText(main_app.theoretical_best, "--:--:---")
            ac.setText(main_app.total_time, "--:--:---")
            sectors_changed = False

        if ui_layout_change:
            ui_layout_change = False
            if not sector_buttons.check_time_update():
                main_app.create_timing_labels()
                main_app.size_ui()
                main_app.page_spinner_changed()

            else:
                main_app.size_ui()
                main_app.page_spinner_changed()

        # makes it so the set opacity function does not need to run every game tick
        if refresh_rate_opacity == 60:
            ac.setBackgroundOpacity(settings_app.window, cfg.settings_window_opacity / 100)
            ac.setBackgroundOpacity(main_app.window, cfg.main_window_opacity / 100)

            refresh_rate_opacity = 0
        refresh_rate_opacity += 1

        if reset_times_flag:
            car_in_config_flag = False
            sector_buttons.reset_sector_cleared()
            main_app.create_timing_labels()
            main_app.size_ui()
            main_app.page_spinner_changed()
            reset_times_flag = False


        if ac.isAcLive() and info.graphics.status != 1:
            if went_into_replay:
                hide_show_non_replay_ui(1)
                went_into_replay = False
            current_force_feedback = ac.getCarState(0, acsys.CS.LastFF)
            if sector_buttons.is_configured() and has_timing_started():
                # player exited the pits and is currently on track

                if session_type_change:
                    session_type_change = False
                    ac.setVisible(main_app.info_label, 0)
                    ac.setVisible(settings_app.info_label, 0)


                old_force_feedback = current_force_feedback
                ac.setText(settings_app.start_info, "You can go on the track to start the timing.")
                ac.setFontColor(settings_app.start_info, 0, 1, 0, 1)



                # player is still on the same lap
                if current_lap == old_lap:
                    if not check_backwards_driving(current_progress):
                        set_up_times(current_progress, lap_time)

                # player finished the lap
                elif current_lap != old_lap:
                    # in case last sector is placed very close to the finish line
                    # there is a possibility that the game engine will 'jump' over the
                    # coords of the last sector, this fixes it by checking if all sectors
                    # are cleared in the first tick of the new lap, and calculates the time, if
                    # they are not, also used for the functionality of setting the last sector equal to the finish line
                    # by giving the last sector a progress checkpoint bigger than 1.
                    # last_lap_time - total_time_of_all_other_sectors
                    if not sector_buttons.are_all_sectors_cleared():
                        last_lap_time = ac.getCarState(0, acsys.CS.LastLap) / 1000
                        if sector_buttons.sector_cleared[0]:
                            set_up_times(3, last_lap_time)


                    if current_progress <= sector_buttons.sector_checkpoints[0]:
                        ac.log("Track Sectors - Debug - Finished a lap")
                        old_lap = current_lap
                        sector_buttons.reset_sector_cleared()
                        new_lap_flag = True


        # if the player is in a normal race, but decided to open the replay
        elif info.graphics.status == 1:
            old_force_feedback = current_force_feedback
            went_into_replay = True
            aux_error_string = "The app isn't made to run in replay mode. Thus will work only when not in replay."
            ac.setText(main_app.info_label, aux_error_string)
            ac.setFontColor(main_app.info_label, 1,0,0,1)
            configure_ui(main_app.info_label, 100, 30, 110, 20, 20, window="main")

            ac.setText(settings_app.info_label, aux_error_string)
            ac.setFontColor(settings_app.info_label, 1,0,0,1)
            configure_ui(settings_app.info_label, 50, 30, 110, 20, 20, window="settings")
            hide_show_non_replay_ui(0)

def acShutdown(*args):
    """Run on shutdown of Assetto Corsa"""

    # Update config and stored data, only if necessary
    if correct_conditions:
        cfg.save()

        stored_data.sector_count = sector_buttons.sector_count + 1
        stored_data.time_update_flag = sector_buttons.check_time_update()
        stored_data.structure_update_flag = structure_update_flag
        stored_data.track_valid_flag = sector_buttons.is_configured(shutdown=True)
        stored_data.imported_checkpoints = sector_buttons.sector_checkpoints
        stored_data.reset_times_flag_config = reset_times_flag_config
        stored_data.update()
        stored_data.save()
