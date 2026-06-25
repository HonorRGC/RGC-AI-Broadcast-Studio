class StoryEngine:

    def update_story(self, driver):

        gained = driver.starting_position - driver.current_position

        if gained >= 10:
            driver.story = "Biggest mover in the field"

        elif gained >= 5:
            driver.story = "Charging through the field"

        elif gained <= -10:
            driver.story = "Having a disastrous race"

        elif gained <= -5:
            driver.story = "Falling backwards"

        else:
            driver.story = "Running consistent laps"