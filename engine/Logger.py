from datetime import datetime
import inspect


class Logger:

    level = 0
    levels = {
        'live': 0,
        'error': 1,
        'warning': 2,
        'info': 3,
        'debug': 4
    }

    def __init__(self, level='live'):
        self.set_level(level)

    def log(self, severity, msg, show_context=False):
        if self.levels[severity.lower()] <= self.level:
            now = datetime.now()

            line = f"{now.strftime('%Y-%m-%d %H:%M:%S')} "
            line += f"[{severity}]\t"

            if show_context:
                context = self.get_context()
            else:
                context = ''

            line += context
            line += str(msg)
            print(line)

    def debug(self, msg, show_context=False):
        severity = 'DEBUG'
        self.log(severity=severity, msg=msg, show_context=show_context)

    def info(self, msg, show_context=False):
        severity = 'INFO'
        self.log(severity=severity, msg=msg, show_context=show_context)

    def warn(self, msg, show_context=False):
        severity = 'WARNING'
        self.log(severity=severity, msg=msg, show_context=show_context)

    def error(self, msg, show_context=True):
        severity = 'ERROR'
        self.log(severity=severity, msg=msg, show_context=show_context)

    def live(self, msg, show_context=False):
        severity = 'LIVE'
        self.log(severity=severity, msg=msg, show_context=show_context)

    def get_context(self):
        class_name = self.__class__.__name__
        caller_name = inspect.stack()[2].function
        return str('%s.%s' % (class_name, caller_name))

    def get_level(self):
        level = self.level

        for [k, v] in self.levels.items():
            if self.level == v:
                level = k

        return level

    def set_level(self, level):
        if level is None or level == '':
            self.live(msg='[log_level] not specified. Going [live] mode.')
            level = 'live'

        if isinstance(level, str):
            self.level = self.levels[level]
        elif isinstance(level, int):
            self.level = level
        else:
            raise Exception('Logger', 'Value [{}] is an unexpected [level].'.format(level))
