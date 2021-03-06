import operator
import time
from datetime import datetime
from random import randint, choice

from appdirs import *
from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.properties import NumericProperty, StringProperty, DictProperty
from kivy.storage.jsonstore import JsonStore
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.progressbar import ProgressBar
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.treeview import TreeView, TreeViewLabel
from kivy.core.window import Window
from kivy.metrics import dp


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

    def on_enter(self, *args):
        self.level = self.app.progression['totals']['max_level']
        self.level_data = self.app.level_data(self.level)
        self.question_number = 0
        self.level_start = time.time()
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
        # Remove the previous answer
        self.answer = ''
        # Get the question
        self.op = self.get_oper('oper')
        # Setting this up for the while loop
        self.known_answer = 0
        while self.known_answer < 1:
            self.o1 = self.get_oper('left')
            self.o2 = self.get_oper('right')
            # Calculate a known answer
            self.known_answer = self.calculate()
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
            if len(self.answer) > 0 and int(self.answer) == self.known_answer:
                self.answer_correct()
            else:
                self.answer_wrong()
            # Store the question
            self.store_question()
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
        if len(self.answer) == 0:
            self.answer = '0'
        self.ids['opgave'].color = [1, 0, 0, 1]
        if self.score > 0:
            self.score += self.level_data['fail_point']

    def measure_success(self):
        self.store_level()
        if self.score >= self.level_data['bronze']:
            self.app.screenmanager.current = 'success'
            # Also make sure we can get to the next level!
            if self.app.progression['totals']['max_level'] < (self.level + 1):
                totals = self.app.progression['totals']
                totals['max_level'] = self.level + 1
                self.app.progression['totals'] = totals
                self.app.chosen_level = self.app.progression['totals']['max_level']
        else:
            self.app.screenmanager.current = 'failure'

    def store_question(self):
        # Copy the object here
        if str(self.level) not in self.app.progression:
            prgr = {}
            self.app.progression[str(self.level)] = {}
        else:
            prgr = self.app.progression[str(self.level)]
        if 'questions' not in prgr:
            prgr['questions'] = {}
        if str(self.level_start) not in prgr['questions']:
            prgr['questions'][str(self.level_start)] = []
        # Add the question and result
        d = {}
        d['timestamp'] = time.time()
        d['level_start'] = self.level_start
        d['o1'] = self.o1
        d['o2'] = self.o2
        d['op'] = self.op
        d['answer_given'] = self.answer
        if int(self.answer) == self.known_answer:
            d['answer_correct'] = True
        else:
            d['answer_correct'] = False
        # The time taken is the percentage of the progressbar that's passed times the allowed max time
        time_taken = (round(((100 - self.ids['progressbar'].value) / 100) * self.level_data['time']), 0)[0]
        d['time_taken'] = time_taken
        prgr['questions'][str(self.level_start)].append(d)
        # This seems a bit complex, but is needed to make sure the data is actually stored
        self.app.progression[str(self.level)]['questions'] = prgr['questions']
        self.app.progression['save'] = {'last': time.time()}

    def store_level(self):
        # Same as store_question, really
        if str(self.level) not in self.app.progression:
            prgr = {}
            self.app.progression[str(self.level)] = {}
        else:
            prgr = self.app.progression[str(self.level)]
        if 'scores' not in prgr:
            prgr['scores'] = []
        # Add the result of this level
        d = {}
        d['timestamp'] = time.time()
        d['level_start'] = self.level_start
        d['score'] = self.score
        if self.score >= self.level_data['bronze']:
            d['passed'] = True
        else:
            d['passed'] = False
        prgr['scores'].append(d)
        self.app.progression[str(self.level)]['scores'] = prgr['scores']
        self.app.progression['save'] = {'last': time.time()}


class AnimProgressBar(ProgressBar):
    def start_progress(self, parent, length):
        Animation.cancel_all(self)
        anim = Animation(value=0, duration=length)
        anim.bind(on_complete=parent.press_ok)
        anim.start(self)

    def stop_progress(self):
        Animation.cancel_all(self)


class MafMeesMenu(Screen):
    pass

class MafMeesScreenManager(ScreenManager):
    pass


class SuccessScreen(Screen):
    pass


class FailureScreen(Screen):
    pass


class LevelSelectorScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.name = 'selector'
        self.app = App.get_running_app()
        # Build here manually, as we need to dynamically build it up
        b0 = BoxLayout(orientation='vertical')
        # Add to self
        self.add_widget(b0)
        l0 = Label(text='Choose a Level', font_size=50, size_hint_y=None)
        b0.add_widget(l0)
        self.g0 = GridLayout(cols=4, padding=10)
        b0.add_widget(self.g0)
        self.draw()

    def on_pre_enter(self, *args):
        self.draw()

    def switch(self, instance):
        self.app.chosen_level = int(instance.id.split('_')[1])
        self.parent.current = 'menu'

    def draw(self):
        # Remove all the widgets
        self.g0.clear_widgets()
        # And add them again, based on the latest numbers.
        max_levels = self.app.progression['totals']['max_level']
        i = 0
        while i <= max_levels:
            btn = Button(id='level_' + str(i), text='Level ' + str(i), on_release=self.switch)
            self.g0.add_widget(btn)
            i += 1

class ReportScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.name = 'reports'
        # Building here manually, as we need to dynamically build it up
        b0 = BoxLayout(orientation='horizontal')
        sv0 = ScrollView(do_scroll_x=False)
        b0.add_widget(sv0)
        self.gl1 = GridLayout(cols=1, size_hint_y=None)
        self.gl1.bind(minimum_height=self.gl1.setter('height'))
        sv0.add_widget(self.gl1)
        # Next is the view for the actual report
        self.sv1 = ScrollView(do_scroll_x=False)
        b0.add_widget(self.sv1)
        # And add the root element to this widget
        self.add_widget(b0)

    def create_menu(self):
        # Clear the parent of everything
        self.gl1.clear_widgets()
        # Add a back button
        btn = Button(id='back', text='Back to Menu', on_release=self.back_to_menu, size_hint_y=None)
        self.gl1.add_widget(btn)
        # Now add the levels as needed
        max_levels = self.app.progression['totals']['max_level']
        i = 0
        while i <= max_levels:
            print(str(i))
            btn = Button(id='level_' + str(i), text='Level ' + str(i), on_release=self.show, size_hint_y=None)
            self.gl1.add_widget(btn)
            i += 1

    def on_pre_enter(self, *args):
        self.app = App.get_running_app()
        # Create the menu
        self.create_menu()
        # And now fill the TreeView with data from the high level
        self.show(None, override=(self.app.progression['totals']['max_level']))

    def back_to_menu(self, *args):
        self.parent.current = 'menu'

    def show(self, instance, override=-1):
        # Select a level
        if override >= 0:
            show = override
        else:
            show = int(instance.id.split('_')[1])
        # Remove previous view
        self.sv1.clear_widgets()
        # Create the view
        tv = TreeView(root_options=dict(text='Level ' + str(show) + ' plays'))
        if str(show) in self.app.progression and 'scores' in self.app.progression[str(show)]:
            data = self.app.progression[str(show)]
            node = {}
            for score in data['scores']:
                name = str(datetime.fromtimestamp(int(score['level_start'])).strftime('%Y-%m-%d %H:%M:%S'))
                if score['passed']:
                    color = [0, 1, 0, 1]
                else:
                    color = [1, 0, 0, 1]
                node[score['level_start']] = tv.add_node(TreeViewLabel(text=name, color=color))
                for q in data['questions'][str(score['level_start'])]:
                    question = "%s %s %s = %s (%ss)" % (q['o1'], q['op'], q['o2'], q['answer_given'], q['time_taken'])
                    if q['answer_correct']:
                        color = [0, 1, 0, 1]
                    else:
                        color = [1, 0, 0, 1]
                    tv.add_node(TreeViewLabel(text=question, color=color), node[score['level_start']])
        else:
            tv.add_node(TreeViewLabel(text='No plays yet.'))
        # Finally, add the treeview to the scrollview
        self.sv1.add_widget(tv)

class MafMeesRekenenApp(App):
    chosen_level = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.localdatafile = os.path.join(self.user_data_dir, 'progression.json')
        self.progression = JsonStore(self.localdatafile)
        if len(self.progression) == 0:
            self.progression['totals'] = {'max_level': 0}
            self.chosen_level = 0
        else:
            self.chosen_level = self.progression['totals']['max_level']
        Window.bind(on_keyboard=self.on_kbd)

    def build(self):
        self.screenmanager = MafMeesScreenManager()
        return self.screenmanager

    def on_kbd(self, window, key, *args):
        # user presses back button
        if key == 27:
            return True

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
                'num': 30,  # Number of questions
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
            },
            3: {
                'left_min': 30,  # Minimum for left argument
                'left_max': 40,  # Maximum for left argument
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
            4: {
                'left_min': 40,  # Minimum for left argument
                'left_max': 50,  # Maximum for left argument
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
            5: {
                'left_min': 1,  # Minimum for left argument
                'left_max': 50,  # Maximum for left argument
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
            6: {
                'left_min': 1,  # Minimum for left argument
                'left_max': 9,  # Maximum for left argument
                'right_min': 1,  # Minimum for right argument
                'right_max': 9,  # Maximum for right argument
                'op_add': False,  # Allow addition?
                'op_sub': True,  # Allow substraction?
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
            7: {
                'left_min': 10,  # Minimum for left argument
                'left_max': 20,  # Maximum for left argument
                'right_min': 1,  # Minimum for right argument
                'right_max': 9,  # Maximum for right argument
                'op_add': False,  # Allow addition?
                'op_sub': True,  # Allow substraction?
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
            8: {
                'left_min': 20,  # Minimum for left argument
                'left_max': 30,  # Maximum for left argument
                'right_min': 1,  # Minimum for right argument
                'right_max': 9,  # Maximum for right argument
                'op_add': False,  # Allow addition?
                'op_sub': True,  # Allow substraction?
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
            9: {
                'left_min': 30,  # Minimum for left argument
                'left_max': 40,  # Maximum for left argument
                'right_min': 1,  # Minimum for right argument
                'right_max': 9,  # Maximum for right argument
                'op_add': False,  # Allow addition?
                'op_sub': True,  # Allow substraction?
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
            10: {
                'left_min': 40,  # Minimum for left argument
                'left_max': 50,  # Maximum for left argument
                'right_min': 1,  # Minimum for right argument
                'right_max': 9,  # Maximum for right argument
                'op_add': False,  # Allow addition?
                'op_sub': True,  # Allow substraction?
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
            11: {
                'left_min': 1,  # Minimum for left argument
                'left_max': 50,  # Maximum for left argument
                'right_min': 1,  # Minimum for right argument
                'right_max': 9,  # Maximum for right argument
                'op_add': False,  # Allow addition?
                'op_sub': True,  # Allow substraction?
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
            12: {
                'left_min': 1,  # Minimum for left argument
                'left_max': 50,  # Maximum for left argument
                'right_min': 1,  # Minimum for right argument
                'right_max': 9,  # Maximum for right argument
                'op_add': True,  # Allow addition?
                'op_sub': True,  # Allow substraction?
                'op_mul': False,  # Allow multiplication?
                'op_div': False,  # Allow division?
                'int_only': True,  # Only allow sums that have an integer as result?
                'num': 30,  # Number of questions
                'time': 30,  # Max time per question allowed, in seconds
                'ok_point': 1,  # Point for a correctly answered question
                'fail_point': -1,  # Point for an incorrectly answered question
                'doubler_at': 10,  # If a question is answered within this amount of seconds, points are doubled
                'bronze': 40,  # Number of points required for next level
                'silver': 50,  # Number of points required for well done
                'gold': 55,  # Number of points required for mastery
            },
            13: {
                'left_min': 1,  # Minimum for left argument
                'left_max': 50,  # Maximum for left argument
                'right_min': 1,  # Minimum for right argument
                'right_max': 20,  # Maximum for right argument
                'op_add': True,  # Allow addition?
                'op_sub': True,  # Allow substraction?
                'op_mul': False,  # Allow multiplication?
                'op_div': False,  # Allow division?
                'int_only': True,  # Only allow sums that have an integer as result?
                'num': 30,  # Number of questions
                'time': 30,  # Max time per question allowed, in seconds
                'ok_point': 1,  # Point for a correctly answered question
                'fail_point': -1,  # Point for an incorrectly answered question
                'doubler_at': 10,  # If a question is answered within this amount of seconds, points are doubled
                'bronze': 40,  # Number of points required for next level
                'silver': 50,  # Number of points required for well done
                'gold': 55,  # Number of points required for mastery
            },
            14: {
                'left_min': 1,  # Minimum for left argument
                'left_max': 50,  # Maximum for left argument
                'right_min': 1,  # Minimum for right argument
                'right_max': 30,  # Maximum for right argument
                'op_add': True,  # Allow addition?
                'op_sub': True,  # Allow substraction?
                'op_mul': False,  # Allow multiplication?
                'op_div': False,  # Allow division?
                'int_only': True,  # Only allow sums that have an integer as result?
                'num': 30,  # Number of questions
                'time': 30,  # Max time per question allowed, in seconds
                'ok_point': 1,  # Point for a correctly answered question
                'fail_point': -1,  # Point for an incorrectly answered question
                'doubler_at': 10,  # If a question is answered within this amount of seconds, points are doubled
                'bronze': 40,  # Number of points required for next level
                'silver': 50,  # Number of points required for well done
                'gold': 55,  # Number of points required for mastery
            },
            15: {
                'left_min': 1,  # Minimum for left argument
                'left_max': 50,  # Maximum for left argument
                'right_min': 1,  # Minimum for right argument
                'right_max': 40,  # Maximum for right argument
                'op_add': True,  # Allow addition?
                'op_sub': True,  # Allow substraction?
                'op_mul': False,  # Allow multiplication?
                'op_div': False,  # Allow division?
                'int_only': True,  # Only allow sums that have an integer as result?
                'num': 30,  # Number of questions
                'time': 30,  # Max time per question allowed, in seconds
                'ok_point': 1,  # Point for a correctly answered question
                'fail_point': -1,  # Point for an incorrectly answered question
                'doubler_at': 10,  # If a question is answered within this amount of seconds, points are doubled
                'bronze': 40,  # Number of points required for next level
                'silver': 50,  # Number of points required for well done
                'gold': 55,  # Number of points required for mastery
            },
            16: {
                'left_min': 1,  # Minimum for left argument
                'left_max': 60,  # Maximum for left argument
                'right_min': 1,  # Minimum for right argument
                'right_max': 50,  # Maximum for right argument
                'op_add': True,  # Allow addition?
                'op_sub': True,  # Allow substraction?
                'op_mul': False,  # Allow multiplication?
                'op_div': False,  # Allow division?
                'int_only': True,  # Only allow sums that have an integer as result?
                'num': 30,  # Number of questions
                'time': 30,  # Max time per question allowed, in seconds
                'ok_point': 1,  # Point for a correctly answered question
                'fail_point': -1,  # Point for an incorrectly answered question
                'doubler_at': 10,  # If a question is answered within this amount of seconds, points are doubled
                'bronze': 40,  # Number of points required for next level
                'silver': 50,  # Number of points required for well done
                'gold': 55,  # Number of points required for mastery
            },
            17: {
                'left_min': 1,  # Minimum for left argument
                'left_max': 70,  # Maximum for left argument
                'right_min': 1,  # Minimum for right argument
                'right_max': 60,  # Maximum for right argument
                'op_add': True,  # Allow addition?
                'op_sub': True,  # Allow substraction?
                'op_mul': False,  # Allow multiplication?
                'op_div': False,  # Allow division?
                'int_only': True,  # Only allow sums that have an integer as result?
                'num': 30,  # Number of questions
                'time': 30,  # Max time per question allowed, in seconds
                'ok_point': 1,  # Point for a correctly answered question
                'fail_point': -1,  # Point for an incorrectly answered question
                'doubler_at': 10,  # If a question is answered within this amount of seconds, points are doubled
                'bronze': 40,  # Number of points required for next level
                'silver': 50,  # Number of points required for well done
                'gold': 55,  # Number of points required for mastery
            },
            18: {
                'left_min': 1,  # Minimum for left argument
                'left_max': 80,  # Maximum for left argument
                'right_min': 1,  # Minimum for right argument
                'right_max': 70,  # Maximum for right argument
                'op_add': True,  # Allow addition?
                'op_sub': True,  # Allow substraction?
                'op_mul': False,  # Allow multiplication?
                'op_div': False,  # Allow division?
                'int_only': True,  # Only allow sums that have an integer as result?
                'num': 30,  # Number of questions
                'time': 30,  # Max time per question allowed, in seconds
                'ok_point': 1,  # Point for a correctly answered question
                'fail_point': -1,  # Point for an incorrectly answered question
                'doubler_at': 10,  # If a question is answered within this amount of seconds, points are doubled
                'bronze': 40,  # Number of points required for next level
                'silver': 50,  # Number of points required for well done
                'gold': 55,  # Number of points required for mastery
            },
            19: {
                'left_min': 1,  # Minimum for left argument
                'left_max': 90,  # Maximum for left argument
                'right_min': 1,  # Minimum for right argument
                'right_max': 80,  # Maximum for right argument
                'op_add': True,  # Allow addition?
                'op_sub': True,  # Allow substraction?
                'op_mul': False,  # Allow multiplication?
                'op_div': False,  # Allow division?
                'int_only': True,  # Only allow sums that have an integer as result?
                'num': 30,  # Number of questions
                'time': 30,  # Max time per question allowed, in seconds
                'ok_point': 1,  # Point for a correctly answered question
                'fail_point': -1,  # Point for an incorrectly answered question
                'doubler_at': 10,  # If a question is answered within this amount of seconds, points are doubled
                'bronze': 40,  # Number of points required for next level
                'silver': 50,  # Number of points required for well done
                'gold': 55,  # Number of points required for mastery
            },
            20: {
                'left_min': 1,  # Minimum for left argument
                'left_max': 100,  # Maximum for left argument
                'right_min': 1,  # Minimum for right argument
                'right_max': 90,  # Maximum for right argument
                'op_add': True,  # Allow addition?
                'op_sub': True,  # Allow substraction?
                'op_mul': False,  # Allow multiplication?
                'op_div': False,  # Allow division?
                'int_only': True,  # Only allow sums that have an integer as result?
                'num': 30,  # Number of questions
                'time': 30,  # Max time per question allowed, in seconds
                'ok_point': 1,  # Point for a correctly answered question
                'fail_point': -1,  # Point for an incorrectly answered question
                'doubler_at': 10,  # If a question is answered within this amount of seconds, points are doubled
                'bronze': 40,  # Number of points required for next level
                'silver': 50,  # Number of points required for well done
                'gold': 55,  # Number of points required for mastery
            },
            21: {
                'left_min': 1,  # Minimum for left argument
                'left_max': 100,  # Maximum for left argument
                'right_min': 1,  # Minimum for right argument
                'right_max': 100,  # Maximum for right argument
                'op_add': True,  # Allow addition?
                'op_sub': True,  # Allow substraction?
                'op_mul': False,  # Allow multiplication?
                'op_div': False,  # Allow division?
                'int_only': True,  # Only allow sums that have an integer as result?
                'num': 30,  # Number of questions
                'time': 30,  # Max time per question allowed, in seconds
                'ok_point': 1,  # Point for a correctly answered question
                'fail_point': -1,  # Point for an incorrectly answered question
                'doubler_at': 10,  # If a question is answered within this amount of seconds, points are doubled
                'bronze': 40,  # Number of points required for next level
                'silver': 50,  # Number of points required for well done
                'gold': 55,  # Number of points required for mastery
            },
            22: {
                'left_min': 1,  # Minimum for left argument
                'left_max': 100,  # Maximum for left argument
                'right_min': 1,  # Minimum for right argument
                'right_max': 100,  # Maximum for right argument
                'op_add': True,  # Allow addition?
                'op_sub': True,  # Allow substraction?
                'op_mul': False,  # Allow multiplication?
                'op_div': False,  # Allow division?
                'int_only': True,  # Only allow sums that have an integer as result?
                'num': 60,  # Number of questions
                'time': 30,  # Max time per question allowed, in seconds
                'ok_point': 1,  # Point for a correctly answered question
                'fail_point': -1,  # Point for an incorrectly answered question
                'doubler_at': 10,  # If a question is answered within this amount of seconds, points are doubled
                'bronze': 70,  # Number of points required for next level
                'silver': 90,  # Number of points required for well done
                'gold': 110,  # Number of points required for mastery
            },
            23: {
                'left_min': 100,  # Minimum for left argument
                'left_max': 200,  # Maximum for left argument
                'right_min': 1,  # Minimum for right argument
                'right_max': 100,  # Maximum for right argument
                'op_add': True,  # Allow addition?
                'op_sub': True,  # Allow substraction?
                'op_mul': False,  # Allow multiplication?
                'op_div': False,  # Allow division?
                'int_only': True,  # Only allow sums that have an integer as result?
                'num': 30,  # Number of questions
                'time': 30,  # Max time per question allowed, in seconds
                'ok_point': 1,  # Point for a correctly answered question
                'fail_point': -1,  # Point for an incorrectly answered question
                'doubler_at': 10,  # If a question is answered within this amount of seconds, points are doubled
                'bronze': 40,  # Number of points required for next level
                'silver': 50,  # Number of points required for well done
                'gold': 55,  # Number of points required for mastery
            },
            24: {
                'left_min': 200,  # Minimum for left argument
                'left_max': 300,  # Maximum for left argument
                'right_min': 1,  # Minimum for right argument
                'right_max': 100,  # Maximum for right argument
                'op_add': True,  # Allow addition?
                'op_sub': True,  # Allow substraction?
                'op_mul': False,  # Allow multiplication?
                'op_div': False,  # Allow division?
                'int_only': True,  # Only allow sums that have an integer as result?
                'num': 30,  # Number of questions
                'time': 30,  # Max time per question allowed, in seconds
                'ok_point': 1,  # Point for a correctly answered question
                'fail_point': -1,  # Point for an incorrectly answered question
                'doubler_at': 10,  # If a question is answered within this amount of seconds, points are doubled
                'bronze': 40,  # Number of points required for next level
                'silver': 50,  # Number of points required for well done
                'gold': 55,  # Number of points required for mastery
            },
            25: {
                'left_min': 1,  # Minimum for left argument
                'left_max': 500,  # Maximum for left argument
                'right_min': 1,  # Minimum for right argument
                'right_max': 100,  # Maximum for right argument
                'op_add': True,  # Allow addition?
                'op_sub': True,  # Allow substraction?
                'op_mul': False,  # Allow multiplication?
                'op_div': False,  # Allow division?
                'int_only': True,  # Only allow sums that have an integer as result?
                'num': 30,  # Number of questions
                'time': 30,  # Max time per question allowed, in seconds
                'ok_point': 1,  # Point for a correctly answered question
                'fail_point': -1,  # Point for an incorrectly answered question
                'doubler_at': 10,  # If a question is answered within this amount of seconds, points are doubled
                'bronze': 40,  # Number of points required for next level
                'silver': 50,  # Number of points required for well done
                'gold': 55,  # Number of points required for mastery
            },
            26: {
                'left_min': 200,  # Minimum for left argument
                'left_max': 600,  # Maximum for left argument
                'right_min': 100,  # Minimum for right argument
                'right_max': 200,  # Maximum for right argument
                'op_add': True,  # Allow addition?
                'op_sub': True,  # Allow substraction?
                'op_mul': False,  # Allow multiplication?
                'op_div': False,  # Allow division?
                'int_only': True,  # Only allow sums that have an integer as result?
                'num': 30,  # Number of questions
                'time': 30,  # Max time per question allowed, in seconds
                'ok_point': 1,  # Point for a correctly answered question
                'fail_point': -1,  # Point for an incorrectly answered question
                'doubler_at': 10,  # If a question is answered within this amount of seconds, points are doubled
                'bronze': 40,  # Number of points required for next level
                'silver': 50,  # Number of points required for well done
                'gold': 55,  # Number of points required for mastery
            },
            27: {
                'left_min': 100,  # Minimum for left argument
                'left_max': 900,  # Maximum for left argument
                'right_min': 100,  # Minimum for right argument
                'right_max': 900,  # Maximum for right argument
                'op_add': True,  # Allow addition?
                'op_sub': True,  # Allow substraction?
                'op_mul': False,  # Allow multiplication?
                'op_div': False,  # Allow division?
                'int_only': True,  # Only allow sums that have an integer as result?
                'num': 30,  # Number of questions
                'time': 30,  # Max time per question allowed, in seconds
                'ok_point': 1,  # Point for a correctly answered question
                'fail_point': -1,  # Point for an incorrectly answered question
                'doubler_at': 10,  # If a question is answered within this amount of seconds, points are doubled
                'bronze': 40,  # Number of points required for next level
                'silver': 50,  # Number of points required for well done
                'gold': 60,  # Number of points required for mastery
            },
            28: {
                'left_min': 1,  # Minimum for left argument
                'left_max': 50,  # Maximum for left argument
                'right_min': 2,  # Minimum for right argument
                'right_max': 2,  # Maximum for right argument
                'op_add': False,  # Allow addition?
                'op_sub': False,  # Allow substraction?
                'op_mul': True,  # Allow multiplication?
                'op_div': False,  # Allow division?
                'int_only': True,  # Only allow sums that have an integer as result?
                'num': 60,  # Number of questions
                'time': 30,  # Max time per question allowed, in seconds
                'ok_point': 1,  # Point for a correctly answered question
                'fail_point': -1,  # Point for an incorrectly answered question
                'doubler_at': 10,  # If a question is answered within this amount of seconds, points are doubled
                'bronze': 60,  # Number of points required for next level
                'silver': 100,  # Number of points required for well done
                'gold': 120,  # Number of points required for mastery
            },
            29: {
                'left_min': 1,  # Minimum for left argument
                'left_max': 50,  # Maximum for left argument
                'right_min': 2,  # Minimum for right argument
                'right_max': 3,  # Maximum for right argument
                'op_add': False,  # Allow addition?
                'op_sub': False,  # Allow substraction?
                'op_mul': True,  # Allow multiplication?
                'op_div': False,  # Allow division?
                'int_only': True,  # Only allow sums that have an integer as result?
                'num': 60,  # Number of questions
                'time': 30,  # Max time per question allowed, in seconds
                'ok_point': 1,  # Point for a correctly answered question
                'fail_point': -1,  # Point for an incorrectly answered question
                'doubler_at': 10,  # If a question is answered within this amount of seconds, points are doubled
                'bronze': 60,  # Number of points required for next level
                'silver': 100,  # Number of points required for well done
                'gold': 120,  # Number of points required for mastery
            },
            30: {
                'left_min': 100,  # Minimum for left argument
                'left_max': 900,  # Maximum for left argument
                'right_min': 100,  # Minimum for right argument
                'right_max': 900,  # Maximum for right argument
                'op_add': True,  # Allow addition?
                'op_sub': True,  # Allow substraction?
                'op_mul': False,  # Allow multiplication?
                'op_div': False,  # Allow division?
                'int_only': True,  # Only allow sums that have an integer as result?
                'num': 60,  # Number of questions
                'time': 20,  # Max time per question allowed, in seconds
                'ok_point': 1,  # Point for a correctly answered question
                'fail_point': -1,  # Point for an incorrectly answered question
                'doubler_at': 7,  # If a question is answered within this amount of seconds, points are doubled
                'bronze': 60,  # Number of points required for next level
                'silver': 100,  # Number of points required for well done
                'gold': 120,  # Number of points required for mastery
            },
            31: {
                'left_min': 300,  # Minimum for left argument
                'left_max': 900,  # Maximum for left argument
                'right_min': 300,  # Minimum for right argument
                'right_max': 900,  # Maximum for right argument
                'op_add': True,  # Allow addition?
                'op_sub': True,  # Allow substraction?
                'op_mul': False,  # Allow multiplication?
                'op_div': False,  # Allow division?
                'int_only': True,  # Only allow sums that have an integer as result?
                'num': 60,  # Number of questions
                'time': 20,  # Max time per question allowed, in seconds
                'ok_point': 1,  # Point for a correctly answered question
                'fail_point': -1,  # Point for an incorrectly answered question
                'doubler_at': 7,  # If a question is answered within this amount of seconds, points are doubled
                'bronze': 60,  # Number of points required for next level
                'silver': 100,  # Number of points required for well done
                'gold': 120,  # Number of points required for mastery
            },
            32: {
                'left_min': 100,  # Minimum for left argument
                'left_max': 900,  # Maximum for left argument
                'right_min': 100,  # Minimum for right argument
                'right_max': 900,  # Maximum for right argument
                'op_add': True,  # Allow addition?
                'op_sub': True,  # Allow substraction?
                'op_mul': False,  # Allow multiplication?
                'op_div': False,  # Allow division?
                'int_only': True,  # Only allow sums that have an integer as result?
                'num': 60,  # Number of questions
                'time': 30,  # Max time per question allowed, in seconds
                'ok_point': 1,  # Point for a correctly answered question
                'fail_point': -1,  # Point for an incorrectly answered question
                'doubler_at': 10,  # If a question is answered within this amount of seconds, points are doubled
                'bronze': 40,  # Number of points required for next level
                'silver': 50,  # Number of points required for well done
                'gold': 55,  # Number of points required for mastery
            },
            33: {
                'left_min': 10,  # Minimum for left argument
                'left_max': 90,  # Maximum for left argument
                'right_min': 2,  # Minimum for right argument
                'right_max': 5,  # Maximum for right argument
                'op_add': False,  # Allow addition?
                'op_sub': False,  # Allow substraction?
                'op_mul': True,  # Allow multiplication?
                'op_div': False,  # Allow division?
                'int_only': True,  # Only allow sums that have an integer as result?
                'num': 60,  # Number of questions
                'time': 30,  # Max time per question allowed, in seconds
                'ok_point': 1,  # Point for a correctly answered question
                'fail_point': -1,  # Point for an incorrectly answered question
                'doubler_at': 10,  # If a question is answered within this amount of seconds, points are doubled
                'bronze': 60,  # Number of points required for next level
                'silver': 100,  # Number of points required for well done
                'gold': 120,  # Number of points required for mastery
            },
        }

        # Actually return the data
        return levels[num]


if __name__ == '__main__':
    MafMeesRekenenApp().run()
