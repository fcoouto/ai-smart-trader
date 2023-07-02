import sys
import os
import getopt

from engine import settings, ScreenManager, SmartTrader, utils


def execute(amount_regions_per_monitor,
            i_monitor, i_region, broker, asset, trade_size):

    sm = ScreenManager.ScreenManager(amount_regions_per_monitor=amount_regions_per_monitor)
    region = sm.get_region(i_monitor=i_monitor, i_region=i_region)
    agent_id = str(i_monitor + 1) + str(i_region + 1)

    strader = SmartTrader.SmartTrader(agent_id=agent_id,
                                      region=region,
                                      broker=broker,
                                      asset=asset,
                                      initial_trade_size=trade_size)
    strader.start()


def main(argsv):
    amount_regions_per_monitor = 2
    i_monitor = 1
    i_region = None
    broker = 'iqcent'
    asset = None
    trade_size = 1.00

    utils.set_terminal_title(title='STrader')

    try:
        opts, args = getopt.getopt(argsv,
                                   'hm:r:b:a:t:',
                                   ['help', 'amount_regions_per_monitor=', 'monitor=', 'region=',
                                    'broker=', 'asset=', 'trade_size='])
    except getopt.GetoptError:
        print('\nException: One or more arguments were not expected.')
        print_help()
        sys.exit(400)

    for opt, arg in opts:
        if opt in ['-h', '--help']:
            print_help()
            sys.exit()
        elif opt in ['-m', '--monitor']:
            i_monitor = int(arg) - 1
        elif opt in ['-r', '--region']:
            i_region = int(arg) - 1
        elif opt in ['-b', '--broker']:
            broker_id = str(arg)
        elif opt in ['-a', '--asset']:
            asset = str(arg)
        elif opt in ['-t', '--trade_size']:
            trade_size = float(arg)
        elif opt in ['--amount_regions_per_monitor']:
            amount_regions_per_monitor = int(arg)

    if (i_monitor is not None and
            i_region is not None and
            broker_id is not None and
            asset is not None):

        if broker_id in settings.BROKERS:
            broker = settings.BROKERS[broker_id]
            execute(amount_regions_per_monitor=amount_regions_per_monitor,
                    i_monitor=i_monitor,
                    i_region=i_region,
                    broker=broker,
                    asset=asset,
                    trade_size=trade_size)

        else:
            print('\nException: Broker [%s] is not supported yet. '
                  'Please, choose one of these: [%s]' % (broker_id, settings.BROKERS.keys()))

    else:
        print('\nException: One or more arguments are missing.')
        print_help()
        sys.exit(400)


def print_help():
    print('\nUsage examples:')
    print('  . python.exe %s --monitor <monitor_id> --region <region_id> --amount_regions_per_monitor <amount_regions>'
          '--broker <broker_id> --asset <asset> --trade_size <trade_size>' % os.path.basename(__file__))
    print('  . python.exe %s --monitor 1 --region 3 --amount_regions_per_monitor 3 '
          '--broker iqcent --asset "AUD/JPY OTC" --trade_size 4.40' % os.path.basename(__file__))
    print('  . python.exe %s -m 1 -r 2 -t 5.50' % os.path.basename(__file__))


if __name__ == '__main__':
    main(sys.argv[1:])
