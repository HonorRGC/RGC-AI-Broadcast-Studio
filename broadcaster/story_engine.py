class StoryEngine:
    def update_story(self, driver):
        gained = driver.starting_position - driver.current_position

        if gained >= 10:
            driver.story = "one of the biggest movers in the field"
        elif gained >= 5:
            driver.story = "charging through the field"
        elif gained <= -10:
            driver.story = "trying to recover from a difficult race"
        elif gained <= -5:
            driver.story = "slipping backward from the starting position"
        elif driver.current_position <= 5:
            driver.story = "running inside the top five"
        elif driver.current_position <= 10:
            driver.story = "fighting for a top ten spot"
        else:
            driver.story = "settling into the race rhythm"