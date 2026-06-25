from broadcaster.driver import Driver


class DriverManager:

    def __init__(self):
        self.drivers = {}

    def get_driver(self, car_idx):

        if car_idx not in self.drivers:
            self.drivers[car_idx] = Driver(car_idx)

        return self.drivers[car_idx]