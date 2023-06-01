import ctypes
import sys
import os
import getopt
import time

from engine import settings, ScreenManager, SmartTrader


def execute(broker, i_monitor, i_region):
    sm = ScreenManager.ScreenManager()
    region = sm.get_region(i_monitor=i_monitor, i_region=i_region)

    strader = SmartTrader.SmartTrader(broker=broker, region=region)

    strader.start()

    print(strader.__dict__)
    print('rsi: ' + strader.rsi[0])


def main(argsv):
    broker_id = i_monitor = i_region = None

    os.system('title STrader')

    try:
        opts, args = getopt.getopt(argsv,
                                   'hb:m:r:',
                                   ['help', 'broker=', 'monitor=', 'region='])
    except getopt.GetoptError:
        print('\nException: One or more arguments were not expected.')
        print_help()
        sys.exit(400)

    for opt, arg in opts:
        if opt in ['-h', '--help']:
            print_help()
            sys.exit()
        elif opt in ['-b', '--broker']:
            broker_id = str(arg)
        elif opt in ['-m', '--monitor']:
            i_monitor = int(arg) - 1
        elif opt in ['-r', '--region']:
            i_region = int(arg) - 1

    if broker_id is not None and i_monitor is not None and i_region is not None:

        if broker_id in settings.BROKERS.keys():
            broker = settings.BROKERS[broker_id]
            execute(broker=broker, i_monitor=i_monitor, i_region=i_region)

        else:
            print('\nException: Broker [%s] is not supported yet. '
                  'Please, choose one of these: [%s]' % (broker_id, settings.BROKERS.keys()))

    else:
        print('\nException: One or more arguments are missing.')
        print_help()
        sys.exit(400)


def print_help():
    print('\nUsage examples:')
    print('  . python.exe %s --monitor <monitor_id> --region <region_id>' % os.path.basename(__file__))
    print('  . python.exe %s --monitor 1 --region 3' % os.path.basename(__file__))
    print('  . python.exe %s -m 1 -r 2' % os.path.basename(__file__))


if __name__ == '__main__':
    main(sys.argv[1:])
