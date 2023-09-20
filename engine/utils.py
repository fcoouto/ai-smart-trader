import os
import re
from datetime import datetime, timezone
from engine import settings


class tmsg:
    header = '\033[95;4m'
    okblue = '\033[94m'
    okcyan = '\033[96m'
    success = '\033[92m'
    warning = '\033[93m'
    danger = '\033[91m'
    endc = '\033[0m'
    bold = '\033[1m'
    italic = '\033[3m'
    underline = '\033[4m'

    context = None

    def print(self, context=None, msg=None, formatting='italic', clear=None, end=None, is_input=False):
        output = None

        if context:
            self.context = context
        elif not context and self.context:
            context = self.context

        if clear:

            if settings.DEBUG_HISTORY is False:
                os.system('cls' if os.name == 'nt' else 'clear')
            print(f"{self.header}{context}{' ' * int(os.get_terminal_size().columns/10)}{self.endc}\n")

        if msg:
            if is_input:
                output = input(f"{getattr(self, formatting)}{msg}{self.endc}")
            else:
                print(f"{getattr(self, formatting)}{msg}{self.endc}", end=end)

        return output

    def input(self, context=None, msg=None, formatting='italic', clear=None, end=None):
        output = self.print(context=context,
                            msg=msg,
                            formatting=formatting,
                            clear=clear,
                            end=end,
                            is_input=True)
        return output


def progress_bar(iterable, prefix='', suffix='', decimals=1, length=20, fill='█', reverse=False, end="\r"):
    """
    Call in a loop to create terminal progress bar
    @params:
        iterable    - Required  : iterable object (Iterable)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
        printEnd    - Optional  : end character (e.g. "\r", "\r\n") (Str)
    """

    # bugfix: "or 1" to make sure we don't get [error division by zero]
    total = len(iterable) or 1

    # Progress Bar Printing Function
    def print_progress_bar(iteration):
        # percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
        filledLength = int(length * iteration // total)
        bar = fill * filledLength + '-' * (length - filledLength)
        padding_left = os.get_terminal_size().columns - length - len(prefix) - len(suffix) - 3

        bar_line = f"\r{' ' * padding_left if padding_left > 0 else ''}{tmsg.italic}{prefix}{tmsg.endc}"
        if prefix:
            bar_line += ' '
        bar_line += f"|{bar}|"

        print(bar_line, end=end)

    # Initial Call
    print_progress_bar(total if reverse else 0)

    # Update Progress Bar
    for i, item in enumerate(iterable):
        yield item

        if reverse:
            print_progress_bar(total - i)
        else:
            print_progress_bar(i + 1)
    # Print New Line on Complete
    print()


def set_terminal_title(title=''):
    if os.getcwd().startswith('/'):
        # Running from Linux
        os.system(f'wmctrl -r :ACTIVE: -T "{title}"')
    elif os.getcwd().startswith('C:\\'):
        # Probably Windows
        os.system(f'title {title}')


def find_nth(string, substring, n):
    i = string.find(substring)

    while i >= 0 and n > 1:
        i = string.find(substring, i + len(substring))
        n -= 1

    return i


def str_to_float(string):
    string = re.sub("[^0-9.]", "", string)

    if string[-1] == '.':
        string = string[:-1]
    if string[-1] == '-':
        string = string[:-1]

    return float(string)


def try_to_delete_file(path):
    try:
        os.remove(path)
    except:
        pass


def does_file_exist(path):
    if os.path.exists(path):
        return True
    return False


def now_utc_tz():
    # Returns [datetime.utcnow] timezone aware
    return datetime.utcnow().replace(tzinfo=timezone.utc)


def now_seconds():
    return float(f'{datetime.utcnow().second}.{datetime.utcnow().microsecond}')


# Technical Analysis
def distance_percent(v1, v2):
    distance = v1 - v2
    distance = distance / v1

    return distance


def distance_percent_abs(v1, v2):
    distance = v1 - v2
    distance = distance / v1

    return abs(distance)


def is_near(v1, v2, threshold):
    distance = distance_percent_abs(v1, v2)

    return distance <= threshold
