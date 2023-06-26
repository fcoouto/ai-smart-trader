import screeninfo


class ScreenManager:
    monitors = []

    def __init__(self, amount_regions_per_monitor=3):
        for monitor in screeninfo.get_monitors():
            monitor = monitor.__dict__
            monitor['regions'] = []

            # Defining regions
            monitor_x = monitor['x']
            monitor_y = monitor['y']

            region_x = monitor_x
            region_y = monitor_y
            region_width = monitor['width'] / amount_regions_per_monitor
            region_height = monitor['height']
            region_center_x = region_x + region_width / 2
            region_center_y = region_y + region_height / 2

            for i in range(0, amount_regions_per_monitor):
                region = {'i': i,
                          'height':  region_height,
                          'width': region_width,
                          'x': region_x,
                          'y': region_y,
                          'center_x': region_center_x,
                          'center_y': region_center_y,
                          0: int(region_x),
                          1: int(region_y),
                          2: int(region_width),
                          3: int(region_height)}
                monitor['regions'].append(region)

                # Preparing for next iteration
                region_x += region_width
                region_center_x = region_x + region_width / 2

            self.monitors.append(monitor)

    def get_monitor(self, i):
        if i < self.monitors.__len__():
            return self.monitors[i]
        else:
            return None

    def get_region(self, i_monitor=0, i_region=0):
        monitor = self.get_monitor(i=i_monitor)
        return monitor['regions'][i_region]

    def regions(self, i_monitor=0):
        return self.monitors[i_monitor]['regions']
