import operator
from calendar import timegm
from datetime import datetime
from random import randint, choice

from appdirs import *
from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.properties import NumericProperty, StringProperty, DictProperty
from kivy.storage.jsonstore import JsonStore
from kivy.uix.progressbar import ProgressBar
from kivy.uix.screenmanager import ScreenManager, Screen


class MafMeesRekenenLevel(Screen):
    score = NumericProperty(0)
    o1 = NumericProperty(0)
    o2 = NumericProperty(0)
    op = StringProperty('')
    answer = StringProperty('')
    answered = False
    question_number = NumericProperty(0)
    level_data = DictProperty({'num': 0})

    def __init__(self, **kw):
        super().__init__(**kw)
        self.reset_event = None
        self.level = 0
        self.app = App.get_running_app()
        self.progression = self.app.progression

    def on_enter(self, *args):
        self.level = self.progression['totals']['max_level']
        self.level_data = self.app.level_data(self.level)
        self.question_number = 0
        self.make_question()

    def calculate(self):
        # Copied from http://stackoverflow.com/a/2983144/1357013
        ops = {"+": operator.add,
               "-": operator.sub,
               "x": operator.mul,
               "/": operator.floordiv}
        op_func = ops[self.op]
        return op_func(self.o1, self.o2)

    def get_oper(self, place):
        if place == 'left' or place == 'right':
            min = self.level_data[place + '_min']
            max = self.level_data[place + '_max']
            return randint(min, max)
        elif place == 'oper':
            l = []
            if self.level_data['op_add']:
                l.append('+')
            if self.level_data['op_sub']:
                l.append('-')
            if self.level_data['op_mul']:
                l.append('x')
            if self.level_data['op_div']:
                l.append('/')
            return choice(l)

    def make_question(self, *args):
        # Reset the color of the question text
        self.ids['opgave'].color = [1, 1, 1, 1]
        # Count the number of questions
        self.question_number += 1
        # Get the question
        self.o1 = self.get_oper('left')
        self.o2 = self.get_oper('right')
        self.op = self.get_oper('oper')
        # Remove the previous answer
        self.answer = ''
        # Calculate a known answer
        self.known_answer = self.calculate()
        # TODO we probably want to add some checks to see if we get integers or not, especially when performing random
        #      divisions
        # Reset the progressbar and start it again
        self.ids['progressbar'].value = 100
        self.ids['progressbar'].start_progress(self, self.level_data['time'])
        # Reset the semaphore to keep track if we're already answered this question
        self.answered = False

    def press_num(self, num):
        """A number has been pressed, make sure that's visible."""
        if not self.answered and len(self.answer) < 4:
            self.answer += str(num)

    def press_bs(self):
        """Backspace has been pressed, remove the last character, if allowed."""
        if not self.answered and len(self.answer) > 0:
            self.answer = self.answer[:-1]

    def press_ok(self, *args):
        """Ok has been pressed, calculate result and score and the like."""
        if not self.answered:
            self.ids['progressbar'].stop_progress()
            self.answered = True
            self.store_question()
            if len(self.answer) > 0 and int(self.answer) == self.known_answer:
                self.answer_correct()
            else:
                self.answer_wrong()
            # Go to the end screen if we're done with the questions
            if self.question_number == self.level_data['num']:
                self.measure_success()
            else:
                self.reset_event = Clock.schedule_once(self.make_question, 4)
        else:
            Clock.unschedule(self.reset_event)
            self.make_question()

    def answer_correct(self):
        self.ids['opgave'].color = [0, 1, 0, 1]
        if self.ids['progressbar'].value > (self.level_data['doubler_at'] / self.level_data['time'] * 100):
            self.score += self.level_data['ok_point'] * 2
            self.ids['opgave'].text += "  !!!"
        else:
            self.score += self.level_data['ok_point']

    def answer_wrong(self):
        self.ids['opgave'].color = [1, 0, 0, 1]
        if self.score > 0:
            self.score += self.level_data['fail_point']

    def measure_success(self):
        if self.score >= self.level_data['bronze']:
            self.app.screenmanager.current = 'success'
            # Also make sure we can get to the next level!
            if self.progression['totals']['max_level'] < (self.level + 1):
                self.progression['totals']['max_level'] = self.level + 1
        else:
            self.app.screenmanager.current = 'failure'

    def store_question(self):
        # Copy the object here
        if self.level not in self.progression:
            progression = {}
        else:
            progression = self.progression[self.level]
        if 'questions' not in progression:
            progression['questions'] = []
        # Add the question and result
        d = {}
        d['timestamp'] = timegm(datetime.now().utctimetuple())
        d['o1'] = self.o1
        d['o2'] = self.o2
        d['op'] = self.op
        d['answer_given'] = self.answer
        if self.answer == self.known_answer:
            d['answer_correct'] = True
        else:
            d['answer_correct'] = False
        # The time taken is the percentage of the progressbar that's passed times the allowed max time
        time_taken = (round(((100 - self.ids['progressbar'].value) / 100) * self.level_data['time']), 0)[0]
        d['time_taken'] = time_taken
        progression['questions'].append(d)
        # This seems a bit complex, but is needed to make sure the data is actually stored
        self.progression[self.level] = progression


class AnimProgressBar(ProgressBar):
    def start_progress(self, parent, length):
        Animation.cancel_all(self)
        anim = Animation(value=0, duration=length)
        anim.bind(on_complete=parent.press_ok)
        anim.start(self)

    def stop_progress(self):
        Animation.cancel_all(self)


class MafMeesMenu(Screen):
    level = NumericProperty

    def on_enter(self):
        self.level = App.get_running_app().progression['totals']['max_level']


class MafMeesScreenManager(ScreenManager):
    pass


class SuccessScreen(Screen):
    pass


class FailureScreen(Screen):
    pass

class MafMeesRekenenApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.localdatafile = os.path.join(self.user_data_dir, 'progression.json')
        self.progression = JsonStore(self.localdatafile)
        if len(self.progression) == 0:
            self.progression['totals'] = {'max_level': 0}

    def build(self):
        self.screenmanager = MafMeesScreenManager()
        return self.screenmanager

    def level_data(self, num):
        levels = {
            0: {
                'left_min': 1,  # Minimum for left argument
                'left_max': 9,  # Maximum for left argument
                'right_min': 1,  # Minimum for right argument
                'right_max': 9,  # Maximum for right argument
                'op_add': True,  # Allow addition?
                'op_sub': False,  # Allow substraction?
                'op_mul': False,  # Allow multiplication?
                'op_div': False,  # Allow division?
                'int_only': True,  # Only allow sums that have an integer as result?
                'num': 20,  # Number of questions
                'time': 30,  # Max time per question allowed, in seconds
                'ok_point': 1,  # Point for a correctly answered question
                'fail_point': -1,  # Point for an incorrectly answered question
                'doubler_at': 10,  # If a question is answered within this amount of seconds, points are doubled
                'bronze': 30,  # Number of points required for next level
                'silver': 40,  # Number of points required for well done
                'gold': 55,  # Number of points required for mastery
            },
            1: {
                'left_min': 10,  # Minimum for left argument
                'left_max': 20,  # Maximum for left argument
                'right_min': 1,  # Minimum for right argument
                'right_max': 9,  # Maximum for right argument
                'op_add': True,  # Allow addition?
                'op_sub': False,  # Allow substraction?
                'op_mul': False,  # Allow multiplication?
                'op_div': False,  # Allow division?
                'int_only': True,  # Only allow sums that have an integer as result?
                'num': 30,  # Number of questions
                'time': 30,  # Max time per question allowed, in seconds
                'ok_point': 1,  # Point for a correctly answered question
                'fail_point': -1,  # Point for an incorrectly answered question
                'doubler_at': 10,  # If a question is answered within this amount of seconds, points are doubled
                'bronze': 30,  # Number of points required for next level
                'silver': 40,  # Number of points required for well done
                'gold': 55,  # Number of points required for mastery
            },
            2: {
                'left_min': 20,  # Minimum for left argument
                'left_max': 30,  # Maximum for left argument
                'right_min': 1,  # Minimum for right argument
                'right_max': 9,  # Maximum for right argument
                'op_add': True,  # Allow addition?
                'op_sub': False,  # Allow substraction?
                'op_mul': False,  # Allow multiplication?
                'op_div': False,  # Allow division?
                'int_only': True,  # Only allow sums that have an integer as result?
                'num': 30,  # Number of questions
                'time': 30,  # Max time per question allowed, in seconds
                'ok_point': 1,  # Point for a correctly answered question
                'fail_point': -1,  # Point for an incorrectly answered question
                'doubler_at': 10,  # If a question is answered within this amount of seconds, points are doubled
                'bronze': 30,  # Number of points required for next level
                'silver': 40,  # Number of points required for well done
                'gold': 55,  # Number of points required for mastery
            }
        }

        # Actually return the data
        return levels[num]


if __name__ == '__main__':
    MafMeesRekenenApp().run()
